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

# ==================== 1. 屏幕与基础参数 (Kobo Glo 758x1024) ====================
WIDTH = 758
HEIGHT = 1024

# 显式使用北京时间 (UTC+8)，彻底解决 GitHub Actions 服务器默认 UTC 导致日期落后一天的 Bug
BEIJING_TZ = timezone(timedelta(hours=8))

# 环境变量读取与清洗
QWEATHER_KEY = os.getenv("QWEATHER_KEY", "").strip()
raw_host = os.getenv("QWEATHER_HOST", "").strip()
QWEATHER_HOST = re.sub(r'^https?://|/.*$', '', raw_host)
LOCATION_ID = os.getenv("LOCATION_ID", "101010100").strip()

# 纯黑白灰度配色（0 墨黑，255 纯白）
COLOR_WHITE = 255
COLOR_BLACK = 0
COLOR_GRAY_DARK = 65
COLOR_GRAY_LIGHT = 135
COLOR_BORDER = 190
COLOR_SHADOW = 225

CITY_MAP = {
    "101010100": "北京",
    "101020100": "上海",
    "101280101": "广州",
    "101280601": "深圳",
    "101070211": "大连 · 高新园区"
}

# ==================== 2. 和风天气数据拉取 ====================
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
        print(f"⚠️ 天气接口请求异常: {e}")

    # 兜底默认值
    if not now_data:
        now_data = {
            "temp": "--", "text": "阴", "icon": "104", "humidity": "--", "windScale": "-",
            "feelsLike": "--", "windDir": "微风", "pressure": "--"
        }
    if not daily_data:
        daily_data = [
            {"fxDate": "今天", "textDay": "阴", "iconDay": "104", "tempMax": "--", "tempMin": "--", "sunrise": "06:00", "sunset": "18:00", "uvIndex": "-"},
            {"fxDate": "明天", "textDay": "多云", "iconDay": "101", "tempMax": "--", "tempMin": "--", "windDirDay": "微风", "windScaleDay": "2", "uvIndex": "-"},
            {"fxDate": "后天", "textDay": "晴", "iconDay": "100", "tempMax": "--", "tempMin": "--", "windDirDay": "微风", "windScaleDay": "2", "uvIndex": "-"}
        ]

    return now_data, daily_data, city_name

# ==================== 3. 字体与农历稳健解析 ====================
def load_font(size, bold=False):
    """带自动降级防护的多路径字体加载"""
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
    """安全解析农历、属相与节气，彻底杜绝任何属性/方法混淆导致的报错"""
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
        print(f"⚠️ 历法解析警告: {e}")
        return "十月初八", "丙午年", "马", ""

