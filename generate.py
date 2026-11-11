import os
import requests
import cairosvg
from PIL import Image
from datetime import datetime

QWEATHER_KEY = os.getenv("QWEATHER_KEY")
LOCATION_ID = os.getenv("LOCATION_ID", "101010100") # 默认北京，可在 Secret 中指定

def fetch_weather():
    now_url = f"https://devapi.qweather.com/v7/weather/now?location={LOCATION_ID}&key={QWEATHER_KEY}"
    daily_url = f"https://devapi.qweather.com/v7/weather/3d?location={LOCATION_ID}&key={QWEATHER_KEY}"
    
    try:
        now_data = requests.get(now_url, timeout=10).json().get("now", {})
        daily_data = requests.get(daily_url, timeout=10).json().get("daily", [])
    except Exception as e:
        print(f"API 获取异常，采用兜底数据: {e}")
        now_data = {"temp": "26", "text": "晴", "humidity": "42", "windScale": "2"}
        daily_data = [
            {"fxDate": "2025-05-19", "textDay": "多云转晴", "tempMax": "27", "tempMin": "15"},
            {"fxDate": "2025-05-20", "textDay": "小雨", "tempMax": "21", "tempMin": "13"},
            {"fxDate": "2025-05-21", "textDay": "晴", "tempMax": "25", "tempMin": "14"}
        ]
    return now_data, daily_data

