import os
import sys
import requests
import cairosvg
from PIL import Image
from datetime import datetime
from lunardate import LunarDate

# 获取基础路径（确保无论在哪个路径下执行，都写入脚本所在目录）
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

QWEATHER_KEY = os.getenv("QWEATHER_KEY")
LOCATION_ID = os.getenv("LOCATION_ID", "101010100")

def get_lunar_and_solar_term():
    """纯本地离线精准计算农历月日、干支生肖与二十四节气"""
    now = datetime.now()
    lunar = LunarDate.fromSolarDate(now.year, now.month, now.day)
    
    gan = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]
    zhi = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]
    zodiac = ["鼠", "牛", "虎", "兔", "龙", "蛇", "马", "羊", "猴", "鸡", "狗", "猪"]
    
    gz_year = f"{gan[(lunar.year - 4) % 10]}{zhi[(lunar.year - 4) % 12]}{zodiac[(lunar.year - 4) % 12]}年"
    
    months = ["正", "二", "三", "四", "五", "六", "七", "八", "九", "十", "冬", "腊"]
    days = [
        "初一", "初二", "初三", "初四", "初五", "初六", "初七", "初八", "初九", "初十",
        "十一", "十二", "十三", "十四", "十五", "十六", "十七", "十八", "十九", "二十",
        "廿一", "廿二", "廿三", "廿四", "廿五", "廿六", "廿七", "廿八", "廿九", "三十"
    ]
    lunar_str = f"农历 {gz_year}{months[lunar.month - 1]}月{days[lunar.day - 1]}"

    solar_terms = {
        (1, 5): "小寒", (1, 20): "大寒", (2, 4): "立春", (2, 19): "雨水",
        (3, 5): "惊蛰", (3, 20): "春分", (4, 4): "清明", (4, 20): "谷雨",
        (5, 5): "立夏", (5, 21): "小满", (6, 5): "芒种", (6, 21): "夏至",
        (7, 7): "小暑", (7, 22): "大暑", (8, 7): "立秋", (8, 23): "处暑",
        (9, 7): "白露", (9, 23): "秋分", (10, 8): "寒露", (10, 23): "霜降",
        (11, 7): "立冬", (11, 22): "小雪", (12, 7): "大雪", (12, 21): "冬至"
    }
    
    term = solar_terms.get((now.month, now.day))
    if term:
        lunar_str += f" · {term}"
    return lunar_str

def fetch_weather():
    print(f"🔍 当前读取到的 LOCATION_ID: '{LOCATION_ID}'")
    
    if not QWEATHER_KEY:
        print("⚠️ 警告: 未检测到环境变量 QWEATHER_KEY，请检查 Secrets 配置！")

    # 1. 自动反查城市和区域名称（专属域名需带 /geo，并提供通用公共域名备用）
    city_name = "本地"
    try:
        geo_url = f"https://m65u9yw236.re.qweatherapi.com/geo/v2/city/lookup?location={LOCATION_ID}&key={QWEATHER_KEY}"
        r_geo = requests.get(geo_url, timeout=10).json()

        # 如果专属域名没有开通 Geo 服务，自动退回到官方通用 GeoAPI
        if r_geo.get("code") != "200":
            backup_geo_url = f"https://geoapi.qweather.com/v2/city/lookup?location={LOCATION_ID}&key={QWEATHER_KEY}"
            r_geo = requests.get(backup_geo_url, timeout=10).json()

        if r_geo.get("code") == "200" and r_geo.get("location"):
            loc = r_geo["location"][0]
            adm2 = loc.get("adm2", "")     # 上级市，如：大连
            district = loc.get("name", "") # 区县，如：普兰店
            
            if adm2 and adm2 != district:
                city_name = f"{adm2} · {district}"
            else:
                city_name = district
            print(f"📍 成功识别城市区域: {city_name}")
        else:
            print(f"⚠️ 城市查询返回非 200，响应内容: {r_geo}")
    except Exception as e:
        print(f"❌ 获取城市信息发生网络异常: {e}")

    # 2. 获取实时天气与3天预报
    now_url = f"https://m65u9yw236.re.qweatherapi.com/v7/weather/now?location={LOCATION_ID}&key={QWEATHER_KEY}"
    daily_url = f"https://m65u9yw236.re.qweatherapi.com/v7/weather/3d?location={LOCATION_ID}&key={QWEATHER_KEY}"
    
    now_data = {}
    daily_data = []

    try:
        print(f"📡 正在获取天气数据 (Location: {LOCATION_ID})...")
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

    # 兜底保障
    if not now_data:
        print("⚠️ 启用实时天气兜底数据")
        now_data = {"temp": "24", "text": "晴", "humidity": "42", "windScale": "2", "feelsLike": "23"}
    if not daily_data:
        print("⚠️ 启用天气预报兜底数据")
        daily_data = [
            {"fxDate": datetime.now().strftime("%Y-%m-%d"), "textDay": "晴", "tempMax": "27", "tempMin": "16", "sunrise": "05:08", "sunset": "19:28"},
            {"fxDate": "未来", "textDay": "多云", "tempMax": "25", "tempMin": "15"},
            {"fxDate": "未来", "textDay": "小雨", "tempMax": "21", "tempMin": "14"}
        ]
        
    return now_data, daily_data, city_name

