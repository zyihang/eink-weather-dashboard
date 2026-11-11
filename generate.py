import os
import requests
import cairosvg
from PIL import Image
from datetime import datetime

QWEATHER_KEY = os.getenv("QWEATHER_KEY")
LOCATION_ID = os.getenv("LOCATION_ID", "101010100") # 默认北京

def fetch_weather():
    now_url = f"https://devapi.qweather.com/v7/weather/now?location={LOCATION_ID}&key={QWEATHER_KEY}"
    daily_url = f"https://devapi.qweather.com/v7/weather/3d?location={LOCATION_ID}&key={QWEATHER_KEY}"
    
    try:
        now_data = requests.get(now_url, timeout=10).json().get("now", {})
        daily_data = requests.get(daily_url, timeout=10).json().get("daily", [])
    except Exception as e:
        print(f"API 获取异常: {e}")
        now_data = {"temp": "23", "text": "多云", "humidity": "48", "windScale": "2", "feelsLike": "22"}
        daily_data = [
            {"fxDate": "2025-05-19", "textDay": "多云", "tempMax": "25", "tempMin": "15"},
            {"fxDate": "2025-05-20", "textDay": "小雨", "tempMax": "20", "tempMin": "14"},
            {"fxDate": "2025-05-21", "textDay": "晴", "tempMax": "26", "tempMin": "16"}
        ]
    return now_data, daily_data

