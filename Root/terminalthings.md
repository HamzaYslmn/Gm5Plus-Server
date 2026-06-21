# GM5 Plus — Terminal Kurulumu (Termux) ve Araçlar

Rootlu GM5 Plus (`shamrock`, Android 8.0, armv7 32-bit, kernel 3.10.84).
`ssh gm5plus` → doğrudan **Termux** (kullanıcı `u0_a94`, root için `sudo`).
Termux:Boot sshd'yi her açılışta başlatır (port 8022).

> Not: Eskiden SSH otomatik chroot'a giriyordu; kaldırıldı — artık Termux'a düşer.
> uv dahil her şey Termux'ta çalışıyor; chroot gerekmiyor (kurulumu en altta, lazım olursa).

## ⭐ uv (Termux'ta native)
Engel: Android 8 SELinux, `untrusted_app`'e hardlink yasaklıyor; uv hardlink ister →
"Could not acquire lock". Çözüm: Magisk SELinux kuralı (kalıcı: `/data/adb/post-fs-data.d/10-uv-hardlink.sh`):
```sh
/data/adb/magisk/magiskpolicy --live "allow untrusted_app app_data_file file link"
```
> Güvenlik: kural tüm uygulamalara hardlink izni verir. Geri al: dosyayı sil + reboot.
```bash
pkg install uv python
uv venv --python python        # armv7'de sistem python3 sart
uv pip install requests
uv run python script.py
```

## zram (1GB swap)
`zram` komut değil, swap aygıtı. 1GB aktif, otomatik (`/data/adb/service.d/zram.sh`).
```bash
swapon --show
```
Kurulum (root): `swapoff` → `echo 1 > reset` → `echo lzo > comp_algorithm` (lz4 YOK!) →
`echo 1073741824 > disksize` → `mkswap` → `swapon`.

## htop / fastfetch
```bash
pkg install htop fastfetch
sudo htop            # /proc kisitli -> sudo
fastfetch            # acilista da gelir
```

## sensors — tam pano (Termux)
`sensors` (alias: `bash ~/.config/sensors.sh`). termux-api ile batarya + CPU + RAM + ağ +
**hareket sensörleri + pusula + ışık** (chroot'ta olmayan).

## termux-api — Android donanımı
```bash
pkg install termux-api
termux-battery-status ; termux-location ; termux-wifi-connectioninfo
sudo pm grant com.termux.api android.permission.CAMERA
termux-camera-photo -c 0 ~/foto.jpg
```

## Donanım erişimi
| Yol | Ne erişir |
|---|---|
| sysfs (`sudo`) | fener, titreşim, LED, batarya, sıcaklık |
| termux-api | kamera, hareket sensörleri, GPS, mikrofon, WiFi |
| Erişilemez | kameranın `/dev/video*` (Qualcomm HAL) |
```sh
echo 200 > /sys/class/timed_output/vibrator/enable     # titret
echo 255 > /sys/class/leds/torch-light0/brightness     # fener AC (0=kapat)
```

# (Opsiyonel) chroot Debian — lazım olursa kurulum

Tam Debian/apt ekosistemi istersen. Tüm adımlar Termux'ta `sudo` ile:

**1) rootfs indir:**
```bash
pkg install proot-distro
proot-distro install debian
sudo mv $PREFIX/var/lib/proot-distro/containers/debian/rootfs /data/local/debian
pkg uninstall proot-distro proot
```
**2) launcher** `/data/local/debian-enter.sh` (root:root, chmod 700):
```sh
#!/system/bin/sh
export PATH=/system/bin:/system/xbin:$PATH
R=/data/local/debian
T="${1:-${TERM:-xterm}}"
grep -q " $R/proc " /proc/mounts || mount -t proc  proc  "$R/proc"
grep -q " $R/sys "  /proc/mounts || mount -t sysfs sysfs "$R/sys"
grep -q " $R/dev "  /proc/mounts || mount -o rbind /dev   "$R/dev"
{ for d in $(getprop net.dns1) $(getprop net.dns2); do
    case "$d" in *:*|*%*|"") : ;; *) echo "nameserver $d" ;; esac
  done; echo "nameserver 1.1.1.1"; echo "nameserver 8.8.8.8"; } > "$R/etc/resolv.conf"
exec env -i /system/bin/toybox chroot "$R" /usr/bin/env -i \
  HOME=/root TERM="$T" PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
  setsid -c /bin/bash --login
```
**3) apt'i aç** (chroot içinde): `echo 'APT::Sandbox::User "root";' > /etc/apt/apt.conf.d/99no-sandbox && apt update`
**4) giriş:** `alias debian='sudo /data/local/debian-enter.sh "$TERM"'` → `debian` / `exit`

**Tuzaklar:** `env -i` (LD_PRELOAD bozuyor) · `setsid -c` (job control) · DNS scoped-IPv6 filtresi ·
apt `_apt` sandbox · **Termux'ta `sudo dpkg/apt/pkg` ÇALIŞTIRMA** (SELinux context bozar; düzeltme:
`sudo chcon -R u:object_r:app_data_file:s0:c512,c768 $PREFIX/var`).

**Silme:** `sudo rm -rf /data/local/debian /data/local/debian-enter.sh` + alias.
**Sınır:** chroot'ta hareket sensörü/kamera/GPS yok (Android API gerekir).

## Sınırlar
Docker / 64-bit (armv8) / yeni kernel YOK — kernel 3.10 + armv7, Qualcomm kaynağı kapalı.
Gerçek Docker için: VPS + SSH.