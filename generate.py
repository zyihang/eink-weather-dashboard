import os
import re
import calendar
import requests
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

# 引入中国农历库 borax
from borax.calendars.lunardate import LunarDate

# ==================== 1. 屏幕与墨水屏配色 (Kobo Glo 758x1024) ====================
WIDTH = 758
HEIGHT = 1024

QWEATHER_KEY = os.getenv("QWEATHER_KEY", "").strip()
raw_host = os.getenv("QWEATHER_HOST", "").strip()
QWEATHER_HOST = re.sub(r'^https?://|/.*$', '', raw_host)
LOCATION_ID = os.getenv("LOCATION_ID", "101010100").strip()

COLOR_WHITE = 255       # 背景白
COLOR_BLACK = 0         # 纯黑
COLOR_GRAY_DARK = 70    # 深灰文字
COLOR_GRAY_LIGHT = 130  # 次级标签底色与次要文字
COLOR_BORDER = 190      # 分割线与细边框

CITY_MAP = {
    "101010100": "北京",
    "101020100": "上海",
    "101280101": "广州",
    "101280601": "深圳",
    "101070211": "大连 · 高新园区"
}

# ==================== 2. 天气数据拉取 ====================
def fetch_weather():
    clean_id = re.sub(r'[^0-9]', '', str(LOCATION_ID))
    if not clean_id:
        clean_id = "101010100"

    city_name = CITY_MAP.get(clean_id, f"城市ID:{clean_id}")
    if clean_id not in CITY_MAP and QWEATHER_HOST and QWEATHER_KEY:
        try:
            geo_url = f"https://{QWEATHER_HOST}/v2/city/lookup?location={clean_id}&key={QWEATHER_KEY}"
            resp = requests.get(geo_url, headers={"Accept-Encoding": "identity"}, timeout=10).json()
            if resp.get("code") == "200" and resp.get("location"):
                loc = resp["location"][0]
                adm2 = loc.get("adm2", "")
                district = loc.get("name", "")
                city_name = f"{adm2} · {district}" if (adm2 and adm2 != district) else district
        except Exception:
            pass

    headers = {
        "X-QW-Api-Key": QWEATHER_KEY,
        "Accept-Encoding": "identity",
        "User-Agent": "Mozilla/5.0"
    }

    now_url = f"https://{QWEATHER_HOST}/v7/weather/now?location={clean_id}&key={QWEATHER_KEY}"
    daily_url = f"https://{QWEATHER_HOST}/v7/weather/3d?location={clean_id}&key={QWEATHER_KEY}"

    now_data = {}
    daily_data = []

    try:
        r_now = requests.get(now_url, headers=headers, timeout=10).json()
        if r_now.get("code") == "200":
            now_data = r_now.get("now", {})
        r_daily = requests.get(daily_url, headers=headers, timeout=10).json()
        if r_daily.get("code") == "200":
            daily_data = r_daily.get("daily", [])
    except Exception as e:
        print(f"⚠️ 天气请求异常: {e}")

    if not now_data:
        now_data = {"temp": "--", "text": "晴", "humidity": "--", "windScale": "-", "feelsLike": "--", "windDir": "微风"}
    if not daily_data:
        daily_data = [
            {"fxDate": "今天", "textDay": "晴", "tempMax": "--", "tempMin": "--", "sunrise": "06:00", "sunset": "18:00", "uvIndex": "-"},
            {"fxDate": "明天", "textDay": "多云", "tempMax": "--", "tempMin": "--", "windDirDay": "微风", "windScaleDay": "2", "uvIndex": "-"},
            {"fxDate": "后天", "textDay": "晴", "tempMax": "--", "tempMin": "--", "windDirDay": "微风", "windScaleDay": "2", "uvIndex": "-"}
        ]

    return now_data, daily_data, city_name

# ==================== 3. 字体与图形辅助 ====================
def load_font(size, bold=False):
    font_paths = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc" if bold else "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc" if bold else "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "msyh.ttc", "simhei.ttf"
    ]
    for p in font_paths:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()

