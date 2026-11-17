import os
import re
import requests
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

# ==================== 配置区 ====================
WIDTH = 758      # Kobo Glo 屏幕宽度
HEIGHT = 1024    # Kobo Glo 屏幕高度

QWEATHER_KEY = os.getenv("QWEATHER_KEY", "")
LOCATION_ID = os.getenv("LOCATION_ID", "101010100")

CITY_MAP = {
    "101010100": "北京",
    "101020100": "上海",
    "101280101": "广州",
    "101280601": "深圳",
    "101070211": "大连 · 高新园区"
}

# ==================== 数据获取 ====================
def fetch_weather():
    global LOCATION_ID
    raw_id = os.getenv("LOCATION_ID", "101010100")
    clean_id = re.sub(r'[^0-9]', '', str(raw_id))
    
    print(f"==========================================")
    print(f"🔍 原始环境变量 LOCATION_ID: repr={repr(raw_id)}")
    print(f"🔍 清洗后的数字 ID: '{clean_id}'")
    print(f"==========================================")

    if "101070211" in clean_id:
        city_name = "大连 · 高新园区"
    elif clean_id in CITY_MAP:
        city_name = CITY_MAP[clean_id]
    else:
        city_name = "未知区域"
        try:
            geo_url = f"https://geoapi.qweather.com/v2/city/lookup?location={clean_id}&key={QWEATHER_KEY}"
            resp = requests.get(geo_url, timeout=10)
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

    now_url = f"https://devapi.qweather.com/v7/weather/now?location={clean_id}&key={QWEATHER_KEY}"
    daily_url = f"https://devapi.qweather.com/v7/weather/3d?location={clean_id}&key={QWEATHER_KEY}"
    
    now_data = {}
    daily_data = []

    try:
        r_now = requests.get(now_url, timeout=10).json()
        r_daily = requests.get(daily_url, timeout=10).json()

        if r_now.get("code") == "200":
            now_data = r_now.get("now", {})
            print(f"✅ 实时天气获取成功: 当前温度 {now_data.get('temp')}℃, 天气 {now_data.get('text')}")
        if r_daily.get("code") == "200":
            daily_data = r_daily.get("daily", [])
            print("✅ 三天天气预报获取成功")
    except Exception as e:
        print(f"❌ API 网络请求异常: {e}")

    if not now_data:
        now_data = {"temp": "--", "text": "晴", "humidity": "--", "windScale": "-", "feelsLike": "--"}
    if not daily_data:
        daily_data = [
            {"fxDate": datetime.now().strftime("%Y-%m-%d"), "textDay": "晴", "tempMax": "--", "tempMin": "--", "sunrise": "06:00", "sunset": "18:00"},
            {"fxDate": "未来", "textDay": "多云", "tempMax": "--", "tempMin": "--"},
            {"fxDate": "未来", "textDay": "晴", "tempMax": "--", "tempMin": "--"}
        ]
        
    return now_data, daily_data, city_name

# 获取每日一言（适合床头醒来查看）
def fetch_hitokoto():
    try:
        r = requests.get("https://v1.hitokoto.cn/?c=d&c=i&c=k", timeout=5).json()
        text = r.get("hitokoto", "每一个清晨，都是新生活的开始。")
        author = r.get("from", "生活")
        return text, author
    except Exception:
        return "保持热爱，奔赴山海。", "生活"

# ==================== 字体加载辅助 ====================
def load_font(size, bold=False):
    # GitHub Actions ubuntu-latest 环境自带 fonts-noto-cjk
    font_paths = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc" if bold else "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc" if bold else "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "msyh.ttc", "simhei.ttf" # 本地测试回退
    ]
    for p in font_paths:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()