def build_svg(now, daily):
    now_dt = datetime.now()
    today_str = now_dt.strftime("%Y-%m-%d")
    weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    week_str = weekdays[now_dt.weekday()]
    
    temp = now.get("temp", "26")
    text = now.get("text", "晴")
    humidity = now.get("humidity", "45")
    wind = now.get("windScale", "2")
    
    d1 = daily[0] if len(daily) > 0 else {"fxDate": "--", "textDay": "晴", "tempMax": "26", "tempMin": "15"}
    d2 = daily[1] if len(daily) > 1 else {"fxDate": "--", "textDay": "阴", "tempMax": "22", "tempMin": "14"}
    d3 = daily[2] if len(daily) > 2 else {"fxDate": "--", "textDay": "晴", "tempMax": "25", "tempMin": "15"}

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 480" width="800" height="480" style="background:#ffffff; font-family: 'Noto Sans CJK SC', 'Source Han Sans SC', 'PingFang SC', sans-serif;">
  <!-- 顶部状态栏 -->
  <rect x="0" y="0" width="800" height="50" fill="#FF0000" />
  <text x="25" y="32" fill="#FFFFFF" font-size="20" font-weight="900" letter-spacing="1">智能气象看板 · WEATHER &amp; ENVIRONMENT</text>
  <text x="630" y="32" fill="#FFFFFF" font-size="15" font-weight="bold">{today_str} · {week_str}</text>

  <!-- 今日实时天气区 -->
  <text x="25" y="85" fill="#000000" font-size="18" font-weight="bold">📍 当前定位区域</text>
  <text x="160" y="85" fill="#000000" font-size="13" opacity="0.7">{now_dt.strftime("%H:%M")} 更新</text>

  <!-- 巨大主温度 -->
  <text x="20" y="180" fill="#000000" font-size="96" font-weight="900" letter-spacing="-3">{temp}°</text>
  
  <!-- 太阳矢量图标 -->
  <g transform="translate(230, 105)">
    <circle cx="35" cy="35" r="22" fill="#FFCC00" stroke="#000000" stroke-width="2.5"/>
    <line x1="35" y1="2" x2="35" y2="8" stroke="#FFCC00" stroke-width="4" stroke-linecap="round"/>
    <line x1="35" y1="62" x2="35" y2="68" stroke="#FFCC00" stroke-width="4" stroke-linecap="round"/>
    <line x1="2" y1="35" x2="8" y2="35" stroke="#FFCC00" stroke-width="4" stroke-linecap="round"/>
    <line x1="62" y1="35" x2="68" y2="35" stroke="#FFCC00" stroke-width="4" stroke-linecap="round"/>
    <line x1="12" y1="12" x2="16" y2="16" stroke="#FFCC00" stroke-width="4" stroke-linecap="round"/>
    <line x1="54" y1="54" x2="58" y2="58" stroke="#FFCC00" stroke-width="4" stroke-linecap="round"/>
    <line x1="12" y1="58" x2="16" y2="54" stroke="#FFCC00" stroke-width="4" stroke-linecap="round"/>
    <line x1="54" y1="16" x2="58" y2="12" stroke="#FFCC00" stroke-width="4" stroke-linecap="round"/>
  </g>
  <text x="320" y="142" fill="#000000" font-size="28" font-weight="900">{text}</text>
  <text x="320" y="172" fill="#FF0000" font-size="15" font-weight="bold">最高温预估: {d1.get("tempMax")}°C</text>

  <!-- 指标栏 -->
  <line x1="25" y1="205" x2="450" y2="205" stroke="#000000" stroke-width="2" />
  
  <text x="25" y="235" fill="#000000" font-size="14" font-weight="bold">相对湿度</text>
  <text x="25" y="262" fill="#000000" font-size="22" font-weight="900">{humidity}%</text>

  <text x="140" y="235" fill="#000000" font-size="14" font-weight="bold">当前风力</text>
  <text x="140" y="262" fill="#000000" font-size="22" font-weight="900">{wind} 级</text>

  <text x="250" y="235" fill="#000000" font-size="14" font-weight="bold">紫外线指数</text>
  <text x="250" y="262" fill="#FF0000" font-size="22" font-weight="900">强</text>

  <text x="360" y="235" fill="#000000" font-size="14" font-weight="bold">空气质量</text>
  <rect x="360" y="244" width="60" height="22" rx="4" fill="#FFCC00" />
  <text x="372" y="260" fill="#000000" font-size="13" font-weight="900">优良</text>

  <!-- 生活提示卡片 -->
  <rect x="25" y="290" width="425" height="160" rx="8" fill="none" stroke="#000000" stroke-width="2" />
  <path d="M 25 298 A 8 8 0 0 1 33 290 L 442 290 A 8 8 0 0 1 450 298 L 450 325 L 25 325 Z" fill="#FFCC00" />
  <text x="40" y="314" fill="#000000" font-size="15" font-weight="900">💡 今日出行与生活提示</text>

  <circle cx="45" cy="355" r="4" fill="#FF0000" />
  <text x="60" y="360" fill="#000000" font-size="14" font-weight="bold">早晚温差较大，出门适量携带薄外套。</text>

  <circle cx="45" cy="390" r="4" fill="#FF0000" />
  <text x="60" y="395" fill="#000000" font-size="14" font-weight="bold">午后光照较充足，外出推荐做好防晒防护。</text>

  <circle cx="45" cy="425" r="4" fill="#000000" />
  <text x="60" y="430" fill="#000000" font-size="14" font-weight="bold">室内建议勤通风换气，保持空气洁净。</text>

  <!-- 纵向分割虚线 -->
  <line x1="480" y1="70" x2="480" y2="455" stroke="#000000" stroke-width="2" stroke-dasharray="4,4" />

  <!-- 未来三天预报 -->
  <text x="505" y="90" fill="#000000" font-size="18" font-weight="900">📅 未来三天天气趋势</text>

  <!-- 明天 -->
  <g transform="translate(505, 115)">
    <rect x="0" y="0" width="270" height="95" rx="8" fill="none" stroke="#000000" stroke-width="2" />
    <path d="M 0 8 A 8 8 0 0 1 8 0 L 8 95 A 8 8 0 0 1 0 87 Z" fill="#FFCC00" />
    <text x="20" y="32" fill="#000000" font-size="16" font-weight="900">明天 · {d1.get("fxDate")[5:]}</text>
    <text x="20" y="60" fill="#000000" font-size="15" font-weight="bold">{d1.get("textDay")}</text>
    <text x="155" y="48" fill="#FF0000" font-size="26" font-weight="900">{d1.get("tempMax")}°</text>
    <text x="210" y="48" fill="#000000" font-size="20" font-weight="bold">/ {d1.get("tempMin")}°</text>
    <text x="160" y="76" fill="#000000" font-size="12">日间温和</text>
  </g>

  <!-- 后天 -->
  <g transform="translate(505, 230)">
    <rect x="0" y="0" width="270" height="95" rx="8" fill="none" stroke="#FF0000" stroke-width="2" />
    <path d="M 0 8 A 8 8 0 0 1 8 0 L 8 95 A 8 8 0 0 1 0 87 Z" fill="#FF0000" />
    <text x="20" y="32" fill="#000000" font-size="16" font-weight="900">后天 · {d2.get("fxDate")[5:]}</text>
    <text x="20" y="60" fill="#FF0000" font-size="15" font-weight="900">{d2.get("textDay")}</text>
    <text x="155" y="48" fill="#FF0000" font-size="26" font-weight="900">{d2.get("tempMax")}°</text>
    <text x="210" y="48" fill="#000000" font-size="20" font-weight="bold">/ {d2.get("tempMin")}°</text>
    <rect x="155" y="62" width="75" height="20" rx="3" fill="#FF0000" />
    <text x="163" y="76" fill="#FFFFFF" font-size="11" font-weight="900">重点关注</text>
  </g>

  <!-- 大后天 -->
  <g transform="translate(505, 345)">
    <rect x="0" y="0" width="270" height="95" rx="8" fill="none" stroke="#000000" stroke-width="1.5" />
    <path d="M 0 8 A 8 8 0 0 1 8 0 L 8 95 A 8 8 0 0 1 0 87 Z" fill="#000000" />
    <text x="20" y="32" fill="#000000" font-size="16" font-weight="900">周三 · {d3.get("fxDate")[5:]}</text>
    <text x="20" y="60" fill="#000000" font-size="15" font-weight="bold">{d3.get("textDay")}</text>
    <text x="155" y="48" fill="#FF0000" font-size="26" font-weight="900">{d3.get("tempMax")}°</text>
    <text x="210" y="48" fill="#000000" font-size="20" font-weight="bold">/ {d3.get("tempMin")}°</text>
    <text x="160" y="76" fill="#000000" font-size="12">天气平稳</text>
  </g>
