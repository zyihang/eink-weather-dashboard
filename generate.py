import os
import re
import requests
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

# ==================== 1. 屏幕与画布配置 (Kobo Glo 竖屏 758x1024) ====================
WIDTH = 758
HEIGHT = 1024

QWEATHER_KEY = os.getenv("QWEATHER_KEY", "").strip()

# 自动清洗 Host（防止带协议头或斜杠导致报错）
raw_host = os.getenv("QWEATHER_HOST", "").strip()
QWEATHER_HOST = re.sub(r'^https?://|/.*$', '', raw_host)

LOCATION_ID = os.getenv("LOCATION_ID", "101010100")

# 纯黑白墨水屏配色系统（基于 16 级灰阶）
COLOR_WHITE = 255      # 背景白
COLOR_BLACK = 0        # 纯黑字/纯黑底
COLOR_GRAY_DARK = 60   # 深灰（次级信息）
COLOR_GRAY_LIGHT = 140 # 浅灰（标签与注释）
COLOR_BORDER = 200     # 边框与阴影

CITY_MAP = {
    "101010100": "北京",
    "101020100": "上海",
    "101280101": "广州",
    "101280601": "深圳",
    "101070211": "大连 · 高新园区"
}

# ==================== 2. 数据获取 ====================
def fetch_weather():
    global LOCATION_ID
    raw_id = os.getenv("LOCATION_ID", "101010100")
    clean_id = re.sub(r'[^0-9]', '', str(raw_id))

    print(f"==========================================")
    print(f"🔍 环境变量检测 -> HOST: '{QWEATHER_HOST}' | 城市ID: '{clean_id}'")
    print(f"==========================================")

    # 城市名匹配
    if "101070211" in clean_id:
        city_name = "大连 · 高新园区"
    elif clean_id in CITY_MAP:
        city_name = CITY_MAP[clean_id]
    else:
        city_name = "未知区域"
        if QWEATHER_HOST and QWEATHER_KEY:
            try:
                geo_url = f"https://{QWEATHER_HOST}/v2/city/lookup?location={clean_id}&key={QWEATHER_KEY}"
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

    if not QWEATHER_HOST:
        print("❌ 错误: 未检测到 QWEATHER_HOST，请检查 GitHub Actions 环境变量！")

    now_url = f"https://{QWEATHER_HOST}/v7/weather/now?location={clean_id}&key={QWEATHER_KEY}"
    daily_url = f"https://{QWEATHER_HOST}/v7/weather/3d?location={clean_id}&key={QWEATHER_KEY}"

    now_data = {}
    daily_data = []

    try:
        r_now = requests.get(now_url, timeout=10).json()
        print(f"📡 实时天气响应 code: {r_now.get('code')}")
        if r_now.get("code") == "200":
            now_data = r_now.get("now", {})
            print(f"✅ 实时天气获取成功: 当前温度 {now_data.get('temp')}℃, 天气 {now_data.get('text')}")
        else:
            print(f"❌ 实时天气返回错误: {r_now}")

        r_daily = requests.get(daily_url, timeout=10).json()
        print(f"📡 三天预报响应 code: {r_daily.get('code')}")
        if r_daily.get("code") == "200":
            daily_data = r_daily.get("daily", [])
            print("✅ 三天天气预报获取成功")
        else:
            print(f"❌ 三天预报返回错误: {r_daily}")
    except Exception as e:
        print(f"❌ API 请求异常: {e}")

    # 兜底测试数据
    if not now_data:
        now_data = {"temp": "--", "text": "晴", "humidity": "--", "windScale": "-", "feelsLike": "--"}
    if not daily_data:
        daily_data = [
            {"fxDate": datetime.now().strftime("%Y-%m-%d"), "textDay": "晴", "tempMax": "--", "tempMin": "--", "uvIndex": "-", "sunrise": "06:00", "sunset": "18:00"},
            {"fxDate": "未来", "textDay": "多云", "tempMax": "--", "tempMin": "--"},
            {"fxDate": "未来", "textDay": "晴", "tempMax": "--", "tempMin": "--"}
        ]

    return now_data, daily_data, city_name

# ==================== 3. 字体与阴影卡片辅助 ====================
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

def draw_shadow_card(draw, x1, y1, x2, y2, radius=12):
    """黑白墨水屏定制阴影卡片（带 16 级灰阶柔和阴影与白底实线框）"""
    # 底部阴影偏移
    draw.rounded_rectangle((x1 + 3, y1 + 3, x2 + 3, y2 + 3), radius=radius, fill=220)
    # 卡片纯白主体与黑色边框
    draw.rounded_rectangle((x1, y1, x2, y2), radius=radius, fill=COLOR_WHITE, outline=COLOR_BORDER, width=2)

