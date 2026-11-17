import os
import requests

host = os.getenv("QWEATHER_HOST", "").strip().replace("https://", "").strip("/")
key = os.getenv("QWEATHER_KEY", "").strip()
loc = os.getenv("LOCATION_ID", "101070211").strip()

print("=" * 60)
print(f"【1. 参数确认】")
print(f"HOST: {host}")
print(f"KEY 长度: {len(key)}")
print(f"LOCATION_ID: {loc}")
print("=" * 60)

# 测试两种和风官方允许的调用方式
# 方式 A：URL Query 传参
url_a = f"https://{host}/v7/weather/now?location={loc}&key={key}"
print(f"【2. 测试方式 A: URL 传参】")
try:
    r_a = requests.get(url_a, headers={"Accept-Encoding": "identity"}, timeout=10)
    print(f"HTTP Status: {r_a.status_code}")
    print(f"返回内容: {r_a.text}")
except Exception as e:
    print(f"请求失败: {e}")

print("-" * 60)

# 方式 B：Header Header 传参（和风最新规范，防特殊字符拦截）
url_b = f"https://{host}/v7/weather/now?location={loc}"
print(f"【3. 测试方式 B: 请求头 Header 传参】")
try:
    r_b = requests.get(url_b, headers={"X-QW-Api-Key": key, "Accept-Encoding": "identity"}, timeout=10)
    print(f"HTTP Status: {r_b.status_code}")
    print(f"返回内容: {r_b.text}")
except Exception as e:
    print(f"请求失败: {e}")

print("=" * 60)
