import os
import requests

# 1. 打印基础环境信息
key = os.getenv("QWEATHER_KEY", "").strip()
host = os.getenv("QWEATHER_HOST", "").strip().replace("https://", "").replace("http://", "").strip("/")
loc = os.getenv("LOCATION_ID", "101010100").strip()

print("=" * 50)
print(f"1. 环境变量排查:")
print(f"   QWEATHER_HOST : '{host}' (长度: {len(host)})")
print(f"   QWEATHER_KEY  : '{key[:4]}****{key[-4:] if len(key)>8 else ''}' (长度: {len(key)})")
print(f"   LOCATION_ID   : '{loc}'")
print("=" * 50)

if not host or not key:
    print("❌ 致命错误: HOST 或 KEY 存在空值，请检查 GitHub Settings -> Secrets / Variables！")
    exit(1)

# 2. 模拟请求
test_url = f"https://{host}/v7/weather/now?location={loc}&key={key}"
print(f"2. 开始发起真实请求: https://{host}/v7/weather/now?location={loc}&key=***")

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    # 显式告知服务器不要返回 brotli/gzip 压缩，防止 Python requests 解包失败
    "Accept-Encoding": "identity" 
}

try:
    resp = requests.get(test_url, headers=headers, timeout=15)
    print(f"3. HTTP 状态码: {resp.status_code}")
    print(f"4. 响应原文 (前 500 字符):")
    print(resp.text[:500])
    
    data = resp.json()
    code = data.get("code")
    print(f"5. 和风 API Code: {code}")
    
    if code == "200":
        print(f"🎉 成功拿到天气数据: 当前气温 {data['now']['temp']}℃, 天气: {data['now']['text']}")
    elif code == "401":
        print("❌ 错误 401 (UNAUTHORIZED): KEY 不正确，或该 KEY 没有绑定当前项目的权限。")
    elif code == "402":
        print("❌ 错误 402 (QUOTA_EXCEEDED): 免费额度耗尽，或请求频率超限。")
    elif code == "403":
        print("❌ 错误 403 (FORBIDDEN): HOST 与 KEY 不匹配！专属 Host 必须配合对应的项目凭证。")
    elif code == "404":
        print("❌ 错误 404 (NOT_FOUND): 城市 ID 不存在，或 URL 路由写错。")
    else:
        print(f"❌ 其他错误 Code: {code}")

except requests.exceptions.ConnectionError as e:
    print(f"❌ 网络/域名连接失败: 无法解析域名 '{host}'，请确认在控制台复制的是否为正确的 API Host。")
    print(f"   详情: {e}")
except Exception as e:
    print(f"❌ 抛出未预期的异常: {type(e).__name__} -> {e}")
print("=" * 50)