# ==================== 4. 绘图主体逻辑 ====================
def generate_image():
    now_data, daily_data, city_name = fetch_weather()
    today = daily_data[0] if daily_data else {}
    tomorrow = daily_data[1] if len(daily_data) > 1 else {}
    after_tomorrow = daily_data[2] if len(daily_data) > 2 else {}

    # 1. 创建灰度画布（灰阶 "L" 模式）
    img = Image.new("L", (WIDTH, HEIGHT), COLOR_WHITE)
    draw = ImageDraw.Draw(img)

    # 2. 字体定义
    font_title = load_font(26, bold=True)
    font_sub = load_font(20)
    font_card_title = load_font(22, bold=True)
    font_big_temp = load_font(100, bold=True)
    font_weather_text = load_font(34, bold=True)
    font_detail = load_font(20)
    font_tag = load_font(16, bold=True)

    # 3. 顶部 Header 状态栏 (原版的黑底反白设计，竖屏加高到 100px)
    draw.rectangle((0, 0, WIDTH, 100), fill=COLOR_BLACK)

    now = datetime.now()
    weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    date_str = f"{now.strftime('%Y-%m-%d')}  {weekdays[now.weekday()]}"

    # 左侧城市与当前日期
    draw.text((30, 20), f"📍 {city_name}", fill=COLOR_WHITE, font=font_title)
    draw.text((30, 60), date_str, fill=190, font=font_sub)

    # 右侧实时更新标记
    draw.text((WIDTH - 210, 60), f"更新于 {now.strftime('%H:%M')}", fill=190, font=font_sub)

    # 4. 核心 2x2 宫格卡片布局（自适应 758x1024 竖屏）
    PAD_X = 30
    GAP_X = 20
    PAD_Y = 120
    GAP_Y = 20

    CARD_W = (WIDTH - PAD_X * 2 - GAP_X) // 2       # 每张卡片宽约 339
    CARD_H = (HEIGHT - PAD_Y - 40 - GAP_Y) // 2      # 每张卡片高约 422

    # 四个卡片的坐标
    # [卡片1: 实时天气] [卡片2: 今日概况]
    # [卡片3: 明天天气] [卡片4: 后天天气]
    c1 = (PAD_X, PAD_Y, PAD_X + CARD_W, PAD_Y + CARD_H)
    c2 = (PAD_X + CARD_W + GAP_X, PAD_Y, PAD_X + CARD_W * 2 + GAP_X, PAD_Y + CARD_H)
    c3 = (PAD_X, PAD_Y + CARD_H + GAP_Y, PAD_X + CARD_W, PAD_Y + CARD_H * 2 + GAP_Y)
    c4 = (PAD_X + CARD_W + GAP_X, PAD_Y + CARD_H + GAP_Y, PAD_X + CARD_W * 2 + GAP_X, PAD_Y + CARD_H * 2 + GAP_Y)

    # ---------------- 卡片 1: 实时天气 ----------------
    draw_shadow_card(draw, *c1)
    # 反白标签块
    draw.rounded_rectangle((c1[0] + 20, c1[1] + 20, c1[0] + 90, c1[1] + 50), radius=4, fill=COLOR_BLACK)
    draw.text((c1[0] + 30, c1[1] + 25), "实况", fill=COLOR_WHITE, font=font_tag)
    draw.text((c1[0] + 105, c1[1] + 24), "当前天气", fill=COLOR_BLACK, font=font_card_title)

    # 超大当前温度
    temp_val = str(now_data.get("temp", "--"))
    draw.text((c1[0] + 25, c1[1] + 80), temp_val, fill=COLOR_BLACK, font=font_big_temp)
    draw.text((c1[0] + 25 + len(temp_val) * 58 + 5, c1[1] + 95), "℃", fill=COLOR_BLACK, font=font_card_title)

    draw.text((c1[0] + 25, c1[1] + 205), now_data.get("text", "晴"), fill=COLOR_BLACK, font=font_weather_text)

    # 详细参数
    draw.line((c1[0] + 25, c1[1] + 265, c1[2] - 25, c1[1] + 265), fill=COLOR_BORDER, width=1)
    draw.text((c1[0] + 25, c1[1] + 285), f"体感温度: {now_data.get('feelsLike', '--')}℃", fill=COLOR_GRAY_DARK, font=font_detail)
    draw.text((c1[0] + 25, c1[1] + 325), f"相对湿度: {now_data.get('humidity', '--')}%", fill=COLOR_GRAY_DARK, font=font_detail)
    draw.text((c1[0] + 25, c1[1] + 365), f"风向风力: {now_data.get('windDir', '微风')} {now_data.get('windScale', '-')}级", fill=COLOR_GRAY_DARK, font=font_detail)

    # ---------------- 卡片 2: 今日概况 ----------------
    draw_shadow_card(draw, *c2)
    draw.rounded_rectangle((c2[0] + 20, c2[1] + 20, c2[0] + 90, c2[1] + 50), radius=4, fill=COLOR_BLACK)
    draw.text((c2[0] + 30, c2[1] + 25), "今天", fill=COLOR_WHITE, font=font_tag)
    draw.text((c2[0] + 105, c2[1] + 24), "全日概览", fill=COLOR_BLACK, font=font_card_title)

    draw.text((c2[0] + 25, c2[1] + 85), f"最高: {today.get('tempMax', '--')}℃", fill=COLOR_BLACK, font=font_card_title)
    draw.text((c2[0] + 25, c2[1] + 125), f"最低: {today.get('tempMin', '--')}℃", fill=COLOR_GRAY_DARK, font=font_card_title)
    draw.text((c2[0] + 25, c2[1] + 175), f"天气状况: {today.get('textDay', '晴')}", fill=COLOR_BLACK, font=font_detail)

    draw.line((c2[0] + 25, c2[1] + 225, c2[2] - 25, c2[1] + 225), fill=COLOR_BORDER, width=1)
    draw.text((c2[0] + 25, c2[1] + 245), f"🌅 日出: {today.get('sunrise', '--')}", fill=COLOR_GRAY_DARK, font=font_detail)
    draw.text((c2[0] + 25, c2[1] + 285), f"🌇 日落: {today.get('sunset', '--')}", fill=COLOR_GRAY_DARK, font=font_detail)
    draw.text((c2[0] + 25, c2[1] + 325), f"紫外线指数: {today.get('uvIndex', '-')}", fill=COLOR_GRAY_DARK, font=font_detail)
    draw.text((c2[0] + 25, c2[1] + 365), f"大气压强: {now_data.get('pressure', '--')} hPa", fill=COLOR_GRAY_DARK, font=font_detail)

    # ---------------- 卡片 3: 明天天气 ----------------
    draw_shadow_card(draw, *c3)
    draw.rounded_rectangle((c3[0] + 20, c3[1] + 20, c3[0] + 90, c3[1] + 50), radius=4, fill=COLOR_GRAY_LIGHT)
    draw.text((c3[0] + 30, c3[1] + 25), "明日", fill=COLOR_WHITE, font=font_tag)
    draw.text((c3[0] + 105, c3[1] + 24), tomorrow.get('fxDate', '未来'), fill=COLOR_BLACK, font=font_card_title)

    draw.text((c3[0] + 25, c3[1] + 90), tomorrow.get('textDay', '晴'), fill=COLOR_BLACK, font=font_weather_text)
    draw.text((c3[0] + 25, c3[1] + 160), f"温度: {tomorrow.get('tempMin', '--')} ~ {tomorrow.get('tempMax', '--')}℃", fill=COLOR_BLACK, font=font_card_title)

    draw.line((c3[0] + 25, c3[1] + 230, c3[2] - 25, c3[1] + 230), fill=COLOR_BORDER, width=1)
    draw.text((c3[0] + 25, c3[1] + 260), f"夜间天气: {tomorrow.get('textNight', '晴')}", fill=COLOR_GRAY_DARK, font=font_detail)
    draw.text((c3[0] + 25, c3[1] + 305), f"风向: {tomorrow.get('windDirDay', '微风')}", fill=COLOR_GRAY_DARK, font=font_detail)
    draw.text((c3[0] + 25, c3[1] + 350), f"紫外线: {tomorrow.get('uvIndex', '-')}", fill=COLOR_GRAY_DARK, font=font_detail)

    # ---------------- 卡片 4: 后天天气 ----------------
    draw_shadow_card(draw, *c4)
    draw.rounded_rectangle((c4[0] + 20, c4[1] + 20, c4[0] + 90, c4[1] + 50), radius=4, fill=COLOR_GRAY_LIGHT)
    draw.text((c4[0] + 30, c4[1] + 25), "后天", fill=COLOR_WHITE, font=font_tag)
    draw.text((c4[0] + 105, c4[1] + 24), after_tomorrow.get('fxDate', '未来'), fill=COLOR_BLACK, font=font_card_title)

    draw.text((c4[0] + 25, c4[1] + 90), after_tomorrow.get('textDay', '晴'), fill=COLOR_BLACK, font=font_weather_text)
    draw.text((c4[0] + 25, c4[1] + 160), f"温度: {after_tomorrow.get('tempMin', '--')} ~ {after_tomorrow.get('tempMax', '--')}℃", fill=COLOR_BLACK, font=font_card_title)

    draw.line((c4[0] + 25, c4[1] + 230, c4[2] - 25, c4[1] + 230), fill=COLOR_BORDER, width=1)
    draw.text((c4[0] + 25, c4[1] + 260), f"夜间天气: {after_tomorrow.get('textNight', '晴')}", fill=COLOR_GRAY_DARK, font=font_detail)
    draw.text((c4[0] + 25, c4[1] + 305), f"风向: {after_tomorrow.get('windDirDay', '微风')}", fill=COLOR_GRAY_DARK, font=font_detail)
    draw.text((c4[0] + 25, c4[1] + 350), f"紫外线: {after_tomorrow.get('uvIndex', '-')}", fill=COLOR_GRAY_DARK, font=font_detail)

    # 5. 归档与保存
    os.makedirs("archive", exist_ok=True)
    archive_path = f"archive/{now.strftime('%Y%m%d_%H%M')}.png"

    # 纯 8-bit 单通道灰度保存（墨水屏秒加载，体积极小）
    img.save("latest.png", format="PNG", optimize=True)
    img.save(archive_path, format="PNG", optimize=True)
    print(f"🎉 成功生成 Kobo Glo 专属黑白天气图片 (758x1024): latest.png 和 {archive_path}")

if __name__ == "__main__":
    generate_image()
