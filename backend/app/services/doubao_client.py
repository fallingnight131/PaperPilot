import time
import httpx
from typing import List, Optional, Generator

from openai import OpenAI
from ..config import Config


class DoubaoClient:
    """豆包大模型（火山方舟）统一客户端"""

    def __init__(self):
        api_key = Config.ARK_API_KEY
        if not api_key or api_key == "your_ark_api_key_here":
            raise ValueError("ARK_API_KEY 环境变量未设置，请在 .env 中填入火山方舟 API Key")

        self._api_key = api_key
        self._base_url = Config.ARK_BASE_URL
        self._client = OpenAI(api_key=api_key, base_url=self._base_url)

        # 直接使用模型名称，无需创建接入点
        self._chat_model = Config.ARK_CHAT_MODEL
        self._embed_model = Config.ARK_EMBED_MODEL

    def _call_multimodal_embedding(self, texts: List[str]) -> List[List[float]]:
        """
        调用火山方舟多模态 Embedding 接口 /embeddings/multimodal。
        doubao-embedding-vision 系列模型不支持标准 /embeddings 接口，
        需要使用多模态接口并以 text 类型输入。
        """
        url = f"{self._base_url}/embeddings/multimodal"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        all_embeddings = []
        for text in texts:
            payload = {
                "model": self._embed_model,
                "input": [{"type": "text", "text": text}],
            }
            resp = httpx.post(url, json=payload, headers=headers, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            # 多模态接口返回格式: {"data": {"embedding": [...]}} 或 {"data": [{"embedding": [...]}]}
            embed_data = data["data"]
            if isinstance(embed_data, list):
                all_embeddings.append(embed_data[0]["embedding"])
            else:
                all_embeddings.append(embed_data["embedding"])

        return all_embeddings

    def get_embedding(self, text: str) -> List[float]:
        """获取单条文本的向量，自动截断到 8000 字符。"""
        if not text or not text.strip():
            return []
        truncated = text[:8000]
        try:
            result = self._call_multimodal_embedding([truncated])
            return result[0]
        except Exception as e:
            print(f"[DoubaoClient] Embedding 错误: {e}")
            raise

    def get_query_embedding(self, text: str) -> List[float]:
        """获取查询文本的向量"""
        return self.get_embedding(text)

    def generate(self, prompt: str, system_prompt: Optional[str] = None,
                 temperature: float = 0.3, max_tokens: int = 4096) -> str:
        """
        调用豆包对话模型生成文本。
        支持传入 system_prompt 和 max_tokens。
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            response = self._client.chat.completions.create(
                model=self._chat_model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"[DoubaoClient] 生成错误: {e}")
            raise

    def generate_stream(self, prompt: str, system_prompt: Optional[str] = None,
                        temperature: float = 0.3) -> Generator:
        """流式输出版本，用于实时返回问答结果"""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            response = self._client.chat.completions.create(
                model=self._chat_model,
                messages=messages,
                temperature=temperature,
                max_tokens=4096,
                stream=True,
            )
            for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            print(f"[DoubaoClient] 流式生成错误: {e}")
            raise

    def batch_embed(self, texts: List[str], batch_size: int = 20) -> List[List[float]]:
        """
        批量获取 embedding。
        每批最多 batch_size 个文本，逐条调用多模态接口。
        """
        all_embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i: i + batch_size]
            processed = [t[:8000] if t and t.strip() else " " for t in batch]
            try:
                embeddings = self._call_multimodal_embedding(processed)
                all_embeddings.extend(embeddings)
            except Exception as e:
                print(f"[DoubaoClient] 批量 Embedding 错误 (batch {i}): {e}")
                raise
            if i + batch_size < len(texts):
                time.sleep(0.3)
        return all_embeddings