def get_weather_icon(text, x, y, scale=1.0):
    """根据天气文字动态生成高质感纯色矢量图标"""
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
    elif "雪" in text:
        return f'''<g transform="translate({x},{y}) scale({scale})">
            <path d="M22 42 A14 14 0 0 1 35 20 A22 22 0 0 1 70 26 A16 16 0 0 1 68 46 H24" fill="#FFFFFF" stroke="#000000" stroke-width="3"/>
            <circle cx="32" cy="62" r="3.5" fill="#FFCC00"/>
            <circle cx="48" cy="62" r="3.5" fill="#FFCC00"/>
            <circle cx="40" cy="74" r="3.5" fill="#FFCC00"/>
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

def build_tips(temp, text):
    t = int(temp) if temp.lstrip('-').isdigit() else 22
    tip1 = "体感凉爽，早晚注意添衣保暖" if t < 18 else ("气温较高，注意做好防暑防晒" if t > 28 else "温度舒适，适宜各项户外活动")
    tip2 = "今日有雨，出门请携带雨具" if "雨" in text else ("湿度较低，注意室内多补水" if "晴" in text else "空气状况良好，建议开窗通风")
    return tip1, tip2

def build_svg(now, daily):
    now_dt = datetime.now()
    today_str = now_dt.strftime("%Y.%m.%d")
    weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    week_str = weekdays[now_dt.weekday()]
    
    temp = str(now.get("temp", "24"))
    feels_like = str(now.get("feelsLike", temp))
    text = now.get("text", "晴")
    humidity = str(now.get("humidity", "45"))
    wind = str(now.get("windScale", "2"))
    
    d1 = daily[0] if len(daily) > 0 else {"fxDate": "--", "textDay": "晴", "tempMax": "25", "tempMin": "16"}
    d2 = daily[1] if len(daily) > 1 else {"fxDate": "--", "textDay": "小雨", "tempMax": "22", "tempMin": "15"}
    d3 = daily[2] if len(daily) > 2 else {"fxDate": "--", "textDay": "晴", "tempMax": "24", "tempMin": "16"}
    
    tip1, tip2 = build_tips(temp, text)
    main_icon = get_weather_icon(text, 260, 95, scale=1.35)
    
    icon_d1 = get_weather_icon(d1.get("textDay", ""), 495, 125, scale=0.6)
    icon_d2 = get_weather_icon(d2.get("textDay", ""), 495, 235, scale=0.6)
    icon_d3 = get_weather_icon(d3.get("textDay", ""), 495, 345, scale=0.6)

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 480" width="800" height="480" style="background:#FFFFFF; font-family: 'Noto Sans CJK SC', 'Source Han Sans SC', sans-serif;">
  <defs>
    <style>
      .bold {{ font-weight: 900; }}
      .medium {{ font-weight: bold; }}
      .light {{ font-weight: 500; fill: #666666; }}
    </style>
  </defs>

  <!-- 顶部极简状态栏 -->
  <line x1="30" y1="52" x2="770" y2="52" stroke="#000000" stroke-width="2"/>
  <rect x="30" y="24" width="8" height="20" fill="#FF0000" />
  <text x="46" y="40" font-size="20" class="bold" fill="#000000" letter-spacing="1">DAILY BRIEFING</text>
  <text x="235" y="40" font-size="14" class="light">气象与环境晨报</text>
  <text x="635" y="40" font-size="16" class="bold" fill="#000000">{today_str} · {week_str}</text>

  <!-- 左侧主 Bento 卡片（当前天气） -->
  <rect x="30" y="70" width="420" height="235" rx="16" fill="#FFFFFF" stroke="#000000" stroke-width="2.5"/>
  
  <!-- 状态胶囊标签 -->
  <rect x="50" y="90" width="76" height="26" rx="13" fill="#FFCC00"/>
  <text x="64" y="108" font-size="13" class="bold" fill="#000000">{text}</text>
  <text x="138" y="108" font-size="13" class="light">体感 {feels_like}°C</text>

  <!-- 超大温度（核心视觉焦点） -->
  <text x="45" y="210" font-size="105" class="bold" fill="#000000" letter-spacing="-4">{temp}°</text>

  <!-- 主矢量图标 -->
  {main_icon}

  <!-- 底部关键参数网格 -->
  <line x1="50" y1="230" x2="430" y2="230" stroke="#E0E0E0" stroke-width="1.5"/>
  <text x="50" y="255" font-size="12" class="light">环境湿度</text>
  <text x="50" y="280" font-size="18" class="bold" fill="#000000">{humidity}%</text>

  <text x="155" y="255" font-size="12" class="light">今日风级</text>
  <text x="155" y="280" font-size="18" class="bold" fill="#000000">{wind} 级</text>

  <text x="260" y="255" font-size="12" class="light">紫外线强度</text>
  <text x="260" y="280" font-size="18" class="bold" fill="#FF0000">强</text>

  <text x="365" y="255" font-size="12" class="light">空气质量</text>
  <text x="365" y="280" font-size="18" class="bold" fill="#000000">优</text>

  <!-- 左下：生活指南卡片 -->
  <rect x="30" y="320" width="420" height="135" rx="16" fill="#F8F8F8" stroke="#000000" stroke-width="2"/>
  <circle cx="52" cy="346" r="5" fill="#FF0000"/>
  <text x="66" y="352" font-size="15" class="bold" fill="#000000">今日贴心提醒</text>

  <text x="52" y="388" font-size="14" class="bold" fill="#000000">1. {tip1}</text>
  <text x="52" y="420" font-size="14" class="bold" fill="#000000">2. {tip2}</text>

  <!-- 右侧：未来三天预报 Bento Grid -->
  <!-- Day 1 -->
  <rect x="475" y="70" width="295" height="100" rx="16" fill="#FFFFFF" stroke="#000000" stroke-width="2"/>
  <text x="495" y="102" font-size="15" class="bold" fill="#000000">明天 · {d1.get("fxDate", "")[5:]}</text>
  <text x="495" y="148" font-size="14" class="medium" fill="#000000">{d1.get("textDay")}</text>
  {icon_d1}
  <text x="645" y="132" font-size="28" class="bold" fill="#FF0000">{d1.get("tempMax")}°</text>
  <text x="705" y="130" font-size="18" class="medium" fill="#000000">/ {d1.get("tempMin")}°</text>

  <!-- Day 2 (重点关注卡片 - 黄色微高亮风格) -->
  <rect x="475" y="180" width="295" height="100" rx="16" fill="#FFFFFF" stroke="#000000" stroke-width="2.5"/>
  <rect x="475" y="180" width="10" height="100" fill="#FFCC00" />
  <text x="495" y="212" font-size="15" class="bold" fill="#000000">后天 · {d2.get("fxDate", "")[5:]}</text>
  <text x="495" y="258" font-size="14" class="bold" fill="#000000">{d2.get("textDay")}</text>
  {icon_d2}
  <text x="645" y="242" font-size="28" class="bold" fill="#FF0000">{d2.get("tempMax")}°</text>
  <text x="705" y="240" font-size="18" class="medium" fill="#000000">/ {d2.get("tempMin")}°</text>

  <!-- Day 3 -->
  <rect x="475" y="290" width="295" height="100" rx="16" fill="#FFFFFF" stroke="#000000" stroke-width="2"/>
  <text x="495" y="322" font-size="15" class="bold" fill="#000000">大后天 · {d3.get("fxDate", "")[5:]}</text>
  <text x="495" y="368" font-size="14" class="medium" fill="#000000">{d3.get("textDay")}</text>
  {icon_d3}
  <text x="645" y="352" font-size="28" class="bold" fill="#FF0000">{d3.get("tempMax")}°</text>
  <text x="705" y="350" font-size="18" class="medium" fill="#000000">/ {d3.get("tempMin")}°</text>

  <!-- 底部签名小字 -->
  <text x="480" y="440" font-size="12" class="light">E-INK WEATHER TERMINAL · AUTO SYNC AT 06:30</text>
</svg>'''
    return svg

def render_image(svg_str):
    cairosvg.svg2png(bytestring=svg_str.encode('utf-8'), write_to='raw.png')
    
    # 纯净墨水屏四色调色板
    img = Image.open('raw.png').convert('RGB')
    palette = [0,0,0,  255,255,255,  255,204,0,  255,0,0] + [0]*(768-12)
    pal_img = Image.new("P", (1, 1))
    pal_img.putpalette(palette)
    
    quantized = img.quantize(palette=pal_img, dither=Image.Dither.NONE)
    
    # 存入当天日期文件夹
    today_folder = os.path.join("archive", datetime.now().strftime("%Y-%m-%d"))
    os.makedirs(today_folder, exist_ok=True)
    quantized.save(os.path.join(today_folder, "weather.png"))
    
    # 根目录保存 latest.png
    quantized.save("latest.png")
    
    if os.path.exists("raw.png"):
        os.remove("raw.png")

if __name__ == "__main__":
    now_d, daily_d = fetch_weather()
    svg_str = build_svg(now_d, daily_d)
    render_image(svg_str)
