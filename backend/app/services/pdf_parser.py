import os
import re
from typing import List, Optional

import fitz  # PyMuPDF

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


class PDFParser:
    """PDF 解析与分块服务，支持文本版和扫描版 PDF"""

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
            "page_count": 0,
            "language": "unknown",
            "abstract": "",
        }

        try:
            doc = fitz.open(file_path)
            metadata["page_count"] = len(doc)

            pdf_meta = doc.metadata
            if pdf_meta:
                metadata["title"] = pdf_meta.get("title", "") or ""
                metadata["authors"] = pdf_meta.get("author", "") or ""
            doc.close()

            # 用统一提取（含 OCR 回退）获取首页文本
            pages = self._extract_pages(file_path)
            first_page_text = pages[0][1] if pages else ""

            if not metadata["title"]:
                lines = [l.strip() for l in first_page_text.split("\n") if l.strip()]
                for line in lines[:5]:
                    if len(line) > 10:
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
