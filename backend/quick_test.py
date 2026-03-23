"""快速测试后端所有 API 接口"""
import httpx

BASE = "http://127.0.0.1:5001/api"


def main():
    print("=" * 50)
    print("🧪 后端 API 接口集成测试")
    print("=" * 50)

    # 1. 注册
    r = httpx.post(f"{BASE}/auth/register", json={
        "username": "testuser", "email": "test@test.com", "password": "123456"
    })
    print(f"[注册] {r.status_code} - {r.json()['message']}")

    # 2. 登录
    r = httpx.post(f"{BASE}/auth/login", json={
        "email": "test@test.com", "password": "123456"
    })
    print(f"[登录] {r.status_code} - {r.json()['message']}")
    token = r.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 3. 获取当前用户
    r = httpx.get(f"{BASE}/auth/me", headers=headers)
    user = r.json()["data"]
    print(f"[用户] {r.status_code} - {user['username']} ({user['email']})")

    # 4. 文献列表（空）
    r = httpx.get(f"{BASE}/documents", headers=headers)
    print(f"[文献列表] {r.status_code} - 共 {r.json()['data']['total']} 篇")

    # 5. 会话列表（空）
    r = httpx.get(f"{BASE}/chat/conversations", headers=headers)
    convs = r.json()["data"]["conversations"]
    print(f"[会话列表] {r.status_code} - 共 {len(convs)} 个")

    # 6. 工具列表
    r = httpx.get(f"{BASE}/tools/list", headers=headers)
    tools = r.json()["data"]["tools"]
    print(f"[工具列表] {r.status_code} - {[t['name'] for t in tools]}")

    # 7. 翻译工具
    r = httpx.post(f"{BASE}/tools/translate", headers=headers, json={
        "text": "Lithium-ion batteries are widely used in energy storage.",
        "target_language": "中文",
    }, timeout=30)
    print(f"[翻译] {r.status_code} - {r.json()['data'].get('translated_text', r.json().get('message', ''))[:80]}")

    # 8. 创建会话
    r = httpx.post(f"{BASE}/chat/conversations", headers=headers, json={"title": "测试会话"})
    conv_id = r.json()["data"]["id"]
    print(f"[创建会话] {r.status_code} - ID: {conv_id}")

    # 9. 删除会话
    r = httpx.delete(f"{BASE}/chat/conversations/{conv_id}", headers=headers)
    print(f"[删除会话] {r.status_code} - {r.json()['message']}")

    # 10. 登出
    r = httpx.post(f"{BASE}/auth/logout", headers=headers)
    print(f"[登出] {r.status_code} - {r.json()['message']}")

    print("\n" + "=" * 50)
    print("🎉 所有接口测试完成！")
    print("=" * 50)


if __name__ == "__main__":
    main()