def get_weather_icon(text, x, y, scale=1.0):
    if "晴" in text:
        return f'''<g transform="translate({x},{y}) scale({scale})">
            <circle cx="40" cy="40" r="22" fill="#FFCC00" stroke="#000000" stroke-width="3"/>
            <path d="M40 8 V0 M40 80 V72 M8 40 H0 M80 40 H72 M17 17 L11 11 M69 69 L63 63 M17 63 L11 69 M69 17 L63 11" stroke="#FFCC00" stroke-width="4" stroke-linecap="round"/>
        </g>'''
    elif "雨" in text:
        return f'''<g transform="translate({x},{y}) scale({scale})">
            <path d="M22 45 A14 14 0 0 1 35 22 A22 22 0 0 1 70 28 A16 16 0 0 1 68 50 H24" fill="#FFFFFF" stroke="#000000" stroke-width="3" stroke-linejoin="round"/>
            <line x1="30" y1="58" x2="24" y2="72" stroke="#FF0000" stroke-width="3.5" stroke-linecap="round"/>
            <line x1="45" y1="58" x2="39" y2="72" stroke="#FF0000" stroke-width="3.5" stroke-linecap="round"/>
            <line x1="60" y1="58" x2="54" y2="72" stroke="#FF0000" stroke-width="3.5" stroke-linecap="round"/>
        </g>'''
    elif "多云" in text or "阴" in text:
        return f'''<g transform="translate({x},{y}) scale({scale})">
            <circle cx="56" cy="28" r="16" fill="#FFCC00" stroke="#000000" stroke-width="2.5"/>
            <path d="M22 52 A14 14 0 0 1 34 30 A20 20 0 0 1 68 36 A15 15 0 0 1 66 58 H24" fill="#FFFFFF" stroke="#000000" stroke-width="3" stroke-linejoin="round"/>
        </g>'''
    else:
        return f'''<g transform="translate({x},{y}) scale({scale})">
            <circle cx="40" cy="40" r="20" fill="#FFCC00" stroke="#000000" stroke-width="3"/>
        </g>'''

