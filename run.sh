#!/bin/sh

# ==================== 配置项 ====================
IMAGE_URL="https://raw.githubusercontent.com/zyihang/eink-weather-dashboard/main/latest.png"
SLEEP_INTERVAL=21600  # 6小时唤醒一次

WORK_DIR="/mnt/onboard/weather"
IMG_TMP="${WORK_DIR}/temp.png"
IMG_NOW="${WORK_DIR}/latest.png"
FBINK="${WORK_DIR}/fbink"

# 背光硬件节点
LIGHT_NODE="/sys/class/backlight/mxc_msp430.0/brightness"
# 备用节点（个别固件可能在 lm3630 或类似目录）
[ ! -f "$LIGHT_NODE" ] && LIGHT_NODE=$(ls /sys/class/backlight/*/brightness 2>/dev/null | head -n 1)

# ================= 智能灯光策略配置 =================
# 0 = 关闭，1~100 = 亮度百分比
set_light_by_time() {
    # 获取当前小时 (00 ~ 23)
    CURRENT_HOUR=$(date +%H | sed 's/^0//')
    [ -z "$CURRENT_HOUR" ] && CURRENT_HOUR=12

    # 策略设置：
    if [ "$CURRENT_HOUR" -ge 7 ] && [ "$CURRENT_HOUR" -lt 19 ]; then
        # 1. 白天 (07:00 ~ 18:59)：自然光足够，关灯极度省电
        TARGET_BRIGHTNESS=0
        echo "☀️ 白天时段: 关闭背光"
    elif [ "$CURRENT_HOUR" -ge 19 ] && [ "$CURRENT_HOUR" -lt 23 ]; then
        # 2. 傍晚/入睡前 (19:00 ~ 22:59)：开启 20% 柔和伴睡灯
        TARGET_BRIGHTNESS=20
        echo "🌙 傍晚时段: 开启柔和夜灯 (亮度 20%)"
    else
        # 3. 深夜 (23:00 ~ 06:59)：关灯防晃眼并深度节能
        TARGET_BRIGHTNESS=0
        echo "🌌 深夜时段: 关闭背光"
    fi

    # 写入硬件节点
    if [ -f "$LIGHT_NODE" ]; then
        echo "$TARGET_BRIGHTNESS" > "$LIGHT_NODE"
    fi
}
# ===================================================

chmod +x "$FBINK"
cd "$WORK_DIR" || exit 1

# 阻止原生 Nickel 界面抢占
pkill -STOP nickel 2>/dev/null

$FBINK -q -c -m -t "正在启动万年历系统..." 2>/dev/null

while true; do
    echo "=== [$(date)] 硬件 RTC 唤醒 ==="

    # 1. 开启网络
    insmod /drivers/ntx_otp.ko 2>/dev/null
    insmod /drivers/wifi.ko 2>/dev/null
    ifconfig wlan0 up 2>/dev/null
    wlarm_le -i eth0 up 2>/dev/null
    /sbin/wifi-enable.sh 2>/dev/null

    # 2. 等待连接 (最多 25 秒)
    NET_OK=0
    for i in $(seq 1 12); do
        sleep 2
        if ping -c 1 223.5.5.5 >/dev/null 2>&1 || ping -c 1 114.114.114.114 >/dev/null 2>&1; then
            NET_OK=1
            echo "✅ Wi-Fi 联机成功"
            break
        fi
    done

    # 3. 下载与墨水屏刷新
    if [ $NET_OK -eq 1 ]; then
        echo "⬇️ 正在拉取云端看板..."
        if command -v curl >/dev/null 2>&1; then
            curl -s -L -k --connect-timeout 10 -m 20 "$IMAGE_URL" -o "$IMG_TMP"
        else
            wget -q --no-check-certificate -T 15 -O "$IMG_TMP" "$IMAGE_URL"
        fi

        if [ -s "$IMG_TMP" ]; then
            mv "$IMG_TMP" "$IMG_NOW"
            echo "🖼️ 正在刷入电子墨水屏..."
            $FBINK -q -c -w -g "$IMG_NOW"
        fi
    else
        echo "❌ Wi-Fi 超时，保持原状"
    fi

    # 4. 彻底切断 Wi-Fi
    /sbin/wifi-disable.sh 2>/dev/null
    wlarm_le -i eth0 down 2>/dev/null
    ifconfig wlan0 down 2>/dev/null

    # 5. 💡 执行智能灯光策略（根据当前时间调整前光）
    set_light_by_time

    # 6. 设置硬件 RTC 唤醒闹钟并进入休眠
    NOW=$(date +%s)
    WAKEUP=$((NOW + SLEEP_INTERVAL))
    echo 0 > /sys/class/rtc/rtc0/wakealarm
    echo "$WAKEUP" > /sys/class/rtc/rtc0/wakealarm

    echo "⚡ 挂起休眠中..."
    sync
    echo mem > /sys/power/state

    # 唤醒后继续
    sleep 2
done
