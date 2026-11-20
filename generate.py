import os
import re
import math
import calendar
import requests
from datetime import datetime, timezone, timedelta
from PIL import Image, ImageDraw, ImageFont

# 引入专业中国农历库 borax
try:
    from borax.calendars.lunardate import LunarDate
except ImportError:
    LunarDate = None

# ==================== 1. Kobo Libra 2 专属参数 (1264 x 1680 @ 300 PPI) ====================
WIDTH = 1264
HEIGHT = 1680

BEIJING_TZ = timezone(timedelta(hours=8))

# 环境变量读取与清洗
QWEATHER_KEY = os.getenv("QWEATHER_KEY", "").strip()
raw_host = os.getenv("QWEATHER_HOST", "").strip()
QWEATHER_HOST = re.sub(r'^https?://|/.*$', '', raw_host)
LOCATION_ID = os.getenv("LOCATION_ID", "101010100").strip()

# 纯黑白灰度配色
COLOR_WHITE = 255
COLOR_BLACK = 0
COLOR_GRAY_DARK = 55
COLOR_GRAY_MID = 110
COLOR_GRAY_LIGHT = 180
COLOR_BORDER = 205
COLOR_BG_CARD = 248  # 微灰底色，制造层次感
COLOR_SHADOW = 230

CITY_MAP = {
    "101010100": "北京",
    "101020100": "上海",
    "101280101": "广州",
    "101280601": "深圳",
    "101070211": "大连 · 高新园区"
}

# ==================== 2. 天气数据拉取 ====================
def fetch_weather():
    clean_id = re.sub(r'[^0-9]', '', str(LOCATION_ID)) or "101010100"
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
        print(f"⚠️ 天气接口请求异常: {e}")

    if not now_data:
        now_data = {
            "temp": "22", "text": "多云", "icon": "101", "humidity": "45", "windScale": "2",
            "feelsLike": "21", "windDir": "东北风", "pressure": "1016"
        }
    if not daily_data:
        daily_data = [
            {"fxDate": "今天", "textDay": "多云", "iconDay": "101", "tempMax": "25", "tempMin": "16", "sunrise": "06:12", "sunset": "18:24", "uvIndex": "4"},
            {"fxDate": "明天", "textDay": "晴", "iconDay": "100", "tempMax": "27", "tempMin": "17", "windDirDay": "南风", "windScaleDay": "2", "uvIndex": "6", "sunrise": "06:13", "sunset": "18:23"},
            {"fxDate": "后天", "textDay": "小雨", "iconDay": "305", "tempMax": "21", "tempMin": "14", "windDirDay": "北风", "windScaleDay": "3", "uvIndex": "2", "sunrise": "06:14", "sunset": "18:21"}
        ]

    return now_data, daily_data, city_name

# ==================== 3. 字体加载与农历稳健解析 ====================
def load_font(size, bold=False):
    font_candidates = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc" if bold else "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc" if bold else "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK.ttc",
        "msyh.ttc", "simhei.ttf"
    ]
    for p in font_candidates:
        if os.path.exists(p):
            for idx in [2, 0]:
                try:
                    return ImageFont.truetype(p, size, index=idx)
                except Exception:
                    continue
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()

def get_lunar_info(dt):
    if LunarDate is None:
        return "农历未知", "辛卯年", "兔", ""
    try:
        ld = LunarDate.from_solar_date(dt.year, dt.month, dt.day)
        lunar_cn = ld.strftime("%M月%D")
        gz_year = ld.strftime("%G年")
        animal = getattr(ld, 'animal', "兔")
        if callable(animal):
            animal = animal()
        solar_term = getattr(ld, 'term', None)
        if callable(solar_term):
            solar_term = solar_term()
        term_str = f" · 【{solar_term}】" if solar_term else ""
        return lunar_cn, gz_year, str(animal), term_str
    except Exception as e:
        print(f"⚠️ 历法警告: {e}")
        return "十月初八", "丙午年", "马", ""