# ==================== 4. 核心绘制 ====================
def generate_calendar_dashboard():
    now_data, daily_data, city_name = fetch_weather()
    today_w = daily_data[0] if daily_data else {}
    tomorrow_w = daily_data[1] if len(daily_data) > 1 else {}
    after_w = daily_data[2] if len(daily_data) > 2 else {}

    now = datetime.now()
    
    # 农历与生肖转换（已修复属性调用问题）
    lunar = LunarDate.from_solar_date(now.year, now.month, now.day)
    lunar_cn = lunar.strftime("%M月%D")  # 例如：十月初八
    gz_year = lunar.strftime("%G年")      # 例如：丙午年
    
    # animal 是属性不是函数
    animal = lunar.animal if hasattr(lunar, 'animal') else "未知"
    
    # term 也是属性或属性方法，做安全判断
    solar_term = getattr(lunar, 'term', None)
    if callable(solar_term):
        solar_term = solar_term()
    term_str = f" · 【{solar_term}】" if solar_term else ""

    # 计算一年中的第几天与周数
    day_of_year = now.timetuple().tm_yday
    week_of_year = now.isocalendar()[1]

    # 画布初始化 (纯 8-bit 单通道灰度)
    img = Image.new("L", (WIDTH, HEIGHT), COLOR_WHITE)
    draw = ImageDraw.Draw(img)

    # 字体准备
    font_bar = load_font(22, bold=True)
    font_sub_bar = load_font(18)
    font_giant_day = load_font(150, bold=True)
    font_date_head = load_font(28, bold=True)
    font_lunar_main = load_font(24, bold=True)
    font_lunar_sub = load_font(20)
    font_cal_week = load_font(16, bold=True)
    font_cal_day = load_font(18)
    font_sec_title = load_font(22, bold=True)
    font_card_head = load_font(20, bold=True)
    font_weather_big = load_font(36, bold=True)
    font_detail = load_font(18)

    # ---------------- 1. 顶部 Header 状态栏 (0 ~ 80px) ----------------
    draw.rectangle((0, 0, WIDTH, 80), fill=COLOR_BLACK)
    draw.text((30, 26), f"📍 {city_name}", fill=COLOR_WHITE, font=font_bar)
    lunar_header = f"岁次{gz_year} · 属{animal} {term_str}"
    draw.text((230, 28), lunar_header, fill=220, font=font_sub_bar)
    draw.text((WIDTH - 170, 28), f"{now.strftime('%H:%M')} 更新", fill=190, font=font_sub_bar)

    # ---------------- 2. 上半区：极简万年历 (80 ~ 460px) ----------------
    # 左侧：今日大字撕历排版 (宽 380px)
    weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    week_str = weekdays[now.weekday()]
    month_str = f"{now.year}年 {now.month}月"

    draw.text((35, 105), month_str, fill=COLOR_BLACK, font=font_date_head)
    draw.text((220, 110), f"·  {week_str}", fill=COLOR_GRAY_DARK, font=font_lunar_sub)

    # 居中特大公历数字
    day_str = f"{now.day:02d}" if now.day < 10 else str(now.day)
    draw.text((28, 130), day_str, fill=COLOR_BLACK, font=font_giant_day)

    # 农历与年份进度详细展示
    draw.text((35, 320), f"农历  {lunar_cn}", fill=COLOR_BLACK, font=font_lunar_main)
    draw.text((35, 365), f"第 {week_of_year} 周  ·  全年第 {day_of_year} 天", fill=COLOR_GRAY_DARK, font=font_lunar_sub)
    draw.text((35, 400), f"公历纪年: {now.strftime('%Y-%m-%d')}", fill=COLOR_GRAY_LIGHT, font=font_detail)

    # 左右分割纵线
    draw.line((395, 110, 395, 440), fill=COLOR_BORDER, width=2)

    # 右侧：当月整月日历矩阵 (X: 425 ~ 728)
    draw.text((425, 105), f"📅 本月日历", fill=COLOR_BLACK, font=font_date_head)

    cal_headers = ["一", "二", "三", "四", "五", "六", "日"]
    grid_start_x = 425
    grid_start_y = 155
    col_w = 43
    row_h = 44

    for i, h in enumerate(cal_headers):
        draw.text((grid_start_x + i * col_w + 10, grid_start_y), h, fill=COLOR_GRAY_DARK, font=font_cal_week)

    draw.line((grid_start_x, grid_start_y + 30, grid_start_x + 7 * col_w, grid_start_y + 30), fill=COLOR_BORDER, width=1)

    cal = calendar.Calendar(firstweekday=0)
    month_days = cal.monthdayscalendar(now.year, now.month)

    for r_idx, week in enumerate(month_days):
        for c_idx, d in enumerate(week):
            if d != 0:
                cx = grid_start_x + c_idx * col_w + 5
                cy = grid_start_y + 40 + r_idx * row_h
                if d == now.day:
                    # 当天反白加黑圆角底框
                    draw.rounded_rectangle((cx - 3, cy - 2, cx + 33, cy + 28), radius=6, fill=COLOR_BLACK)
                    draw.text((cx + (3 if d < 10 else 0), cy + 2), str(d), fill=COLOR_WHITE, font=font_cal_day)
                else:
                    draw.text((cx + (4 if d < 10 else 0), cy + 2), str(d), fill=COLOR_BLACK, font=font_cal_day)

    # 中部横向主分割线
    draw.line((30, 465, WIDTH - 30, 465), fill=COLOR_BLACK, width=2)

    # ---------------- 3. 下半区：今天 + 未来 2 天气象卡片 (480 ~ 990px) ----------------
    draw.text((30, 485), "🌤️ 气象看板 (今天及未来两日)", fill=COLOR_BLACK, font=font_sec_title)

    card_y = 525
    card_w = (WIDTH - 60 - 20) // 3  # 每张卡片宽约 226
    card_h = 450

    cards_meta = [
        {"label": "今天", "date": "实况", "w": today_w, "is_today": True},
        {"label": "明天", "date": tomorrow_w.get("fxDate", "未来")[5:], "w": tomorrow_w, "is_today": False},
        {"label": "后天", "date": after_w.get("fxDate", "未来")[5:], "w": after_w, "is_today": False},
    ]

    for i, item in enumerate(cards_meta):
        x1 = 30 + i * (card_w + 10)
        x2 = x1 + card_w
        w_obj = item["w"]

        # 卡片圆角白底外框 + 投影
        draw.rounded_rectangle((x1 + 3, card_y + 3, x2 + 3, card_y + card_h + 3), radius=10, fill=225)
        draw.rounded_rectangle((x1, card_y, x2, card_y + card_h), radius=10, fill=COLOR_WHITE, outline=COLOR_BLACK if item["is_today"] else COLOR_BORDER, width=2 if item["is_today"] else 1)

        # 卡片顶部标签
        tag_bg = COLOR_BLACK if item["is_today"] else COLOR_GRAY_LIGHT
        draw.rounded_rectangle((x1 + 15, card_y + 15, x1 + 80, card_y + 45), radius=4, fill=tag_bg)
        draw.text((x1 + 25, card_y + 19), item["label"], fill=COLOR_WHITE, font=font_card_head)
        draw.text((x1 + 92, card_y + 20), item["date"], fill=COLOR_GRAY_DARK, font=font_detail)

        # 卡片内部数据呈现
        if item["is_today"]:
            cur_temp = str(now_data.get("temp", "--"))
            draw.text((x1 + 15, card_y + 60), f"{cur_temp}℃", fill=COLOR_BLACK, font=font_giant_day)
            draw.text((x1 + 15, card_y + 180), now_data.get("text", "晴"), fill=COLOR_BLACK, font=font_weather_big)
            draw.text((x1 + 15, card_y + 230), f"全日: {w_obj.get('tempMin', '--')} ~ {w_obj.get('tempMax', '--')}℃", fill=COLOR_GRAY_DARK, font=font_detail)

            draw.line((x1 + 15, card_y + 265, x2 - 15, card_y + 265), fill=COLOR_BORDER, width=1)
            draw.text((x1 + 15, card_y + 280), f"体感温度: {now_data.get('feelsLike', '--')}℃", fill=COLOR_BLACK, font=font_detail)
            draw.text((x1 + 15, card_y + 312), f"相对湿度: {now_data.get('humidity', '--')}%", fill=COLOR_BLACK, font=font_detail)
            draw.text((x1 + 15, card_y + 344), f"风向风力: {now_data.get('windDir', '微风')} {now_data.get('windScale', '-')}级", fill=COLOR_BLACK, font=font_detail)
            draw.text((x1 + 15, card_y + 376), f"日出日落: {w_obj.get('sunrise', '--')}/{w_obj.get('sunset', '--')}", fill=COLOR_GRAY_DARK, font=font_detail)
            draw.text((x1 + 15, card_y + 408), f"紫外线指数: {w_obj.get('uvIndex', '-')}", fill=COLOR_GRAY_DARK, font=font_detail)
        else:
            weather_desc = w_obj.get("textDay", "晴")
            draw.text((x1 + 15, card_y + 70), weather_desc, fill=COLOR_BLACK, font=font_weather_big)
            draw.text((x1 + 15, card_y + 125), f"{w_obj.get('tempMin', '--')} ~ {w_obj.get('tempMax', '--')}℃", fill=COLOR_BLACK, font=font_date_head)

            draw.line((x1 + 15, card_y + 185, x2 - 15, card_y + 185), fill=COLOR_BORDER, width=1)
            draw.text((x1 + 15, card_y + 210), f"夜间天气: {w_obj.get('textNight', '晴')}", fill=COLOR_GRAY_DARK, font=font_detail)
            draw.text((x1 + 15, card_y + 250), f"白天风向: {w_obj.get('windDirDay', '微风')}", fill=COLOR_GRAY_DARK, font=font_detail)
            draw.text((x1 + 15, card_y + 290), f"风力等级: {w_obj.get('windScaleDay', '-')}级", fill=COLOR_GRAY_DARK, font=font_detail)
            draw.text((x1 + 15, card_y + 330), f"紫外线: {w_obj.get('uvIndex', '-')}", fill=COLOR_GRAY_DARK, font=font_detail)
            draw.text((x1 + 15, card_y + 370), f"日出: {w_obj.get('sunrise', '--')}", fill=COLOR_GRAY_DARK, font=font_detail)
            draw.text((x1 + 15, card_y + 405), f"日落: {w_obj.get('sunset', '--')}", fill=COLOR_GRAY_DARK, font=font_detail)

    # 底部标记
    draw.text((WIDTH // 2 - 100, 995), "Kobo Glo E-Ink Calendar", fill=180, font=font_sub_bar)

    # 导出与保存
    os.makedirs("archive", exist_ok=True)
    archive_path = f"archive/{now.strftime('%Y%m%d_%H%M')}.png"

    img.save("latest.png", format="PNG", optimize=True)
    img.save(archive_path, format="PNG", optimize=True)
    print(f"🎉 成功生成极简万年历天气看板: latest.png 和 {archive_path}")

if __name__ == "__main__":
    generate_calendar_dashboard()