# ==================== 核心绘图逻辑 ====================
def generate_kobo_image():
    now_data, daily_data, city_name = fetch_weather()
    quote, quote_from = fetch_hitokoto()
    today = daily_data[0] if daily_data else {}

    # 1. 创建纯黑白/灰阶画布 (灰度模式 "L")
    img = Image.new("L", (WIDTH, HEIGHT), 255) # 纯白底
    draw = ImageDraw.Draw(img)

    # 2. 字体准备
    font_city = load_font(26, bold=True)
    font_date = load_font(24)
    font_temp_giant = load_font(130, bold=True)
    font_weather_title = load_font(42, bold=True)
    font_sub_info = load_font(24)
    font_table_head = load_font(22, bold=True)
    font_table_text = load_font(20)
    font_quote = load_font(22)
    font_quote_author = load_font(18)

    # 3. 顶部 Header 区 (Y: 30 ~ 110)
    now = datetime.now()
    weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    date_str = f"{now.strftime('%Y年%m月%d日')}  {weekdays[now.weekday()]}"
    
    draw.text((40, 40), f"📍 {city_name}", fill=0, font=font_city)
    draw.text((40, 80), date_str, fill=80, font=font_date)
    draw.text((WIDTH - 210, 80), f"更新于 {now.strftime('%H:%M')}", fill=120, font=font_date)

    # 分割线
    draw.line((40, 125, WIDTH - 40, 125), fill=0, width=3)

    # 4. 实时核心天气区 (Y: 150 ~ 380)
    temp_str = str(now_data.get("temp", "--"))
    draw.text((40, 140), temp_str, fill=0, font=font_temp_giant)
    draw.text((40 + len(temp_str) * 75 + 10, 150), "℃", fill=0, font=font_weather_title)

    weather_text = now_data.get("text", "晴")
    draw.text((360, 160), weather_text, fill=0, font=font_weather_title)
    
    # 辅助小指标（体感、湿度、风力）
    feels = now_data.get("feelsLike", "--")
    humi = now_data.get("humidity", "--")
    wind = now_data.get("windScale", "-")
    sub_detail = f"体感 {feels}℃   |   相对湿度 {humi}%   |   风力 {wind}级"
    draw.text((360, 225), sub_detail, fill=70, font=font_sub_info)

    # 今日高低温范围 + 日出日落
    temp_range = f"今日最高 {today.get('tempMax', '--')}℃  /  最低 {today.get('tempMin', '--')}℃"
    draw.text((360, 265), temp_range, fill=0, font=font_sub_info)

    sun_info = f"🌅 日出 {today.get('sunrise', '--')}    🌇 日落 {today.get('sunset', '--')}"
    draw.text((40, 320), sun_info, fill=60, font=font_sub_info)

    # 细分割线
    draw.line((40, 370, WIDTH - 40, 370), fill=180, width=1)

    # 5. 三天预报卡片区 (Y: 400 ~ 640)
    draw.text((40, 400), "📋 近期天气预报", fill=0, font=font_table_head)

    card_y = 440
    card_w = (WIDTH - 80 - 20) // 3
    card_h = 160

    day_labels = ["今天", "明天", "后天"]
    for i in range(min(3, len(daily_data))):
        d = daily_data[i]
        x1 = 40 + i * (card_w + 10)
        x2 = x1 + card_w
        
        # 黑色/灰色细边框卡片（非常适合黑白墨水屏）
        draw.rounded_rectangle((x1, card_y, x2, card_y + card_h), radius=8, outline=0, width=2)
        
        # 标签头
        draw.text((x1 + 15, card_y + 15), day_labels[i], fill=0, font=font_table_head)
        draw.text((x1 + 15, card_y + 55), d.get("textDay", "晴"), fill=60, font=font_table_text)
        draw.text((x1 + 15, card_y + 90), f"{d.get('tempMin', '--')}℃ ~ {d.get('tempMax', '--')}℃", fill=0, font=font_table_head)

    # 细分割线
    draw.line((40, 660, WIDTH - 40, 660), fill=180, width=1)

    # 6. 床头格言/每日一言区 (Y: 700 ~ 920)
    draw.text((40, 700), "💬 朝暮寄语", fill=0, font=font_table_head)
    
    # 自动折行处理
    def wrap_text(text, limit=20):
        return [text[i:i+limit] for i in range(0, len(text), limit)]
    
    quote_lines = wrap_text(quote, 22)
    q_y = 740
    for line in quote_lines:
        draw.text((40, q_y), f"“ {line}" if q_y == 740 else f"  {line}", fill=40, font=font_quote)
        q_y += 35
    draw.text((WIDTH - 240, q_y + 10), f"—— 《{quote_from}》", fill=100, font=font_quote_author)

    # 7. 底部极简 Footer (Y: 960)
    draw.line((40, 960, WIDTH - 40, 960), fill=210, width=1)
    draw.text((WIDTH // 2 - 120, 980), "E-Ink Dashboard for Kobo Glo", fill=150, font=font_quote_author)

    # 8. 保存与归档
    os.makedirs("archive", exist_ok=True)
    archive_path = f"archive/{now.strftime('%Y%m%d_%H%M')}.png"
    
    # 纯 8-bit 黑白 PNG 导出（极大减小文件体积，Kobo 渲染几乎秒加载）
    img.save("latest.png", format="PNG", optimize=True)
    img.save(archive_path, format="PNG", optimize=True)
    print(f"🎉 成功生成适合 Kobo Glo (758x1024) 的黑白看板图片: latest.png 和 {archive_path}")

if __name__ == "__main__":
    generate_kobo_image()
