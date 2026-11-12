import re

def fetch_weather():
    global LOCATION_ID
    # 1. 彻底清洗 LOCATION_ID，过滤掉可能混入的空格、双引号、单引号、换行符
    raw_id = os.getenv("LOCATION_ID", "101010100")
    clean_id = re.sub(r'[^0-9]', '', str(raw_id))  # 只保留纯数字
    
    print(f"==========================================")
    print(f"🔍 原始环境变量 LOCATION_ID: repr={repr(raw_id)}")
    print(f"🔍 清洗后的数字 ID: '{clean_id}'")
    print(f"==========================================")

    # 2. 精准匹配（只要包含 101070211 就直接指定高新园区）
    if "101070211" in clean_id:
        city_name = "大连 · 高新园区"
        print(f"🎯 强制命中高新园区: {city_name}")
    elif clean_id in CITY_MAP:
        city_name = CITY_MAP[clean_id]
        print(f"📍 本地精准映射命中城市: {city_name}")
    else:
        # 如果不是内置城市，尝试在线请求并打印完整的返回信息
        city_name = "未知区域"
        try:
            geo_url = f"https://geoapi.qweather.com/v2/city/lookup?location={clean_id}&key={QWEATHER_KEY}"
            resp = requests.get(geo_url, timeout=10)
            print(f"📡 请求 Geo 接口状态: {resp.status_code}, 内容: {resp.text}")
            r_geo = resp.json()
            if r_geo.get("code") == "200" and r_geo.get("location"):
                loc = r_geo["location"][0]
                adm2 = loc.get("adm2", "")
                district = loc.get("name", "")
                city_name = f"{adm2} · {district}" if (adm2 and adm2 != district) else district
            else:
                city_name = f"城市ID:{clean_id}"
        except Exception as e:
            print(f"❌ Geo 查询失败: {e}")
            city_name = f"城市ID:{clean_id}"

    # 3. 获取天气数据（使用清洗干净的 clean_id）
    now_url = f"https://m65u9yw236.re.qweatherapi.com/v7/weather/now?location={clean_id}&key={QWEATHER_KEY}"
    daily_url = f"https://m65u9yw236.re.qweatherapi.com/v7/weather/3d?location={clean_id}&key={QWEATHER_KEY}"
    
    now_data = {}
    daily_data = []

    try:
        r_now = requests.get(now_url, timeout=10).json()
        r_daily = requests.get(daily_url, timeout=10).json()

        if r_now.get("code") == "200":
            now_data = r_now.get("now", {})
            print(f"✅ 实时天气获取成功: 当前温度 {now_data.get('temp')}℃, 天气 {now_data.get('text')}")
        else:
            print(f"❌ 实时天气接口异常: {r_now}")

        if r_daily.get("code") == "200":
            daily_data = r_daily.get("daily", [])
            print("✅ 三天天气预报获取成功")
        else:
            print(f"❌ 预报天气接口异常: {r_daily}")

    except Exception as e:
        print(f"❌ API 网络请求异常: {e}")

    if not now_data:
        now_data = {"temp": "24", "text": "晴", "humidity": "42", "windScale": "2", "feelsLike": "23"}
    if not daily_data:
        daily_data = [
            {"fxDate": datetime.now().strftime("%Y-%m-%d"), "textDay": "晴", "tempMax": "27", "tempMin": "16", "sunrise": "05:08", "sunset": "19:28"},
            {"fxDate": "未来", "textDay": "多云", "tempMax": "25", "tempMin": "15"},
            {"fxDate": "未来", "textDay": "小雨", "tempMax": "21", "tempMin": "14"}
        ]
        
    return now_data, daily_data, city_name
