import os
import re
from typing import List, Dict, Optional

import fitz  # PyMuPDF


class PDFParser:
    """PDF 解析与分块服务"""

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

            # 从 PDF 元数据中提取
            pdf_meta = doc.metadata
            if pdf_meta:
                metadata["title"] = pdf_meta.get("title", "") or ""
                metadata["authors"] = pdf_meta.get("author", "") or ""

            # 从首页文本中提取
            if len(doc) > 0:
                first_page_text = doc[0].get_text("text")

                # 如果元数据中没有标题，尝试从首页提取
                if not metadata["title"]:
                    lines = [l.strip() for l in first_page_text.split("\n") if l.strip()]
                    if lines:
                        # 取首页第一个较长的行作为标题
                        for line in lines[:5]:
                            if len(line) > 10:
                                metadata["title"] = line[:200]
                                break

                # 尝试提取摘要
                abstract_match = re.search(
                    r"(?:Abstract|摘\s*要)[:\s]*\n?(.*?)(?:\n\s*(?:Keywords|关键词|Introduction|1\s|1\.))",
                    first_page_text,
                    re.DOTALL | re.IGNORECASE,
                )
                if abstract_match:
                    metadata["abstract"] = abstract_match.group(1).strip()[:2000]

                # 简单语言检测
                chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", first_page_text))
                total_chars = len(first_page_text)
                if total_chars > 0 and chinese_chars / total_chars > 0.3:
                    metadata["language"] = "zh"
                else:
                    metadata["language"] = "en"

            doc.close()
        except Exception as e:
            print(f"[PDFParser] 提取元数据失败: {e}")

        return metadata

    def parse_and_chunk(
        self, file_path: str, chunk_size: int = 800, chunk_overlap: int = 100
    ) -> List[dict]:
        """
        使用 PyMuPDF 逐页提取文本，按段落边界进行语义分块。

        每个 chunk 包含：content, page_number, chunk_index, char_start, char_end
        过滤掉长度小于 50 字符的无效块。
        """
        chunks = []
        try:
            doc = fitz.open(file_path)
            full_text_parts = []  # (page_number, text)

            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text("text")
                if text.strip():
                    full_text_parts.append((page_num + 1, text))

            doc.close()

            # 将所有文本合并，记录每个字符对应的页码
            all_text = ""
            char_page_map = []  # 每个字符对应的页码

            for page_num, text in full_text_parts:
                start = len(all_text)
                all_text += text
                char_page_map.extend([page_num] * len(text))

            if not all_text.strip():
                return []

            # 按段落进行分块
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
                    # 保存当前块
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

                    # 重叠处理
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

            # 保存最后一个块
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

    def _get_page_for_position(self, char_page_map: list, position: int) -> int:
        """根据字符位置获取对应页码"""
        if not char_page_map:
            return 1
        idx = min(position, len(char_page_map) - 1)
        idx = max(0, idx)
        return char_page_map[idx]