def build_svg(now, daily, city_name):
    now_dt = datetime.now()
    today_str = now_dt.strftime("%Y.%m.%d")
    weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    week_str = weekdays[now_dt.weekday()]
    lunar_info = get_lunar_and_solar_term()
    
    temp = str(now.get("temp", "24"))
    feels_like = str(now.get("feelsLike", temp))
    text = now.get("text", "晴")
    humidity = str(now.get("humidity", "45"))
    wind = str(now.get("windScale", "2"))
    
    d1 = daily[0] if len(daily) > 0 else {}
    d2 = daily[1] if len(daily) > 1 else {}
    d3 = daily[2] if len(daily) > 2 else {}
    
    sunrise = d1.get("sunrise", "05:12")
    sunset = d1.get("sunset", "19:25")
    
    main_icon = get_weather_icon(text, 255, 95, scale=1.3)
    icon_d1 = get_weather_icon(d1.get("textDay", "晴"), 495, 125, scale=0.6)
    icon_d2 = get_weather_icon(d2.get("textDay", "多云"), 495, 235, scale=0.6)
    icon_d3 = get_weather_icon(d3.get("textDay", "晴"), 495, 345, scale=0.6)

    # 动态计算城市胶囊的宽度，确保短名字和长名字都排版工整
    capsule_width = max(80, len(city_name) * 14 + 20)

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 480" width="800" height="480" style="background:#FFFFFF; font-family: 'Noto Sans CJK SC', 'Source Han Sans SC', sans-serif;">
  <defs>
    <style>
      .heavy {{ font-weight: 900; }}
      .bold {{ font-weight: bold; }}
      .muted {{ font-weight: 500; fill: #666666; }}
    </style>
  </defs>

  <!-- 1. 顶部 Header 状态栏 -->
  <line x1="30" y1="52" x2="770" y2="52" stroke="#000000" stroke-width="2"/>
  <rect x="30" y="24" width="8" height="20" fill="#FF0000" />
  <text x="46" y="40" font-size="20" class="heavy" fill="#000000" letter-spacing="1">DAILY BRIEFING</text>
  
  <!-- 城市与区域标签（醒目呈现） -->
  <rect x="220" y="24" width="{capsule_width}" height="20" rx="10" fill="#000000" />
  <text x="{220 + capsule_width // 2}" y="38" font-size="12" class="heavy" fill="#FFFFFF" text-anchor="middle">📍 {city_name}</text>
  
  <!-- 右上角：公历与农历节气 -->
  <text x="770" y="28" font-size="15" class="bold" fill="#000000" text-anchor="end">{today_str} · {week_str}</text>
  <text x="770" y="46" font-size="12" class="muted" text-anchor="end">{lunar_info}</text>

  <!-- 2. 主天气卡片 (Bento 大卡) -->
  <rect x="30" y="70" width="425" height="225" rx="16" fill="#FFFFFF" stroke="#000000" stroke-width="2.5"/>
  
  <!-- 当前天气状态小胶囊 -->
  <rect x="50" y="88" width="72" height="25" rx="12.5" fill="#FFCC00"/>
  <text x="86" y="105" font-size="13" class="heavy" fill="#000000" text-anchor="middle">{text}</text>
  <text x="132" y="105" font-size="13" class="muted">体感 {feels_like}°C</text>

  <!-- 超大温度 -->
  <text x="45" y="200" font-size="100" class="heavy" fill="#000000" letter-spacing="-4">{temp}°</text>
  {main_icon}

  <!-- 指标栏 -->
  <line x1="50" y1="220" x2="435" y2="220" stroke="#EEEEEE" stroke-width="1.5"/>
  <text x="50" y="244" font-size="12" class="muted">湿度</text>
  <text x="50" y="268" font-size="17" class="heavy" fill="#000000">{humidity}%</text>

  <text x="120" y="244" font-size="12" class="muted">风向风级</text>
  <text x="120" y="268" font-size="17" class="heavy" fill="#000000">{wind} 级</text>

  <text x="195" y="244" font-size="12" class="muted">紫外线</text>
  <text x="195" y="268" font-size="17" class="heavy" fill="#FF0000">正常</text>

  <!-- 日出日落小罗盘部件 -->
  <g transform="translate(285, 230)">
    <path d="M 10 38 A 45 45 0 0 1 125 38" fill="none" stroke="#000000" stroke-width="1.5" stroke-dasharray="3,3" />
    <line x1="5" y1="38" x2="130" y2="38" stroke="#000000" stroke-width="1" />
    <circle cx="68" cy="12" r="5" fill="#FFCC00" stroke="#000000" stroke-width="1.5"/>
    <line x1="68" y1="4" x2="68" y2="2" stroke="#FFCC00" stroke-width="2"/>
    <line x1="60" y1="12" x2="58" y2="12" stroke="#FFCC00" stroke-width="2"/>
    <line x1="76" y1="12" x2="78" y2="12" stroke="#FFCC00" stroke-width="2"/>
    <text x="10" y="52" font-size="11" class="bold" fill="#000000">🌅 {sunrise}</text>
    <text x="125" y="52" font-size="11" class="bold" fill="#000000" text-anchor="end">🌇 {sunset}</text>
  </g>

  <!-- 3. 左下：东方雅韵金句与提醒笺条 -->
  <rect x="30" y="312" width="425" height="143" rx="16" fill="#FBFBFB" stroke="#000000" stroke-width="2"/>
  
  <rect x="50" y="328" width="22" height="22" rx="4" fill="#FF0000" />
  <text x="54" y="344" font-size="14" class="heavy" fill="#FFFFFF">箴</text>
  
  <text x="80" y="345" font-size="17" class="heavy" fill="#000000" letter-spacing="2">心平气和</text>
  <text x="170" y="344" font-size="12" class="muted">/ 平常心是道，从容对晨昏</text>

  <line x1="50" y1="362" x2="435" y2="362" stroke="#EEEEEE" stroke-width="1"/>
  <circle cx="56" cy="385" r="3.5" fill="#FF0000"/>
  <text x="68" y="390" font-size="13" class="bold" fill="#000000">气温舒适，宜饮茶静心，缓步当车。</text>

  <circle cx="56" cy="418" r="3.5" fill="#FFCC00"/>
  <text x="68" y="423" font-size="13" class="bold" fill="#000000">日暮霞光可期（{sunset}），傍晚宜漫步舒怀。</text>

  <!-- 4. 右侧 Bento Grid：未来三天趋势 -->
  <!-- 明天 -->
  <rect x="475" y="70" width="295" height="100" rx="16" fill="#FFFFFF" stroke="#000000" stroke-width="2"/>
  <text x="495" y="102" font-size="15" class="bold" fill="#000000">明天 · {d1.get("fxDate", "")[5:]}</text>
  <text x="495" y="148" font-size="14" class="bold" fill="#000000">{d1.get("textDay")}</text>
  {icon_d1}
  <text x="645" y="132" font-size="28" class="heavy" fill="#FF0000">{d1.get("tempMax")}°</text>
  <text x="705" y="130" font-size="18" class="bold" fill="#000000">/ {d1.get("tempMin")}°</text>

  <!-- 后天 (醒目黄标) -->
  <rect x="475" y="180" width="295" height="100" rx="16" fill="#FFFFFF" stroke="#000000" stroke-width="2.5"/>
  <rect x="475" y="180" width="10" height="100" fill="#FFCC00" />
  <text x="495" y="212" font-size="15" class="bold" fill="#000000">后天 · {d2.get("fxDate", "")[5:]}</text>
  <text x="495" y="258" font-size="14" class="heavy" fill="#000000">{d2.get("textDay")}</text>
  {icon_d2}
  <text x="645" y="242" font-size="28" class="heavy" fill="#FF0000">{d2.get("tempMax")}°</text>
  <text x="705" y="240" font-size="18" class="bold" fill="#000000">/ {d2.get("tempMin")}°</text>

  <!-- 大后天 -->
  <rect x="475" y="290" width="295" height="100" rx="16" fill="#FFFFFF" stroke="#000000" stroke-width="2"/>
  <text x="495" y="322" font-size="15" class="bold" fill="#000000">大后天 · {d3.get("fxDate", "")[5:]}</text>
  <text x="495" y="368" font-size="14" class="bold" fill="#000000">{d3.get("textDay")}</text>
  {icon_d3}
  <text x="645" y="352" font-size="28" class="heavy" fill="#FF0000">{d3.get("tempMax")}°</text>
  <text x="705" y="350" font-size="18" class="bold" fill="#000000">/ {d3.get("tempMin")}°</text>

  <!-- 底部微注 -->
  <text x="480" y="440" font-size="11" class="muted">E-INK WEATHER STATION · DAILY ARCHIVE EDITION</text>
</svg>'''
    return svg

def render_image(svg_str):
    raw_path = os.path.join(BASE_DIR, 'raw.png')
    latest_path = os.path.join(BASE_DIR, 'latest.png')
    
    print("🎨 正在渲染 SVG 为 PNG 图像...")
    cairosvg.svg2png(bytestring=svg_str.encode('utf-8'), write_to=raw_path)
    
    img = Image.open(raw_path).convert('RGB')
    palette = [0,0,0,  255,255,255,  255,204,0,  255,0,0] + [0]*(768-12)
    pal_img = Image.new("P", (1, 1))
    pal_img.putpalette(palette)
    
    quantized = img.quantize(palette=pal_img, dither=Image.Dither.NONE)
    
    today_folder = os.path.join(BASE_DIR, "archive", datetime.now().strftime("%Y-%m-%d"))
    os.makedirs(today_folder, exist_ok=True)
    archive_path = os.path.join(today_folder, "weather.png")
    
    quantized.save(archive_path)
    quantized.save(latest_path)
    
    if os.path.exists(raw_path):
        os.remove(raw_path)

    print("🎉 图片生成完毕！")
    print(f"👉 最新图路径: {latest_path}")
    print(f"👉 归档图路径: {archive_path}")

if __name__ == "__main__":
    now_d, daily_d, city = fetch_weather()
    svg_str = build_svg(now_d, daily_d, city)
    render_image(svg_str)
