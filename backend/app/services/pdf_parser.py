import base64
import json as _json
import os
import re
from typing import List, Optional

import fitz  # PyMuPDF
import httpx

# OCR 依赖（可选），仅在扫描版 PDF 时使用
try:
    import pytesseract
    from PIL import Image
    import io
    _OCR_AVAILABLE = True
except ImportError:
    _OCR_AVAILABLE = False

# 每页文本少于此字符数时视为扫描页，触发 OCR
_SCANNED_PAGE_THRESHOLD = 50
# OCR 渲染 DPI（越高越准，越慢）
_OCR_DPI = 200

# DOI 正则：匹配 10.XXXX/... 格式
_DOI_PATTERN = re.compile(r'\b(10\.\d{4,9}/[^\s\]><,;\'"\u201c\u201d\uff09\uff08]+)', re.IGNORECASE)


class PDFParser:
    """PDF 解析与分块服务，支持文本版和扫描版 PDF"""

    # ── 内部：DOI 提取与 CrossRef 查询 ────────────────────────────────────────

    def _extract_doi(self, text: str, pdf_meta: dict) -> str:
        """从文本或 PDF 元数据中提取 DOI。"""
        # 先尝试 PDF 元数据中的 doi / subject 字段
        for key in ("doi", "subject", "keywords"):
            val = pdf_meta.get(key, "") or ""
            m = _DOI_PATTERN.search(val)
            if m:
                return m.group(1).rstrip(".")
        # 再在文本中搜索
        m = _DOI_PATTERN.search(text)
        if m:
            return m.group(1).rstrip(".")
        return ""

    def _sanitize_pdf_meta(self, title: str, authors: str) -> tuple[str, str]:
        """
        过滤 PDF 内置元数据中明显无效的标题和作者。
        常见污染来源：Word/WPS 导出时写入的窗口标题和系统用户名。
        返回 (cleaned_title, cleaned_authors)。
        """
        # ── 无效标题模式 ─────────────────────────────────────────────────────
        _INVALID_TITLE_PATTERNS = re.compile(
            r'Microsoft\s+(Word|Office|Excel|PowerPoint)'  # Word 窗口标题
            r'|WPS\s+(Writer|Office)'                      # WPS 窗口标题
            r'|\.(doc|docx|xls|xlsx|ppt|pptx|wps|odt|rtf)$'  # 以文档扩展名结尾
            r'|^(Untitled|无标题|新建文档|document\d*|slide\d*)$',  # 通用占位名
            re.IGNORECASE,
        )
        # ── 无效作者模式（单个系统用户名）────────────────────────────────────
        _INVALID_AUTHOR_PATTERNS = re.compile(
            r'^(new|user|admin|administrator|owner|default|guest'
            r'|unknown|author|pc|desktop|laptop|computer|\d+)$',
            re.IGNORECASE,
        )

        clean_title = title.strip()
        if _INVALID_TITLE_PATTERNS.search(clean_title):
            clean_title = ""

        clean_authors = authors.strip()
        if _INVALID_AUTHOR_PATTERNS.match(clean_authors):
            clean_authors = ""

        return clean_title, clean_authors

    def _query_crossref(self, doi: str) -> dict:
        """通过 CrossRef API 查询 DOI，返回标准化的 title 和 authors。"""
        try:
            url = f"https://api.crossref.org/works/{doi}"
            # trust_env=False：忽略系统代理，避免 SOCKS 代理依赖问题
            resp = httpx.get(url, timeout=8.0, trust_env=False,
                             headers={"User-Agent": "PaperPilot/1.0 (mailto:support@paperpilot.app)"})
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") == "ok":
                    msg = data["message"]
                    title = (msg.get("title") or [""])[0]
                    authors_list = msg.get("author") or []
                    authors = "; ".join(
                        f"{a.get('given', '')} {a.get('family', '')}".strip()
                        for a in authors_list
                        if a.get("family") or a.get("given")
                    )
                    return {"title": title, "authors": authors}
        except Exception as e:
            print(f"[PDFParser] CrossRef 查询失败 (doi={doi}): {e}")
        return {}

    def _extract_metadata_by_vision(self, file_path: str) -> dict:
        """
        将首页渲染为图片，调用视觉大模型提取标题、作者、DOI。
        仅在 ARK_VISION_MODEL 已配置时生效；出错时静默返回空字典。
        """
        from ..config import Config
        from openai import OpenAI
        vision_model = Config.ARK_VISION_MODEL
        if not vision_model or not Config.ARK_API_KEY:
            return {}
        try:
            doc = fitz.open(file_path)
            pix = doc[0].get_pixmap(matrix=fitz.Matrix(2, 2), colorspace=fitz.csRGB)
            doc.close()
            b64 = base64.b64encode(pix.tobytes("png")).decode()

            client = OpenAI(api_key=Config.ARK_API_KEY, base_url=Config.ARK_BASE_URL)
            resp = client.chat.completions.create(
                model=vision_model,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "image_url",
                         "image_url": {"url": f"data:image/png;base64,{b64}"}},
                        {"type": "text",
                         "text": (
                             "请从这篇学术论文首页图片中提取以下信息。"
                             "作者字段请列出所有作者，用分号分隔。"
                             "找不到的字段留空字符串。"
                             "只返回 JSON，不要有任何其他文字：\n"
                             '{"title": "论文完整标题", "authors": "作者1; 作者2", "doi": "DOI号"}'
                         )},
                    ],
                }],
                temperature=0,
                max_tokens=512,
            )
            text = resp.choices[0].message.content.strip()
            m = re.search(r'\{.*\}', text, re.DOTALL)
            if m:
                data = _json.loads(m.group())
                return {k: str(data.get(k, "")).strip() for k in ("title", "authors", "doi")}
        except Exception as e:
            print(f"[PDFParser] 视觉模型提取元数据失败: {e}")
        return {}

    # ── 内部：OCR 单页 ─────────────────────────────────────────────────────────

    def _ocr_page(self, page: fitz.Page) -> str:
        """将一页渲染为图片后 OCR，返回识别文本。"""
        if not _OCR_AVAILABLE:
            return ""
        try:
            mat = fitz.Matrix(_OCR_DPI / 72, _OCR_DPI / 72)
            pix = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            # chi_sim+eng 覆盖中英混排论文
            text = pytesseract.image_to_string(img, lang="chi_sim+eng")
            return text
        except Exception as e:
            print(f"[PDFParser] OCR 失败（第 {page.number + 1} 页）: {e}")
            return ""

    def _extract_pages(self, file_path: str) -> List[tuple]:
        """
        逐页提取文本，扫描页自动 OCR。
        返回 [(page_number, text), ...]，page_number 从 1 开始。
        """
        result = []
        doc = fitz.open(file_path)

        # 判断整份 PDF 是否为扫描版（全文本量极少）
        total_native = sum(len(doc[i].get_text("text").strip()) for i in range(len(doc)))
        is_scanned = total_native < _SCANNED_PAGE_THRESHOLD * len(doc)

        if is_scanned and not _OCR_AVAILABLE:
            print("[PDFParser] 检测到扫描版 PDF，但 OCR 依赖未安装（pytesseract / Pillow）")

        if is_scanned:
            print(f"[PDFParser] 检测到扫描版 PDF，启用 OCR（共 {len(doc)} 页）")

        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text("text")

            if len(text.strip()) < _SCANNED_PAGE_THRESHOLD:
                # 该页文本极少，尝试 OCR
                ocr_text = self._ocr_page(page)
                if ocr_text.strip():
                    text = ocr_text

            if text.strip():
                result.append((page_num + 1, text))

        doc.close()
        return result

    # ── 公开：提取元数据 ───────────────────────────────────────────────────────

    def extract_metadata(self, file_path: str) -> dict:
        """
        提取 PDF 元数据：标题、作者、页数、语言。
        尝试从 PDF 元数据和首页文本中提取。
        """
        metadata = {
            "title": "",
            "authors": "",
            "doi": "",
            "page_count": 0,
            "language": "unknown",
            "abstract": "",
        }

        try:
            doc = fitz.open(file_path)
            metadata["page_count"] = len(doc)

            pdf_meta = doc.metadata or {}
            raw_title = pdf_meta.get("title", "") or ""
            raw_authors = pdf_meta.get("author", "") or ""
            doc.close()

            metadata["title"], metadata["authors"] = self._sanitize_pdf_meta(raw_title, raw_authors)

            # 用统一提取（含 OCR 回退）获取首页文本（前两页）
            pages = self._extract_pages(file_path)
            first_page_text = pages[0][1] if pages else ""
            second_page_text = pages[1][1] if len(pages) > 1 else ""
            search_text = first_page_text + "\n" + second_page_text

            # ── 提取 DOI ──────────────────────────────────────────────────────
            doi = self._extract_doi(search_text, pdf_meta)
            metadata["doi"] = doi

            # ── 有 DOI 则通过 CrossRef 获取规范标题和完整作者 ─────────────────
            if doi:
                print(f"[PDFParser] 发现 DOI: {doi}，正在查询 CrossRef …")
                crossref = self._query_crossref(doi)
                if crossref.get("title"):
                    metadata["title"] = crossref["title"]
                if crossref.get("authors"):
                    metadata["authors"] = crossref["authors"]

            # ── 无法从 CrossRef 获取时的兜底提取 ─────────────────────────────
            if not metadata["title"]:
                raw_lines = first_page_text.split("\n")
                # 跳过期刊元数据行：卷号/期号/年份/纯英文期刊名/作者序等
                _SKIP_LINE = re.compile(
                    r'Vol\.?\s*\d|No\.?\s*\d'       # Vol/No 行
                    r'|\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b'  # 月份
                    r'|^\d{4}\s*年'                 # 以年份开头
                    r'|第\s*\d+\s*[卷期]'           # 中文卷期
                    r'|^[A-Za-z][A-Za-z\s,\.\-:&]+$'  # 纯英文行（期刊英文名）
                    r'|^(作者序|前言|序言|摘\s*要|Abstract)$',
                    re.IGNORECASE,
                )
                n = len(raw_lines)
                # 第一遍：优先选"前后均为空行的孤立行"（论文标题的典型排版特征）
                for i in range(min(n, 40)):
                    line = raw_lines[i].strip()
                    if len(line) <= 5 or _SKIP_LINE.search(line):
                        continue
                    prev_blank = (i == 0 or not raw_lines[i - 1].strip())
                    next_blank = (i + 1 >= n or not raw_lines[i + 1].strip())
                    if prev_blank and next_blank:
                        metadata["title"] = line[:200]
                        break
                # 第二遍：兜底——取前20行中第一个长度>5且不被跳过的行
                if not metadata["title"]:
                    for line in [l.strip() for l in raw_lines[:20] if l.strip()]:
                        if len(line) > 5 and not _SKIP_LINE.search(line):
                            metadata["title"] = line[:200]
                            break

            abstract_match = re.search(
                r"(?:Abstract|摘\s*要)[:\s]*\n?(.*?)(?:\n\s*(?:Keywords|关键词|Introduction|1\s|1\.))",
                first_page_text,
                re.DOTALL | re.IGNORECASE,
            )
            if abstract_match:
                metadata["abstract"] = abstract_match.group(1).strip()[:2000]

            chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", first_page_text))
            total_chars = len(first_page_text)
            if total_chars > 0 and chinese_chars / total_chars > 0.3:
                metadata["language"] = "zh"
            else:
                metadata["language"] = "en"

            # ── 作者为空时，从正文文本中二次提取 ────────────────────────────
            if not metadata["authors"]:
                # 策略1：英文罗马拼音作者行（含全部作者），如 "PENG Jiayue, ZU Chenxi, LI Hong"
                en_author_m = re.search(
                    r'^([A-Z]{2,}\s+[A-Za-z]+(?:[,，]\s*[A-Z]{2,}\s+[A-Za-z]+)+)\s*$',
                    search_text,
                    re.MULTILINE,
                )
                if en_author_m:
                    # 统一格式：将逗号替换为分号分隔
                    authors_str = en_author_m.group(1).strip()
                    authors_str = re.sub(r'[,，]\s*', '; ', authors_str)
                    metadata["authors"] = authors_str

            if not metadata["authors"]:
                # 策略2：脚注 "第一作者: 姓名" 格式（仅第一作者，最后兜底）
                footnote_m = re.search(r'第[一]?作者[：:]\s*([\u4e00-\u9fff]{2,5})', search_text)
                if footnote_m:
                    metadata["authors"] = footnote_m.group(1)

            # ── 仍为空时用视觉模型兜底（需配置 ARK_VISION_MODEL）────────────
            if not metadata["authors"] or not metadata["title"]:
                print("[PDFParser] 作者/标题未能识别，尝试视觉模型提取 …")
                vision = self._extract_metadata_by_vision(file_path)
                if vision.get("title") and not metadata["title"]:
                    metadata["title"] = vision["title"]
                if vision.get("authors"):
                    metadata["authors"] = vision["authors"]
                if vision.get("doi") and not metadata["doi"]:
                    metadata["doi"] = vision["doi"]

        except Exception as e:
            print(f"[PDFParser] 提取元数据失败: {e}")

        return metadata

    # ── 公开：解析并分块 ───────────────────────────────────────────────────────

    def parse_and_chunk(
        self, file_path: str, chunk_size: int = 800, chunk_overlap: int = 100
    ) -> List[dict]:
        """
        提取 PDF 全文（扫描版自动 OCR）并按段落边界分块。

        每个 chunk 包含：content, page_number, chunk_index, char_start, char_end
        过滤掉长度小于 50 字符的无效块。
        """
        chunks = []
        try:
            full_text_parts = self._extract_pages(file_path)

            all_text = ""
            char_page_map: List[int] = []

            for page_num, text in full_text_parts:
                all_text += text
                char_page_map.extend([page_num] * len(text))

            if not all_text.strip():
                return []

            paragraphs = re.split(r"\n\s*\n|\n(?=[A-Z0-9])", all_text)
            current_chunk = ""
            current_start = 0
            char_offset = 0
            chunk_index = 0

            for para in paragraphs:
                para = para.strip()
                if not para:
                    char_offset += len(para) + 1
                    continue

                if len(current_chunk) + len(para) + 1 > chunk_size and current_chunk:
                    chunk_end = current_start + len(current_chunk)
                    page_num = self._get_page_for_position(char_page_map, current_start)
                    if len(current_chunk.strip()) >= 50:
                        chunks.append({
                            "content": current_chunk.strip(),
                            "page_number": page_num,
                            "chunk_index": chunk_index,
                            "char_start": current_start,
                            "char_end": chunk_end,
                        })
                        chunk_index += 1

                    overlap_text = current_chunk[-chunk_overlap:] if len(current_chunk) > chunk_overlap else ""
                    current_chunk = overlap_text + " " + para
                    current_start = chunk_end - len(overlap_text)
                else:
                    if current_chunk:
                        current_chunk += "\n" + para
                    else:
                        current_chunk = para
                        current_start = char_offset

                char_offset += len(para) + 1

            if current_chunk.strip() and len(current_chunk.strip()) >= 50:
                chunk_end = current_start + len(current_chunk)
                page_num = self._get_page_for_position(char_page_map, current_start)
                chunks.append({
                    "content": current_chunk.strip(),
                    "page_number": page_num,
                    "chunk_index": chunk_index,
                    "char_start": current_start,
                    "char_end": chunk_end,
                })

        except Exception as e:
            print(f"[PDFParser] 解析分块失败: {e}")
            raise

        return chunks

    # ── 内部工具 ───────────────────────────────────────────────────────────────

    def _get_page_for_position(self, char_page_map: list, position: int) -> int:
        """根据字符位置获取对应页码"""
        if not char_page_map:
            return 1
        idx = min(position, len(char_page_map) - 1)
        idx = max(0, idx)
        return char_page_map[idx]