# ==================== 4. 墨水屏专属：纯黑白矢量气象图标绘制引擎 ====================
def draw_weather_icon(draw, icon_code, text, x, y, size=64):
    """
    根据和风天气的 icon 代码与文字，在 (x, y) 处绘制尺寸为 size 的纯黑白矢量图形。
    0 噪点、0 渐变，纯依靠黑白线框和几何剪影实现印刷级质感。
    """
    code = str(icon_code)
    # 类别判定
    is_sunny = (code == "100") or ("晴" in text)
    is_cloudy = (code in ["101", "102", "103"]) or ("多云" in text)
    is_overcast = (code == "104") or ("阴" in text)
    is_rain = (code.startswith("3") or "雨" in text)
    is_snow = (code.startswith("4") or "雪" in text)
    is_fog = (code.startswith("5") or "雾" in text or "霾" in text)
    is_thunder = ("雷" in text)

    cx, cy = x + size // 2, y + size // 2

    # 1. 晴天 (Sun)
    if is_sunny and not is_cloudy:
        r = size * 0.22
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=COLOR_WHITE, outline=COLOR_BLACK, width=max(2, size // 20))
        # 8 根太阳光芒线
        ray_len = size * 0.12
        ray_dist = size * 0.32
        for i in range(8):
            angle = i * (math.pi / 4)
            x1 = cx + math.cos(angle) * ray_dist
            y1 = cy + math.sin(angle) * ray_dist
            x2 = cx + math.cos(angle) * (ray_dist + ray_len)
            y2 = cy + math.sin(angle) * (ray_dist + ray_len)
            draw.line((x1, y1, x2, y2), fill=COLOR_BLACK, width=max(2, size // 22))
        return

    # 2. 云朵基础辅助函数 (Cloud Silhouette)
    def draw_cloud(base_cx, base_cy, scale=1.0, fill_color=COLOR_WHITE):
        cw = size * 0.65 * scale
        ch = size * 0.38 * scale
        left = base_cx - cw / 2
        top = base_cy - ch / 2
        w = max(2, int(size // 22))

        # 主底部胶囊
        draw.rounded_rectangle((left, top + ch * 0.35, left + cw, top + ch * 0.95), radius=int(ch * 0.3), fill=fill_color, outline=COLOR_BLACK, width=w)
        # 顶部两个重叠圆形成凸起
        r1 = ch * 0.45
        r2 = ch * 0.35
        c1x, c1y = left + cw * 0.42, top + ch * 0.45
        c2x, c2y = left + cw * 0.72, top + ch * 0.55
        draw.ellipse((c1x - r1, c1y - r1, c1x + r1, c1y + r1), fill=fill_color, outline=COLOR_BLACK, width=w)
        draw.ellipse((c2x - r2, c2y - r2, c2x + r2, c2y + r2), fill=fill_color, outline=COLOR_BLACK, width=w)
        # 内部掏白消除交叉内线
        draw.ellipse((c1x - r1 + w, c1y - r1 + w, c1x + r1 - w, c1y + r1 - w), fill=fill_color)
        draw.ellipse((c2x - r2 + w, c2y - r2 + w, c2x + r2 - w, c2y + r2 - w), fill=fill_color)
        draw.rectangle((left + w, top + ch * 0.35 + w, left + cw - w, top + ch * 0.95 - w), fill=fill_color)

    # 3. 多云 (Sun behind cloud)
    if is_cloudy:
        # 左上角露出一半太阳
        sun_cx, sun_cy = cx - size * 0.15, cy - size * 0.15
        r = size * 0.18
        draw.ellipse((sun_cx - r, sun_cy - r, sun_cx + r, sun_cy + r), fill=COLOR_WHITE, outline=COLOR_BLACK, width=2)
        for i in range(5):
            angle = math.pi + i * (math.pi / 4)
            x1 = sun_cx + math.cos(angle) * (r + 2)
            y1 = sun_cy + math.sin(angle) * (r + 2)
            x2 = sun_cx + math.cos(angle) * (r + size * 0.08)
            y2 = sun_cy + math.sin(angle) * (r + size * 0.08)
            draw.line((x1, y1, x2, y2), fill=COLOR_BLACK, width=2)
        # 前方白底云朵覆盖
        draw_cloud(cx + size * 0.06, cy + size * 0.1, scale=0.88, fill_color=COLOR_WHITE)
        return

    # 4. 阴天 (Overcast Double Clouds)
    if is_overcast:
        # 后层实心黑细边云
        draw_cloud(cx - size * 0.1, cy - size * 0.12, scale=0.75, fill_color=COLOR_WHITE)
        # 前层白云
        draw_cloud(cx + size * 0.08, cy + size * 0.12, scale=0.85, fill_color=COLOR_WHITE)
        return

    # 5. 雨天 / 雷阵雨 (Rain / Thunder)
    if is_rain:
        draw_cloud(cx, cy - size * 0.12, scale=0.85, fill_color=COLOR_WHITE)
        # 绘制倾斜雨滴
        rain_w = max(2, size // 25)
        for rx_offset in [-size * 0.2, 0, size * 0.2]:
            rx = cx + rx_offset
            ry = cy + size * 0.2
            draw.line((rx, ry, rx - size * 0.08, ry + size * 0.18), fill=COLOR_BLACK, width=rain_w)
        if is_thunder:
            # 叠加小闪电
            tx, ty = cx, cy + size * 0.18
            draw.line((tx + 2, ty, tx - 4, ty + 10), fill=COLOR_BLACK, width=2)
            draw.line((tx - 4, ty + 10, tx + 4, ty + 10), fill=COLOR_BLACK, width=2)
            draw.line((tx + 4, ty + 10, tx - 2, ty + 22), fill=COLOR_BLACK, width=2)
        return

    # 6. 雪天 (Snow)
    if is_snow:
        draw_cloud(cx, cy - size * 0.12, scale=0.85, fill_color=COLOR_WHITE)
        for sx_offset in [-size * 0.18, 0, size * 0.18]:
            sx = cx + sx_offset
            sy = cy + size * 0.26
            # 绘制小雪花十字星
            draw.line((sx - 4, sy, sx + 4, sy), fill=COLOR_BLACK, width=2)
            draw.line((sx, sy - 4, sx, sy + 4), fill=COLOR_BLACK, width=2)
        return

    # 7. 雾 / 霾 (Fog / Mist)
    if is_fog:
        line_w = max(2, size // 22)
        draw.line((cx - size * 0.35, cy - size * 0.15, cx + size * 0.35, cy - size * 0.15), fill=COLOR_BLACK, width=line_w)
        draw.line((cx - size * 0.42, cy, cx + size * 0.42, cy), fill=COLOR_BLACK, width=line_w)
        draw.line((cx - size * 0.3, cy + size * 0.15, cx + size * 0.3, cy + size * 0.15), fill=COLOR_BLACK, width=line_w)
        draw.line((cx - size * 0.2, cy + size * 0.3, cx + size * 0.2, cy + size * 0.3), fill=COLOR_BLACK, width=line_w)
        return

    # 默认兜底：通用云朵
    draw_cloud(cx, cy, scale=0.9, fill_color=COLOR_WHITE)

# ==================== 5. 绘图主程序 ====================
def generate_calendar_dashboard():
    now_data, daily_data, city_name = fetch_weather()
    today_w = daily_data[0] if daily_data else {}
    tomorrow_w = daily_data[1] if len(daily_data) > 1 else {}
    after_w = daily_data[2] if len(daily_data) > 2 else {}

    now = datetime.now(BEIJING_TZ)
    lunar_cn, gz_year, animal, term_str = get_lunar_info(now)

    day_of_year = now.timetuple().tm_yday
    week_of_year = now.isocalendar()[1]

    # 初始化 8-bit 单通道灰度画布
    img = Image.new("L", (WIDTH, HEIGHT), COLOR_WHITE)
    draw = ImageDraw.Draw(img)

    # 字体准备
    font_bar = load_font(22, bold=True)
    font_sub_bar = load_font(18)
    font_giant_day = load_font(120, bold=True)   # 左侧撕历日期
    font_date_head = load_font(26, bold=True)
    font_lunar_main = load_font(24, bold=True)
    font_lunar_sub = load_font(19)
    font_cal_week = load_font(16, bold=True)
    font_cal_day = load_font(17)
    font_sec_title = load_font(22, bold=True)
    font_card_head = load_font(18, bold=True)

    # 天气专用字体规范
    font_temp_today = load_font(52, bold=True)   # 实况温度规范字号
    font_temp_unit = load_font(20, bold=True)    # ℃ 符号
    font_weather_title = load_font(24, bold=True) # 现象（阴、晴、多云）
    font_detail = load_font(17)                  # 明细项

    # ---------------- 1. 顶部 Header 状态栏 (0 ~ 80px) ----------------
    draw.rectangle((0, 0, WIDTH, 80), fill=COLOR_BLACK)
    draw.text((30, 26), f"📍 {city_name}", fill=COLOR_WHITE, font=font_bar)
    lunar_header = f"岁次{gz_year} · 属{animal} {term_str}"
    draw.text((230, 28), lunar_header, fill=220, font=font_sub_bar)
    draw.text((WIDTH - 170, 28), f"{now.strftime('%H:%M')} 更新", fill=190, font=font_sub_bar)

    # ---------------- 2. 上半区：极简万年历 (80 ~ 460px) ----------------
    weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    week_str = weekdays[now.weekday()]
    month_str = f"{now.year}年 {now.month}月"

    draw.text((35, 105), month_str, fill=COLOR_BLACK, font=font_date_head)
    draw.text((215, 109), f"·  {week_str}", fill=COLOR_GRAY_DARK, font=font_lunar_sub)

    # 撕历超大公历日期
    day_str = f"{now.day:02d}" if now.day < 10 else str(now.day)
    draw.text((32, 138), day_str, fill=COLOR_BLACK, font=font_giant_day)

    # 农历与纪年
    draw.text((35, 305), f"农历  {lunar_cn}", fill=COLOR_BLACK, font=font_lunar_main)
    draw.text((35, 348), f"第 {week_of_year} 周  ·  全年第 {day_of_year} 天", fill=COLOR_GRAY_DARK, font=font_lunar_sub)
    draw.text((35, 385), f"公历纪年: {now.strftime('%Y-%m-%d')}", fill=COLOR_GRAY_LIGHT, font=font_detail)

    # 纵向中线
    draw.line((395, 110, 395, 435), fill=COLOR_BORDER, width=2)

    # 右侧：本月日历矩阵 (支持 5 行与 6 行自适应)
    draw.text((425, 105), "📅 本月日历", fill=COLOR_BLACK, font=font_date_head)

    cal_headers = ["一", "二", "三", "四", "五", "六", "日"]
    grid_start_x = 425
    grid_start_y = 150
    col_w = 43

    for i, h in enumerate(cal_headers):
        draw.text((grid_start_x + i * col_w + 10, grid_start_y), h, fill=COLOR_GRAY_DARK, font=font_cal_week)

    draw.line((grid_start_x, grid_start_y + 28, grid_start_x + 7 * col_w, grid_start_y + 28), fill=COLOR_BORDER, width=1)

    cal = calendar.Calendar(firstweekday=0)
    month_days = cal.monthdayscalendar(now.year, now.month)
    row_h = 42 if len(month_days) <= 5 else 36  # 自适应 6 行月份

    for r_idx, week in enumerate(month_days):
        for c_idx, d in enumerate(week):
            if d != 0:
                cx = grid_start_x + c_idx * col_w + 5
                cy = grid_start_y + 36 + r_idx * row_h
                if d == now.day:
                    draw.rounded_rectangle((cx - 3, cy - 2, cx + 33, cy + 26), radius=6, fill=COLOR_BLACK)
                    draw.text((cx + (3 if d < 10 else 0), cy + 2), str(d), fill=COLOR_WHITE, font=font_cal_day)
                else:
                    draw.text((cx + (4 if d < 10 else 0), cy + 2), str(d), fill=COLOR_BLACK, font=font_cal_day)

    # 主水平分割线
    draw.line((30, 460, WIDTH - 30, 460), fill=COLOR_BLACK, width=2)

    # ---------------- 3. 下半区：气象三列卡片看板 (480 ~ 990px) ----------------
    draw.text((30, 480), "🌤️ 气象看板 (今天及未来两日)", fill=COLOR_BLACK, font=font_sec_title)

    card_y = 515
    pad_x = 30
    gap_x = 15
    card_w = (WIDTH - pad_x * 2 - gap_x * 2) // 3  # 精确等分 222px
    card_h = 460

    cards_meta = [
        {"label": "今天", "date": "实况", "w": today_w, "is_today": True},
        {"label": "明天", "date": tomorrow_w.get("fxDate", "未来")[5:], "w": tomorrow_w, "is_today": False},
        {"label": "后天", "date": after_w.get("fxDate", "未来")[5:], "w": after_w, "is_today": False},
    ]

    for i, item in enumerate(cards_meta):
        x1 = pad_x + i * (card_w + gap_x)
        x2 = x1 + card_w
        w_obj = item["w"]

        # 阴影与圆角底框
        draw.rounded_rectangle((x1 + 3, card_y + 3, x2 + 3, card_y + card_h + 3), radius=10, fill=COLOR_SHADOW)
        draw.rounded_rectangle((x1, card_y, x2, card_y + card_h), radius=10, fill=COLOR_WHITE,
                               outline=COLOR_BLACK if item["is_today"] else COLOR_BORDER,
                               width=2 if item["is_today"] else 1)

        # 标签栏
        tag_bg = COLOR_BLACK if item["is_today"] else COLOR_GRAY_LIGHT
        draw.rounded_rectangle((x1 + 15, card_y + 15, x1 + 75, card_y + 44), radius=4, fill=tag_bg)
        draw.text((x1 + 24, card_y + 18), item["label"], fill=COLOR_WHITE, font=font_card_head)
        draw.text((x1 + 88, card_y + 20), item["date"], fill=COLOR_GRAY_DARK, font=font_detail)

        # ---------------- 今日实况卡片（左数据 + 右大图标） ----------------
        if item["is_today"]:
            cur_temp = str(now_data.get("temp", "--"))
            draw.text((x1 + 16, card_y + 58), cur_temp, fill=COLOR_BLACK, font=font_temp_today)

            try:
                temp_width = draw.textlength(cur_temp, font=font_temp_today)
            except AttributeError:
                temp_width = len(cur_temp) * 28

            draw.text((x1 + 16 + temp_width + 4, card_y + 62), "℃", fill=COLOR_BLACK, font=font_temp_unit)

            text_desc = now_data.get("text", "晴")
            draw.text((x1 + 16, card_y + 124), text_desc, fill=COLOR_BLACK, font=font_weather_title)
            draw.text((x1 + 16, card_y + 165), f"{w_obj.get('tempMin', '--')} ~ {w_obj.get('tempMax', '--')}℃", fill=COLOR_GRAY_DARK, font=font_detail)

            # 👉 右上角绘制 64x64 纯矢量实况天气图标
            icon_code = now_data.get("icon", "100")
            draw_weather_icon(draw, icon_code, text_desc, x2 - 76, card_y + 70, size=62)

            # 统一对齐分割线
            draw.line((x1 + 15, card_y + 198, x2 - 15, card_y + 198), fill=COLOR_BORDER, width=1)

            # 均匀行间距排布
            draw.text((x1 + 16, card_y + 215), f"体感温度: {now_data.get('feelsLike', '--')}℃", fill=COLOR_BLACK, font=font_detail)
            draw.text((x1 + 16, card_y + 247), f"相对湿度: {now_data.get('humidity', '--')}%", fill=COLOR_BLACK, font=font_detail)
            draw.text((x1 + 16, card_y + 279), f"风向: {now_data.get('windDir', '微风')}", fill=COLOR_BLACK, font=font_detail)
            draw.text((x1 + 16, card_y + 311), f"风力: {now_data.get('windScale', '-')}级", fill=COLOR_BLACK, font=font_detail)
            draw.text((x1 + 16, card_y + 343), f"紫外线: {w_obj.get('uvIndex', '-')}", fill=COLOR_GRAY_DARK, font=font_detail)
            draw.text((x1 + 16, card_y + 375), f"气压: {now_data.get('pressure', '--')} hPa", fill=COLOR_GRAY_DARK, font=font_detail)
            draw.text((x1 + 16, card_y + 407), f"日落: {w_obj.get('sunset', '--')}", fill=COLOR_GRAY_DARK, font=font_detail)

        # ---------------- 明日/后天预报卡片（左预报 + 右中图标） ----------------
        else:
            weather_desc = w_obj.get("textDay", "晴")
            draw.text((x1 + 16, card_y + 62), weather_desc, fill=COLOR_BLACK, font=font_weather_title)
            draw.text((x1 + 16, card_y + 115), f"{w_obj.get('tempMin', '--')} ~ {w_obj.get('tempMax', '--')}℃", fill=COLOR_BLACK, font=font_date_head)
            draw.text((x1 + 16, card_y + 165), f"夜间: {w_obj.get('textNight', '晴')}", fill=COLOR_GRAY_DARK, font=font_detail)

            # 👉 右上角绘制 50x50 预报天气图标
            icon_code = w_obj.get("iconDay", "100")
            draw_weather_icon(draw, icon_code, weather_desc, x2 - 68, card_y + 75, size=52)

            # 统一对齐分割线
            draw.line((x1 + 15, card_y + 198, x2 - 15, card_y + 198), fill=COLOR_BORDER, width=1)

            draw.text((x1 + 16, card_y + 215), f"白天风向: {w_obj.get('windDirDay', '微风')}", fill=COLOR_GRAY_DARK, font=font_detail)
            draw.text((x1 + 16, card_y + 247), f"风力等级: {w_obj.get('windScaleDay', '-')}级", fill=COLOR_GRAY_DARK, font=font_detail)
            draw.text((x1 + 16, card_y + 279), f"紫外线: {w_obj.get('uvIndex', '-')}", fill=COLOR_GRAY_DARK, font=font_detail)
            draw.text((x1 + 16, card_y + 311), f"日出时间: {w_obj.get('sunrise', '--')}", fill=COLOR_GRAY_DARK, font=font_detail)
            draw.text((x1 + 16, card_y + 343), f"日落时间: {w_obj.get('sunset', '--')}", fill=COLOR_GRAY_DARK, font=font_detail)

    # 底部说明
    draw.text((WIDTH // 2 - 100, 995), "Kobo Glo E-Ink Calendar", fill=180, font=font_sub_bar)

    # ---------------- 6. 导出并保存 ----------------
    os.makedirs("archive", exist_ok=True)
    archive_path = f"archive/{now.strftime('%Y%m%d_%H%M')}.png"

    img.save("latest.png", format="PNG", optimize=True)
    img.save(archive_path, format="PNG", optimize=True)
    print(f"🎉 成功生成带墨水屏气象矢量图标的万年历看板: latest.png 和 {archive_path}")

if __name__ == "__main__":
    generate_calendar_dashboard()
