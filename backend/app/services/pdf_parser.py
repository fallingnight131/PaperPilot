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

    def _query_doi_metadata(self, doi: str) -> dict:
        """
        通过 DOI 查询标题和作者。
        1. CrossRef API：国际期刊，数据完整
        2. doi.org CSL JSON 内容协商：覆盖万方/知网等中文期刊
        """
        ua = "PaperPilot/1.0 (mailto:support@paperpilot.app)"

        # 1. CrossRef（国际期刊）
        try:
            resp = httpx.get(f"https://api.crossref.org/works/{doi}",
                             timeout=8.0, trust_env=False,
                             headers={"User-Agent": ua})
            if resp.status_code == 200:
                msg = resp.json().get("message", {})
                title = (msg.get("title") or [""])[0]
                authors = "; ".join(
                    f"{a.get('given', '')} {a.get('family', '')}".strip()
                    for a in (msg.get("author") or [])
                    if a.get("family") or a.get("given")
                )
                if title:
                    print(f"[PDFParser] CrossRef 找到: {title[:50]}")
                    return {"title": title, "authors": authors}
        except Exception as e:
            print(f"[PDFParser] CrossRef 查询失败: {e}")

        # 2. doi.org CSL JSON 内容协商（覆盖中文期刊）
        try:
            resp = httpx.get(
                f"https://doi.org/{doi}",
                timeout=12.0, trust_env=False, follow_redirects=True,
                headers={
                    "Accept": "application/vnd.citationstyles.csl+json",
                    "User-Agent": ua,
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                title = data.get("title", "").strip()
                authors = "; ".join(
                    (a.get("literal")
                     or f"{a.get('family', '')} {a.get('given', '')}".strip()
                     or a.get("given", "")).strip()
                    for a in (data.get("author") or [])
                    if a.get("literal") or a.get("family") or a.get("given")
                )
                if title:
                    print(f"[PDFParser] doi.org CSL 找到: {title[:50]}")
                    return {"title": title, "authors": authors}
        except Exception as e:
            print(f"[PDFParser] doi.org CSL 查询失败: {e}")

        return {}

    # ── 内部：OCR 单页 ─────────────────────────────────────────────────────────

    def _ocr_page(self, page: fitz.Page) -> str:
        """
        将一页渲染为图片后 OCR，返回识别文本。
        使用 image_to_data 获取词级坐标，按行分组后应用栏位检测，
        处理双栏布局与单栏摘要混排的情况。
        """
        if not _OCR_AVAILABLE:
            return ""
        try:
            mat = fitz.Matrix(_OCR_DPI / 72, _OCR_DPI / 72)
            pix = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            img_width = img.width

            data = pytesseract.image_to_data(
                img,
                lang="chi_sim+eng",
                output_type=pytesseract.Output.DICT,
            )

            # 按 (block_num, par_num, line_num) 分组，还原每一行
            lines: dict = {}
            n = len(data["level"])
            for i in range(n):
                if data["level"][i] != 5:       # 只取词级（level=5）
                    continue
                conf = data["conf"][i]
                if int(conf) < 0:               # 过滤无效识别
                    continue
                text = data["text"][i].strip()
                if not text:
                    continue

                key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
                left = data["left"][i]
                top = data["top"][i]
                right = left + data["width"][i]

                if key not in lines:
                    lines[key] = {"x0": left, "y0": top, "x1": right, "words": []}
                else:
                    lines[key]["x0"] = min(lines[key]["x0"], left)
                    lines[key]["y0"] = min(lines[key]["y0"], top)
                    lines[key]["x1"] = max(lines[key]["x1"], right)
                lines[key]["words"].append(text)

            if not lines:
                return ""

            # 构建行列表：(x0, y0, x1, text)
            line_list = [
                (v["x0"], v["y0"], v["x1"], "".join(v["words"]))
                for v in lines.values()
            ]

            # 复用与原生文本相同的栏位检测逻辑（坐标换成像素）
            mid_x = img_width / 2
            tolerance = img_width * 0.03

            full_blocks, left_col, right_col = [], [], []
            for x0, y0, x1, text in line_list:
                if x0 < mid_x - tolerance and x1 > mid_x + tolerance:
                    full_blocks.append((y0, text))
                elif x1 <= mid_x + tolerance:
                    left_col.append((y0, text))
                else:
                    right_col.append((y0, text))

            is_two_col = bool(left_col) and bool(right_col)
            if is_two_col:
                col_start_y = min(b[0] for b in left_col + right_col)
                top_full = sorted(
                    [(y0, t) for y0, t in full_blocks if y0 <= col_start_y],
                    key=lambda b: b[0],
                )
                bottom_full = sorted(
                    [(y0, t) for y0, t in full_blocks if y0 > col_start_y],
                    key=lambda b: b[0],
                )
                ordered = (
                    top_full
                    + sorted(left_col, key=lambda b: b[0])
                    + sorted(right_col, key=lambda b: b[0])
                    + bottom_full
                )
            else:
                ordered = sorted(full_blocks + left_col + right_col, key=lambda b: b[0])

            return "\n".join(t for _, t in ordered)

        except Exception as e:
            print(f"[PDFParser] OCR 失败（第 {page.number + 1} 页）: {e}")
            return ""

    def _extract_page_text(self, page: fitz.Page) -> str:
        """
        从单页提取文本，自动识别双栏布局。
        以页面中线为界：跨越中线的块为全宽块，两侧各自的块为左/右栏。
        顺序：顶部全宽块 → 左栏 → 右栏 → 底部全宽块。
        """
        blocks = page.get_text("blocks")
        # blocks 格式：(x0, y0, x1, y1, text, block_no, block_type)
        text_blocks = [
            (b[0], b[1], b[2], b[4])
            for b in blocks
            if b[6] == 0 and b[4].strip()
        ]
        if not text_blocks:
            return ""

        page_width = page.rect.width
        mid_x = page_width / 2
        # 允许 3% 容差，避免恰好压线的块判断错误
        tolerance = page_width * 0.03

        full_blocks = []  # 全宽块（跨越中线）
        left_col = []     # 左栏块
        right_col = []    # 右栏块

        for x0, y0, x1, text in text_blocks:
            if x0 < mid_x - tolerance and x1 > mid_x + tolerance:
                full_blocks.append((y0, text))
            elif x1 <= mid_x + tolerance:
                left_col.append((y0, text))
            else:
                right_col.append((y0, text))

        is_two_col = bool(left_col) and bool(right_col)

        if is_two_col:
            col_start_y = min(b[0] for b in left_col + right_col)
            top_full = sorted(
                [(y0, t) for y0, t in full_blocks if y0 <= col_start_y],
                key=lambda b: b[0],
            )
            bottom_full = sorted(
                [(y0, t) for y0, t in full_blocks if y0 > col_start_y],
                key=lambda b: b[0],
            )
            left_sorted = sorted(left_col, key=lambda b: b[0])
            right_sorted = sorted(right_col, key=lambda b: b[0])
            ordered = top_full + left_sorted + right_sorted + bottom_full
        else:
            ordered = sorted(full_blocks + left_col + right_col, key=lambda b: b[0])

        return "\n".join(t for _, t in ordered)

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
            text = self._extract_page_text(page)

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
        提取 PDF 元数据。
        策略：从首两页文本中找 DOI → CrossRef 查询标题和作者。
        找不到 DOI 或 CrossRef 无结果时：标题留空（由调用方用文件名填充），作者留空。
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
            doc.close()

            # 提取前两页文本用于 DOI 搜索和语言判断
            pages = self._extract_pages(file_path)
            first_page_text = pages[0][1] if pages else ""
            second_page_text = pages[1][1] if len(pages) > 1 else ""
            search_text = first_page_text + "\n" + second_page_text

            # 语言判断
            chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", search_text))
            if len(search_text) > 0 and chinese_chars / len(search_text) > 0.15:
                metadata["language"] = "zh"
            else:
                metadata["language"] = "en"

            # 从文本或 PDF 元数据中提取 DOI
            doi = self._extract_doi(search_text, pdf_meta)
            metadata["doi"] = doi

            # 有 DOI 则查询元数据（CrossRef → doi.org 页面爬取）
            if doi:
                print(f"[PDFParser] 发现 DOI: {doi}，正在查询元数据 …")
                result = self._query_doi_metadata(doi)
                if result.get("title"):
                    metadata["title"] = result["title"]
                if result.get("authors"):
                    metadata["authors"] = result["authors"]
            else:
                print("[PDFParser] 未找到 DOI，标题和作者将使用默认值")

        except Exception as e:
            print(f"[PDFParser] 提取元数据失败: {e}")

        return metadata

    # ── 公开：解析并分块 ───────────────────────────────────────────────────────

    def parse_and_chunk(
        self, file_path: str, chunk_size: int = 800, chunk_overlap: int = 250
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

            paragraphs = re.split(r"\n\s*\n|\n(?=[A-Z][a-z])", all_text)
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