# ==================== 4. 纯黑白矢量气象图标绘制引擎 (针对 300 PPI 缩放增强) ====================
def draw_weather_icon(draw, icon_code, text, x, y, size=90):
    code = str(icon_code)
    is_sunny = (code == "100") or ("晴" in text)
    is_cloudy = (code in ["101", "102", "103"]) or ("多云" in text)
    is_overcast = (code == "104") or ("阴" in text)
    is_rain = (code.startswith("3") or "雨" in text)
    is_snow = (code.startswith("4") or "雪" in text)
    is_fog = (code.startswith("5") or "雾" in text or "霾" in text)
    is_thunder = ("雷" in text)

    cx, cy = x + size // 2, y + size // 2
    stroke_w = max(3, int(size // 18))

    # 1. 晴天 (Sun)
    if is_sunny and not is_cloudy:
        r = size * 0.23
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=COLOR_WHITE, outline=COLOR_BLACK, width=stroke_w)
        ray_len = size * 0.12
        ray_dist = size * 0.33
        for i in range(8):
            angle = i * (math.pi / 4)
            x1 = cx + math.cos(angle) * ray_dist
            y1 = cy + math.sin(angle) * ray_dist
            x2 = cx + math.cos(angle) * (ray_dist + ray_len)
            y2 = cy + math.sin(angle) * (ray_dist + ray_len)
            draw.line((x1, y1, x2, y2), fill=COLOR_BLACK, width=stroke_w)
        return

    # 2. 云朵辅助函数
    def draw_cloud(base_cx, base_cy, scale=1.0, fill_color=COLOR_WHITE):
        cw = size * 0.68 * scale
        ch = size * 0.40 * scale
        left = base_cx - cw / 2
        top = base_cy - ch / 2
        w = max(3, int(size // 18))

        draw.rounded_rectangle((left, top + ch * 0.35, left + cw, top + ch * 0.95), radius=int(ch * 0.3), fill=fill_color, outline=COLOR_BLACK, width=w)
        r1 = ch * 0.45
        r2 = ch * 0.35
        c1x, c1y = left + cw * 0.42, top + ch * 0.45
        c2x, c2y = left + cw * 0.72, top + ch * 0.55
        draw.ellipse((c1x - r1, c1y - r1, c1x + r1, c1y + r1), fill=fill_color, outline=COLOR_BLACK, width=w)
        draw.ellipse((c2x - r2, c2y - r2, c2x + r2, c2y + r2), fill=fill_color, outline=COLOR_BLACK, width=w)
        draw.ellipse((c1x - r1 + w, c1y - r1 + w, c1x + r1 - w, c1y + r1 - w), fill=fill_color)
        draw.ellipse((c2x - r2 + w, c2y - r2 + w, c2x + r2 - w, c2y + r2 - w), fill=fill_color)
        draw.rectangle((left + w, top + ch * 0.35 + w, left + cw - w, top + ch * 0.95 - w), fill=fill_color)

    # 3. 多云
    if is_cloudy:
        sun_cx, sun_cy = cx - size * 0.16, cy - size * 0.16
        r = size * 0.19
        draw.ellipse((sun_cx - r, sun_cy - r, sun_cx + r, sun_cy + r), fill=COLOR_WHITE, outline=COLOR_BLACK, width=stroke_w)
        for i in range(5):
            angle = math.pi + i * (math.pi / 4)
            x1 = sun_cx + math.cos(angle) * (r + 3)
            y1 = sun_cy + math.sin(angle) * (r + 3)
            x2 = sun_cx + math.cos(angle) * (r + size * 0.09)
            y2 = sun_cy + math.sin(angle) * (r + size * 0.09)
            draw.line((x1, y1, x2, y2), fill=COLOR_BLACK, width=stroke_w)
        draw_cloud(cx + size * 0.06, cy + size * 0.1, scale=0.88, fill_color=COLOR_WHITE)
        return

    # 4. 阴天
    if is_overcast:
        draw_cloud(cx - size * 0.12, cy - size * 0.12, scale=0.78, fill_color=COLOR_WHITE)
        draw_cloud(cx + size * 0.08, cy + size * 0.12, scale=0.88, fill_color=COLOR_WHITE)
        return

    # 5. 雨天
    if is_rain:
        draw_cloud(cx, cy - size * 0.14, scale=0.88, fill_color=COLOR_WHITE)
        rain_w = max(3, size // 22)
        for rx_offset in [-size * 0.22, 0, size * 0.22]:
            rx = cx + rx_offset
            ry = cy + size * 0.20
            draw.line((rx, ry, rx - size * 0.08, ry + size * 0.22), fill=COLOR_BLACK, width=rain_w)
        if is_thunder:
            tx, ty = cx, cy + size * 0.20
            draw.line((tx + 3, ty, tx - 5, ty + 14), fill=COLOR_BLACK, width=3)
            draw.line((tx - 5, ty + 14, tx + 5, ty + 14), fill=COLOR_BLACK, width=3)
            draw.line((tx + 5, ty + 14, tx - 3, ty + 30), fill=COLOR_BLACK, width=3)
        return

    # 6. 雪天
    if is_snow:
        draw_cloud(cx, cy - size * 0.14, scale=0.88, fill_color=COLOR_WHITE)
        for sx_offset in [-size * 0.20, 0, size * 0.20]:
            sx = cx + sx_offset
            sy = cy + size * 0.28
            draw.line((sx - 6, sy, sx + 6, sy), fill=COLOR_BLACK, width=3)
            draw.line((sx, sy - 6, sx, sy + 6), fill=COLOR_BLACK, width=3)
        return

    # 7. 雾 / 霾
    if is_fog:
        line_w = max(3, size // 20)
        draw.line((cx - size * 0.38, cy - size * 0.18, cx + size * 0.38, cy - size * 0.18), fill=COLOR_BLACK, width=line_w)
        draw.line((cx - size * 0.45, cy, cx + size * 0.45, cy), fill=COLOR_BLACK, width=line_w)
        draw.line((cx - size * 0.32, cy + size * 0.18, cx + size * 0.32, cy + size * 0.18), fill=COLOR_BLACK, width=line_w)
        draw.line((cx - size * 0.22, cy + size * 0.34, cx + size * 0.22, cy + size * 0.34), fill=COLOR_BLACK, width=line_w)
        return

    draw_cloud(cx, cy, scale=0.92, fill_color=COLOR_WHITE)

# ==================== 5. 主绘制流程 ====================
def generate_calendar_dashboard():
    now_data, daily_data, city_name = fetch_weather()
    today_w = daily_data[0] if daily_data else {}
    tomorrow_w = daily_data[1] if len(daily_data) > 1 else {}
    after_w = daily_data[2] if len(daily_data) > 2 else {}

    now = datetime.now(BEIJING_TZ)
    lunar_cn, gz_year, animal, term_str = get_lunar_info(now)
    day_of_year = now.timetuple().tm_yday
    week_of_year = now.isocalendar()[1]

    img = Image.new("L", (WIDTH, HEIGHT), COLOR_WHITE)
    draw = ImageDraw.Draw(img)

    # 300 PPI 级高分字体梯度
    font_bar = load_font(30, bold=True)
    font_bar_sub = load_font(24)
    font_giant_day = load_font(190, bold=True)   # 震撼的超大公历日期
    font_date_title = load_font(42, bold=True)
    font_lunar_main = load_font(36, bold=True)
    font_lunar_sub = load_font(26)
    font_cal_week = load_font(24, bold=True)
    font_cal_day = load_font(26)
    
    font_bento_title = load_font(32, bold=True)
    font_temp_giant = load_font(90, bold=True)
    font_temp_deg = load_font(36, bold=True)
    font_weather_desc = load_font(42, bold=True)
    font_tag = load_font(24, bold=True)
    font_metric_k = load_font(24)
    font_metric_v = load_font(26, bold=True)

    PAD_X = 54

    # ---------------- 1. 顶部极简状态胶囊 (y: 35 ~ 115) ----------------
    draw.rounded_rectangle((PAD_X, 35, WIDTH - PAD_X, 115), radius=20, fill=COLOR_BLACK)
    draw.text((PAD_X + 28, 56), f"📍 {city_name}", fill=COLOR_WHITE, font=font_bar)
    lunar_tag = f"岁次 {gz_year} · 肖{animal} {term_str}"
    draw.text((PAD_X + 340, 60), lunar_tag, fill=225, font=font_bar_sub)
    draw.text((WIDTH - PAD_X - 220, 60), f"{now.strftime('%H:%M')} 更新", fill=180, font=font_bar_sub)

    # ---------------- 2. 上半区：万年历 Bento (y: 145 ~ 630) ----------------
    weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    week_str = weekdays[now.weekday()]
    month_str = f"{now.year}年 {now.month}月"

    # 左侧：公历大字撕历风格
    draw.text((PAD_X + 10, 145), month_str, fill=COLOR_BLACK, font=font_date_title)
    draw.text((PAD_X + 270, 155), f"·  {week_str}", fill=COLOR_GRAY_MID, font=font_lunar_sub)

    day_str = f"{now.day:02d}" if now.day < 10 else str(now.day)
    draw.text((PAD_X + 5, 185), day_str, fill=COLOR_BLACK, font=font_giant_day)

    draw.text((PAD_X + 15, 435), f"农历  {lunar_cn}", fill=COLOR_BLACK, font=font_lunar_main)
    draw.text((PAD_X + 15, 495), f"全年第 {day_of_year} 天  ·  第 {week_of_year} 周", fill=COLOR_GRAY_DARK, font=font_lunar_sub)
    draw.text((PAD_X + 15, 545), f"公历纪年: {now.strftime('%Y-%m-%d')}", fill=COLOR_GRAY_LIGHT, font=font_lunar_sub)

    # 中部分割竖线
    cal_mid_x = 645
    draw.line((cal_mid_x, 150, cal_mid_x, 610), fill=COLOR_BORDER, width=2)

    # 右侧：本月月历方阵
    cal_start_x = 690
    draw.text((cal_start_x, 145), "📅 本月日历", fill=COLOR_BLACK, font=font_date_title)

    cal_headers = ["一", "二", "三", "四", "五", "六", "日"]
    col_w = 70
    grid_top_y = 215

    for i, h in enumerate(cal_headers):
        draw.text((cal_start_x + i * col_w + 14, grid_top_y), h, fill=COLOR_GRAY_MID, font=font_cal_week)

    draw.line((cal_start_x, grid_top_y + 40, cal_start_x + 7 * col_w, grid_top_y + 40), fill=COLOR_BORDER, width=2)

    cal = calendar.Calendar(firstweekday=0)
    month_days = cal.monthdayscalendar(now.year, now.month)
    row_h = 56 if len(month_days) <= 5 else 48

    for r_idx, week in enumerate(month_days):
        for c_idx, d in enumerate(week):
            if d != 0:
                cx = cal_start_x + c_idx * col_w + 6
                cy = grid_top_y + 55 + r_idx * row_h
                if d == now.day:
                    draw.rounded_rectangle((cx - 4, cy - 4, cx + 52, cy + 38), radius=10, fill=COLOR_BLACK)
                    draw.text((cx + (8 if d < 10 else 2), cy + 2), str(d), fill=COLOR_WHITE, font=font_cal_day)
                else:
                    draw.text((cx + (8 if d < 10 else 2), cy + 2), str(d), fill=COLOR_BLACK, font=font_cal_day)

    # ---------------- 3. 中半区：今日实况 Bento 气象主看板 (y: 655 ~ 1125) ----------------
    bento_y = 655
    bento_h = 470
    bento_w = WIDTH - PAD_X * 2

    # 主 Bento 阴影与白色底板
    draw.rounded_rectangle((PAD_X + 4, bento_y + 4, PAD_X + bento_w + 4, bento_y + bento_h + 4), radius=22, fill=COLOR_SHADOW)
    draw.rounded_rectangle((PAD_X, bento_y, PAD_X + bento_w, bento_y + bento_h), radius=22, fill=COLOR_WHITE, outline=COLOR_BLACK, width=3)

    # 今日标签
    draw.rounded_rectangle((PAD_X + 30, bento_y + 30, PAD_X + 130, bento_y + 75), radius=8, fill=COLOR_BLACK)
    draw.text((PAD_X + 44, bento_y + 37), "今日实况", fill=COLOR_WHITE, font=font_tag)

    # 实况大字温度与现象
    cur_temp = str(now_data.get("temp", "--"))
    draw.text((PAD_X + 30, bento_y + 90), cur_temp, fill=COLOR_BLACK, font=font_temp_giant)

    try:
        t_len = draw.textlength(cur_temp, font=font_temp_giant)
    except AttributeError:
        t_len = len(cur_temp) * 55

    draw.text((PAD_X + 30 + t_len + 8, bento_y + 100), "℃", fill=COLOR_BLACK, font=font_temp_deg)

    weather_desc = now_data.get("text", "晴")
    draw.text((PAD_X + 30, bento_y + 205), weather_desc, fill=COLOR_BLACK, font=font_weather_desc)
    draw.text((PAD_X + 30, bento_y + 270), f"今日温差  {today_w.get('tempMin', '--')}° ~ {today_w.get('tempMax', '--')}°", fill=COLOR_GRAY_DARK, font=font_metric_v)

    # 右侧绘制 110px 顶级大矢量天气图标
    icon_code = now_data.get("icon", "100")
    draw_weather_icon(draw, icon_code, weather_desc, PAD_X + 340, bento_y + 120, size=120)

    # 实况右侧：6 个气象指标微型便当块 (3 列 x 2 行)
    metrics_x = PAD_X + 530
    draw.line((metrics_x - 30, bento_y + 30, metrics_x - 30, bento_y + bento_h - 30), fill=COLOR_BORDER, width=2)

    chips = [
        ("体感温度", f"{now_data.get('feelsLike', '--')} ℃"),
        ("相对湿度", f"{now_data.get('humidity', '--')} %"),
        ("风向风力", f"{now_data.get('windDir', '微风')} {now_data.get('windScale', '-')}级"),
        ("紫外线", f"{today_w.get('uvIndex', '-')} 指数"),
        ("日出时间", f"🌅 {today_w.get('sunrise', '--')}"),
        ("日落时间", f"🌇 {today_w.get('sunset', '--')}"),
    ]

    chip_col_w = 310
    chip_row_h = 135
    for idx, (mk, mv) in enumerate(chips):
        r = idx // 2
        c = idx % 2
        bx = metrics_x + c * chip_col_w
        by = bento_y + 40 + r * chip_row_h

        draw.rounded_rectangle((bx, by, bx + chip_col_w - 20, by + chip_row_h - 15), radius=12, fill=COLOR_BG_CARD)
        draw.text((bx + 20, by + 20), mk, fill=COLOR_GRAY_MID, font=font_metric_k)
        draw.text((bx + 20, by + 65), mv, fill=COLOR_BLACK, font=font_metric_v)

    # ---------------- 4. 下半区：明日与后天双列宽卡片 (y: 1155 ~ 1610) ----------------
    forecast_y = 1155
    forecast_h = 445
    card_gap = 30
    fc_card_w = (WIDTH - PAD_X * 2 - card_gap) // 2

    fc_meta = [
        {"title": "明天", "date": tomorrow_w.get("fxDate", "未来")[5:], "data": tomorrow_w},
        {"title": "后天", "date": after_w.get("fxDate", "未来")[5:], "data": after_w},
    ]

    for i, fc in enumerate(fc_meta):
        x1 = PAD_X + i * (fc_card_w + card_gap)
        x2 = x1 + fc_card_w
        d = fc["data"]

        draw.rounded_rectangle((x1 + 4, forecast_y + 4, x2 + 4, forecast_y + forecast_h + 4), radius=20, fill=COLOR_SHADOW)
        draw.rounded_rectangle((x1, forecast_y, x2, forecast_y + forecast_h), radius=20, fill=COLOR_WHITE, outline=COLOR_BORDER, width=2)

        # 头部日期标签
        draw.rounded_rectangle((x1 + 25, forecast_y + 25, x1 + 115, forecast_y + 70), radius=8, fill=COLOR_GRAY_DARK)
        draw.text((x1 + 37, forecast_y + 32), fc["title"], fill=COLOR_WHITE, font=font_tag)
        draw.text((x1 + 130, forecast_y + 35), fc["date"], fill=COLOR_GRAY_MID, font=font_metric_k)

        # 天气现象与气温
        f_text = d.get("textDay", "晴")
        draw.text((x1 + 25, forecast_y + 95), f_text, fill=COLOR_BLACK, font=font_bento_title)
        draw.text((x1 + 25, forecast_y + 155), f"{d.get('tempMin', '--')}° ~ {d.get('tempMax', '--')}°", fill=COLOR_BLACK, font=font_weather_desc)
        draw.text((x1 + 25, forecast_y + 225), f"夜间天气: {d.get('textNight', '晴')}", fill=COLOR_GRAY_MID, font=font_metric_k)

        # 右侧天气图标 (80px)
        f_icon = d.get("iconDay", "100")
        draw_weather_icon(draw, f_icon, f_text, x2 - 130, forecast_y + 110, size=95)

        draw.line((x1 + 25, forecast_y + 275, x2 - 25, forecast_y + 275), fill=COLOR_BORDER, width=1)

        # 辅助参数
        draw.text((x1 + 25, forecast_y + 295), f"白天风向: {d.get('windDirDay', '微风')} · {d.get('windScaleDay', '-')}级", fill=COLOR_GRAY_DARK, font=font_metric_k)
        draw.text((x1 + 25, forecast_y + 340), f"紫外线指数: {d.get('uvIndex', '-')}", fill=COLOR_GRAY_DARK, font=font_metric_k)
        draw.text((x1 + 25, forecast_y + 385), f"日出日落: {d.get('sunrise', '--')} / {d.get('sunset', '--')}", fill=COLOR_GRAY_DARK, font=font_metric_k)

    # ---------------- 5. 底部装饰 ----------------
    draw.text((WIDTH // 2 - 145, 1630), "Kobo Libra 2 · 300 PPI E-Ink Dashboard", fill=COLOR_GRAY_LIGHT, font=font_cal_week)

    # ---------------- 6. 保存导出 ----------------
    os.makedirs("archive", exist_ok=True)
    img.save("latest.png", format="PNG", optimize=True)
    print("🎉 成功为 Kobo Libra 2 生成 1264x1680 @ 300PPI 高清 Bento 看板: latest.png")

if __name__ == "__main__":
    generate_calendar_dashboard()
