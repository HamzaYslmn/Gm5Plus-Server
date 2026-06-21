#!/data/data/com.termux/files/usr/bin/bash
# GM5 Plus (shamrock) Termux sunucu kurulumu - otonom, non-interactive.
# Termux icinde calisir. run-as ile yerlestirilip env'li calistirilir.
export PREFIX=/data/data/com.termux/files/usr
export HOME=/data/data/com.termux/files/home
export PATH=$PREFIX/bin:$PATH
export LD_LIBRARY_PATH=$PREFIX/lib
export TMPDIR=$PREFIX/tmp
export LANG=en_US.UTF-8
export DEBIAN_FRONTEND=noninteractive
APT='-o Dpkg::Options::=--force-confold -o Dpkg::Options::=--force-confdef'

echo "### SETUP START $(date) ###"

# --- paketler ---
apt-get update -y $APT
pkg install -y $APT openssh htop fastfetch termux-api python avahi nss-mdns uv procps termux-services || true

# --- SSH: PC public key, port 8022 ---
mkdir -p $HOME/.ssh && chmod 700 $HOME/.ssh
cat > $HOME/.ssh/authorized_keys <<'PUBKEY'
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIKJCSuxz/HT2r6o3+pCU4/9rGbiM9ndWPJ7hluyG8OgR gm5-access
PUBKEY
chmod 600 $HOME/.ssh/authorized_keys
grep -q '^Port 8022' $PREFIX/etc/ssh/sshd_config 2>/dev/null || echo 'Port 8022' >> $PREFIX/etc/ssh/sshd_config

# --- uv: VARSAYILAN (hardlink) birak — Termux'ta cache+venv ayni dosya sisteminde,
# hardlink calisir (hizli, az disk). UV_LINK_MODE=copy GEREKMEZ (yavas + kopya).
# Sadece venv farkli FS'teyse (orn /sdcard) uv otomatik copy'e duser, sorun degil.
touch $HOME/.bashrc

# --- avahi: gm5plus.local ---
AC=$PREFIX/etc/avahi/avahi-daemon.conf
if [ -f "$AC" ]; then
  sed -i 's/^#*host-name=.*/host-name=gm5plus/' "$AC"
  grep -q '^host-name=' "$AC" || sed -i '/\[server\]/a host-name=gm5plus' "$AC"
  sed -i 's/^#*domain-name=.*/domain-name=local/' "$AC"
fi

# --- sensors komutu: tum Android sensorleri + termal + batarya ---
cat > $PREFIX/bin/sensors <<'SENS'
#!/data/data/com.termux/files/usr/bin/bash
echo "================ ANDROID SENSORS (liste) ================"
termux-sensor -l 2>/dev/null
echo
echo "================ SENSOR OKUMALARI (tek atis) ============"
termux-sensor -a -n 1 2>/dev/null
echo
echo "================ TERMAL BOLGELER ========================"
for z in /sys/class/thermal/thermal_zone*; do
  [ -e "$z/temp" ] || continue
  printf "%-30s %s\n" "$(cat "$z/type" 2>/dev/null)" "$(cat "$z/temp" 2>/dev/null)"
done
echo
echo "================ BATARYA ================================"
termux-battery-status 2>/dev/null
SENS
chmod +x $PREFIX/bin/sensors

# --- boot autostart: cihazla sshd + avahi ---
mkdir -p $HOME/.termux/boot
cat > $HOME/.termux/boot/start-server.sh <<'BOOT'
#!/data/data/com.termux/files/usr/bin/sh
termux-wake-lock
sshd
avahi-daemon --no-drop-root --no-rlimits -D 2>/dev/null
BOOT
chmod +x $HOME/.termux/boot/start-server.sh

# --- login'de fastfetch ---
grep -q 'fastfetch' $HOME/.bashrc || printf '\ncommand -v fastfetch >/dev/null && fastfetch\n' >> $HOME/.bashrc

# --- servisleri simdi baslat ---
termux-wake-lock 2>/dev/null
pkill sshd 2>/dev/null; sshd
avahi-daemon --no-drop-root --no-rlimits -D 2>/dev/null || true

echo "### VERSIYONLAR ###"
echo "uv:        $(uv --version 2>&1 | head -1)"
echo "htop:      $(htop --version 2>&1 | head -1)"
echo "fastfetch: $(fastfetch --version 2>&1 | head -1)"
echo "python:    $(python --version 2>&1)"
echo "ssh user:  $(whoami)"
echo "sshd port: $(grep -m1 '^Port' $PREFIX/etc/ssh/sshd_config 2>/dev/null)"
echo "sshd pid:  $(pgrep sshd | tr '\n' ' ')"
echo "avahi pid: $(pgrep avahi-daemon | tr '\n' ' ')"
echo "### SETUP DONE $(date) ###"
touch $HOME/SETUP_DONE