</svg>'''
    return svg

def render_image(svg_str):
    # 1. Cairo 高精度矢量渲染为高清原始图
    cairosvg.svg2png(bytestring=svg_str.encode('utf-8'), write_to='raw.png')
    
    # 2. 纯四色墨水屏调色板量化（无噪点）
    img = Image.open('raw.png').convert('RGB')
    palette = [0,0,0,  255,255,255,  255,204,0,  255,0,0] + [0]*(768-12)
    pal_img = Image.new("P", (1, 1))
    pal_img.putpalette(palette)
    
    quantized = img.quantize(palette=pal_img, dither=Image.Dither.NONE)
    
    # 3. 按日期创建归档目录 (格式: archive/2025-05-18/)
    today_folder = os.path.join("archive", datetime.now().strftime("%Y-%m-%d"))
    os.makedirs(today_folder, exist_ok=True)
    
    # 保存归档图片
    dated_path = os.path.join(today_folder, "weather.png")
    quantized.save(dated_path)
    
    # 同时根目录保留最新一份 latest.png
    quantized.save("latest.png")
    
    # 清理临时原始文件
    if os.path.exists("raw.png"):
        os.remove("raw.png")
        
    print(f"成功保存归档图片: {dated_path}")
    print("成功更新最新图片: latest.png")

if __name__ == "__main__":
    now_d, daily_d = fetch_weather()
    svg_data = build_svg(now_d, daily_d)
    render_image(svg_data)
