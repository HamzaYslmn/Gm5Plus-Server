#!/system/bin/sh
# GM5 tek ayar script'i: CPU idle freq + core_ctl + ZRAM + swappiness + ekran (W/H/DPI).
# /data/adb/gm-tune.conf'u okur, ROM varsayilanini override eder (post_boot.sh'tan SONRA).
# Kurulum: bu dosya -> /data/adb/service.d/  (chmod 755) + gm-tune.conf -> /data/adb/
# Canli ekran (reboot'suz):  sh .../91-gm-tune.sh res 810 1440 240   |   res reset (stok)
CONF=/data/adb/gm-tune.conf

apply_res() {  # $1=W $2=H $3=DPI   | veya  $1=reset
    if [ "$1" = "reset" ]; then
        wm size reset; wm density reset; return
    fi
    [ -n "$1" ] && [ -n "$2" ] && wm size "${1}x${2}"
    [ -n "$3" ] && wm density "$3"
}

# Manuel ekran modu:  ... res W H DPI   |   ... res reset
if [ "$1" = "res" ]; then apply_res "$2" "$3" "$4"; exit 0; fi

# --- boot modu ---
[ -f "$CONF" ] || exit 0
i=0
until [ "$(getprop sys.boot_completed)" = "1" ] || [ "$i" -ge 60 ]; do sleep 2; i=$((i + 1)); done
sleep 3
. "$CONF"

# CPU idle taban freq
set_min() {  # $1=cpu  $2=deger
    d=/sys/devices/system/cpu/cpu$1/cpufreq
    [ -d "$d" ] || return
    case "$2" in
        hw)  cat "$d/cpuinfo_min_freq" > "$d/scaling_min_freq" 2>/dev/null ;;
        "")  : ;;
        *)   echo "$2" > "$d/scaling_min_freq" 2>/dev/null ;;
    esac
}
set_min 0 "$LITTLE_MIN"
set_min 4 "$BIG_MIN"
[ -n "$LITTLE_MIN_CPUS" ] && echo "$LITTLE_MIN_CPUS" > /sys/devices/system/cpu/cpu0/core_ctl/min_cpus 2>/dev/null
[ -n "$BIG_MIN_CPUS" ]    && echo "$BIG_MIN_CPUS"    > /sys/devices/system/cpu/cpu4/core_ctl/min_cpus 2>/dev/null
[ -n "$SWAPPINESS" ]      && echo "$SWAPPINESS"      > /proc/sys/vm/swappiness 2>/dev/null

# ZRAM yeniden boyutlandir (sadece deger verildiyse ve farkliysa)
if [ -n "$ZRAM_MB" ]; then
    bytes=$((ZRAM_MB * 1024 * 1024))
    cur=$(cat /sys/block/zram0/disksize 2>/dev/null)
    if [ "$cur" != "$bytes" ]; then
        swapoff /dev/block/zram0 2>/dev/null
        echo 1 > /sys/block/zram0/reset 2>/dev/null
        echo "$bytes" > /sys/block/zram0/disksize 2>/dev/null
        mkswap /dev/block/zram0 >/dev/null 2>&1 && swapon /dev/block/zram0 -p 32758 2>/dev/null
    fi
fi

# Ekran cozunurluk + DPI (sadece deger verildiyse)
apply_res "$RES_W" "$RES_H" "$RES_DPI"
