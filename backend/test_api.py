"""验证豆包大模型（火山方舟）API 是否可用"""
import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("ARK_API_KEY", "")
chat_model = os.getenv("ARK_CHAT_MODEL", "doubao-seed-2-0-lite-260215")
embed_model = os.getenv("ARK_EMBED_MODEL", "doubao-embedding-large-text-250515")

print("=" * 50)
print("🔍 豆包大模型（火山方舟）API 验证")
print("=" * 50)

if not api_key or api_key == "your_ark_api_key_here":
    print("❌ 请先在 .env 文件中填入 ARK_API_KEY")
    exit(1)

print(f"🔑 API Key: {api_key[:8]}...{api_key[-4:]}")
print(f"💬 对话模型: {chat_model}")
print(f"📐 Embedding 模型: {embed_model}")

from openai import OpenAI

client = OpenAI(
    api_key=api_key,
    base_url=os.getenv("ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3"),
)

# 测试 1: 文本生成
print("\n--- 测试文本生成 ---")
try:
    response = client.chat.completions.create(
        model=chat_model,
        messages=[
            {"role": "system", "content": "你是一位科研助理。"},
            {"role": "user", "content": "请用一句话介绍锂离子电池的工作原理。"},
        ],
        temperature=0.3,
        max_tokens=200,
    )
    text = response.choices[0].message.content
    print(f"✅ 成功！回复: {text.strip()}")
    print(f"   模型: {response.model}")
    print(f"   Token 用量: {response.usage.total_tokens}")
except Exception as e:
    print(f"❌ 文本生成失败: {e}")

# 测试 2: Embedding（使用多模态接口）
print("\n--- 测试 Embedding ---")
import httpx
embed_url = f"{os.getenv('ARK_BASE_URL', 'https://ark.cn-beijing.volces.com/api/v3')}/embeddings/multimodal"
embed_headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
try:
    payload = {
        "model": embed_model,
        "input": [{"type": "text", "text": "锂离子电池正极材料"}],
    }
    resp = httpx.post(embed_url, json=payload, headers=embed_headers, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    embed_data = data["data"]
    vec = embed_data["embedding"] if isinstance(embed_data, dict) else embed_data[0]["embedding"]
    print(f"✅ 成功！向量维度: {len(vec)}, 前3个值: {vec[:3]}")
    print(f"   模型: {data.get('model', embed_model)}")
except Exception as e:
    print(f"❌ Embedding 失败: {e}")

# 测试 3: 批量 Embedding
print("\n--- 测试批量 Embedding ---")
try:
    texts = ["固态电解质", "负极材料", "电池循环性能"]
    results = []
    for t in texts:
        payload = {
            "model": embed_model,
            "input": [{"type": "text", "text": t}],
        }
        resp = httpx.post(embed_url, json=payload, headers=embed_headers, timeout=60)
        resp.raise_for_status()
        rdata = resp.json()["data"]
        vec = rdata["embedding"] if isinstance(rdata, dict) else rdata[0]["embedding"]
        results.append(vec)
    print(f"✅ 成功！返回 {len(results)} 个向量")
    for i, vec in enumerate(results):
        print(f"   [{i}] 维度: {len(vec)}")
except Exception as e:
    print(f"❌ 批量 Embedding 失败: {e}")

print("\n" + "=" * 50)
print("🎉 验证完成！")
