import os
import requests
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime

# 1. 基础配置
QWEATHER_KEY = os.getenv("QWEATHER_KEY")
LOCATION_ID = os.getenv("LOCATION_ID", "101010100") # 默认北京，可在 Secret 中覆盖

COLOR_BLACK = (0, 0, 0)
COLOR_WHITE = (255, 255, 255)
COLOR_YELLOW = (255, 204, 0)   # 调准明黄色
COLOR_RED = (255, 0, 0)

def fetch_data():
    now_url = f"https://devapi.qweather.com/v7/weather/now?location={LOCATION_ID}&key={QWEATHER_KEY}"
    daily_url = f"https://devapi.qweather.com/v7/weather/3d?location={LOCATION_ID}&key={QWEATHER_KEY}"
    
    now_res = requests.get(now_url, timeout=10).json()
    daily_res = requests.get(daily_url, timeout=10).json()
    
    now = now_res.get("now", {"temp": "25", "text": "晴", "humidity": "40", "windScale": "2"})
    daily = daily_res.get("daily", [])
    return now, daily

def get_font(size):
    # GitHub Ubuntu 环境下安装的开源文泉驿中文字体路径
    font_paths = [
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "msyh.ttc"
    ]
    for p in font_paths:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()

def draw_canvas(now, daily):
    img = Image.new("RGB", (800, 480), COLOR_WHITE)
    draw = ImageDraw.Draw(img)

    f_title = get_font(20)
    f_huge = get_font(90)
    f_mid = get_font(22)
    f_small = get_font(16)

    # 顶部红色状态栏
    draw.rectangle([0, 0, 800, 50], fill=COLOR_RED)
    draw.text((25, 12), "智能气象看板 · WEATHER DASHBOARD", font=f_title, fill=COLOR_WHITE)
    today_str = datetime.now().strftime("%Y-%m-%d")
    draw.text((640, 15), today_str, font=f_small, fill=COLOR_WHITE)

    # 左侧大温度
    temp_text = f"{now.get('temp', '--')}°"
    draw.text((25, 75), temp_text, font=f_huge, fill=COLOR_BLACK)
    
    # 实时天气状况标识 (黄底黑字小标签)
    weather_text = now.get('text', '晴')
    draw.rectangle([210, 100, 280, 140], fill=COLOR_YELLOW)
    draw.text((220, 107), weather_text, font=f_mid, fill=COLOR_BLACK)

    # 环境指标
    draw.line([(25, 190), (450, 190)], fill=COLOR_BLACK, width=2)
    draw.text((25, 210), f"湿度: {now.get('humidity', '--')}%", font=f_mid, fill=COLOR_BLACK)
    draw.text((160, 210), f"风力: {now.get('windScale', '--')}级", font=f_mid, fill=COLOR_BLACK)
    draw.text((300, 210), "空气: 优", font=f_mid, fill=COLOR_BLACK)

    # 提示框卡片
    draw.rectangle([25, 270, 450, 440], outline=COLOR_BLACK, width=2)
    draw.rectangle([25, 270, 450, 310], fill=COLOR_YELLOW)
    draw.text((40, 280), "出行与穿衣建议", font=f_mid, fill=COLOR_BLACK)
    draw.text((40, 330), "• 昼夜温差大，早晚请注意添衣保暖", font=f_small, fill=COLOR_BLACK)
    draw.text((40, 370), "• 今日紫外线较强，午后出行做好防护", font=f_small, fill=COLOR_RED)
    draw.text((40, 410), "• 天气干燥，请注意多补水", font=f_small, fill=COLOR_BLACK)

    # 中部分割虚线
    for y in range(70, 460, 10):
        draw.line([(480, y), (480, y+5)], fill=COLOR_BLACK, width=1)

    # 右侧三天预报
    draw.text((505, 70), "未来三天预报", font=f_mid, fill=COLOR_BLACK)
    start_y = 115
    for i, d in enumerate(daily[:3]):
        # 卡片框
        draw.rectangle([505, start_y, 775, start_y + 95], outline=COLOR_BLACK, width=1)
        draw.rectangle([505, start_y, 515, start_y + 95], fill=COLOR_YELLOW if i==0 else COLOR_BLACK)
        
        date_txt = d.get('fxDate', '')[5:] # 取 MM-DD
        draw.text((530, start_y + 15), f"日期: {date_txt}", font=f_small, fill=COLOR_BLACK)
        draw.text((530, start_y + 50), d.get('textDay', ''), font=f_mid, fill=COLOR_BLACK)
        
        max_t = f"{d.get('tempMax')}°"
        min_t = f"/ {d.get('tempMin')}°"
        draw.text((670, start_y + 20), max_t, font=f_mid, fill=COLOR_RED)
        draw.text((720, start_y + 20), min_t, font=f_mid, fill=COLOR_BLACK)
        start_y += 115

    return img

def convert_to_4color_bin(img):
    # 构建黑白红黄专属调色板
    palette = [0,0,0,  255,255,255,  255,204,0,  255,0,0] + [0]*(768-12)
    pal_img = Image.new("P", (1, 1))
    pal_img.putpalette(palette)
    
    # 抖动量化
    quantized = img.quantize(palette=pal_img, dither=Image.Dither.FLOYDSTEINBERG)
    quantized.save("output_preview.png") # 预览效果图

    # 导出 2-bit 紧凑二进制 (96,000 字节)
    pixels = list(quantized.getdata())
    packed = bytearray()
    for i in range(0, len(pixels), 4):
        p0, p1, p2, p3 = pixels[i] & 0x03, pixels[i+1] & 0x03, pixels[i+2] & 0x03, pixels[i+3] & 0x03
        packed.append((p0 << 6) | (p1 << 4) | (p2 << 2) | p3)
    
    with open("weather.bin", "wb") as f:
        f.write(packed)

if __name__ == "__main__":
    now_data, daily_data = fetch_data()
    canvas = draw_canvas(now_data, daily_data)
    convert_to_4color_bin(canvas)
