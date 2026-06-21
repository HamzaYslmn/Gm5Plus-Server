# GM 5 Plus — Termux Sunucu Kurulumu (otonom, 2026-06-21)

Cihaz: GM 5 Plus (shamrock), Android One Experience 0616 (Android 10 **arm64**), kernel 3.10.84.
Hepsi `adb` + `run-as` (Termux github-debug = debuggable) ile otonom yapıldı. **Hiçbiri root gerektirmedi** (gm-tune hariç, aşağıda).

## ✅ Tamamlananlar — hepsi doğrulandı

| İş | Durum | Not |
|---|---|---|
| Setup wizard baypas | ✅ | `settings put global device_provisioned 1` + setupwizard disabled — PIN sormadı |
| Resmi Termux (arm64) | ✅ | `termux-app v0.118.3+github-debug_arm64-v8a` + `termux-api v0.53.0` + `termux-boot v0.8.1` (eşleşen imza, GitHub) |
| openssh / htop / fastfetch / python / uv | ✅ | uv **0.11.23**, htop 3.5.1, fastfetch 2.64.2, python 3.13.13 |
| **uv çalışıyor** | ✅ | venv + `uv pip install` + import test geçti. **Varsayılan hardlink** (Termux'ta cache+venv aynı FS → hızlı, az disk). `UV_LINK_MODE=copy` KALDIRILDI — gereksizdi (yavaş/kopya); farklı FS'te uv zaten otomatik copy'e düşer |
| **sshd port 8022** | ✅ | PC ed25519 anahtarı `authorized_keys`'te → **parolasız** |
| **`ssh gm5plus`** | ✅ | PC `~/.ssh/config`: HostName 192.168.1.149, Port 8022. **Soğuk reboot sonrası test edildi, çalışıyor** |
| **Cihazla başlama** | ✅ | termux-boot → `~/.termux/boot/start-server.sh` (`termux-wake-lock; sshd`). Reboot testi: sshd kendiliğinden başladı |
| **adb kalıcı** | ✅ | Magisk `service.d/60-adb-enable.sh` her boot adb'yi açar (reboot sonrası adb döndü) |
| **`system` komutu** | ✅ | **Textual TUI** (`extras/system.py`): canlı paneller (SYSTEM cpu/gpu/temp/trend, NETWORK throughput/sinyal/disk, BATTERY, SENSORS) + **KONTROL butonları** (🔦flash toggle, RGB bildirim-LED kırmızı/yeşil/mavi/kapat, titreşim). Toast: 2sn, aynı anda max 3. Tuşlar: f=flash, r=LED kapat, v=titreşim, q=çıkış. `system --no-tui`=ANSI shell pano, `system --once`=tek kare. `pip install textual` gerekir (kuruldu). Paneller: SYSTEM, NETWORK, BATTERY, SENSORS (+türetilmiş pusula/yükseklik), TOUCH (multitouch+hall, root). Kontrol root (su) + termux-api. **`sensors` komutu kaldırıldı** — hepsi `system`'e taşındı. |
| fastfetch login'de | ✅ | `.bashrc`'de — `ssh gm5plus` ile girince çıkar |
| RAM trim | ✅ | **Google stack kapatıldı** (reversible): GMS, GSF, Play Store, location.history, turbo, feedback, partnersetup, syncadapters, pixelmigrate + as/messaging/ims. YouTube **Chrome'da** çalışıyor (GMS gerekmez, test edildi). Undo: `extras/google-trim-undo.sh`. Kazanç ~65MB RAM (hesapsız GMS küçüktü) + arka plan wakeup/senkron kalktı (pil). Korundu: Chrome, WebView, NexusLauncher, klavye. |
| Depolama | ✅ | /data **21.7GB boş** (repartition sayesinde) — projeler için bol |
| mDNS (gm5plus.local) | ⚠️ engelli | aşağıda — Android multicast filtresi |

## Nasıl kullanılır
```bash
ssh gm5plus            # PC'den bağlan (parolasız, ed25519)
sensors                # tüm sensörler + termal + batarya
htop                   # işlemciler (8×A53)
fastfetch              # sistem özeti
uv venv .venv && . .venv/bin/activate && uv pip install <paket>
```
Termux/sshd cihaz açılınca otomatik başlar; `ssh gm5plus` her zaman hazır (aynı WiFi'de).
IP değişirse: `~/.ssh/config`'te `HostName`'i güncelle veya `adb shell ip addr show wlan0`.

## ✅ gm-tune (güç/termal tuning) — DEPLOY EDİLDİ + doğrulandı
Magisk "Shell" su izni verildi → `adb shell su` ile root çalışıyor (uid=0). gm-tune deploy edildi:
`/data/adb/service.d/91-gm-tune.sh` (0755, root, `adb_data_file:s0`) + `/data/adb/gm-tune.conf`. Her boot çalışır.
**Doğrulandı (uygulandı):**
- cpu0 `scaling_min_freq=960000`=`cpuinfo_min_freq` → idle min freq hw tabanında (güç ↓)
- `scaling_max=1516800` (1.5GHz) **dokunulmadı** → **peak performans korundu**
- core_ctl `min_cpus` little=1/big=0 → idle'da **3/8 çekirdek açık** (güç ↓, ısı ↓)
- RES boş (0616 zaten 810p + dokunmatik dead-zone riski)
Ayarları değiştir: `/data/adb/gm-tune.conf` düzenle + reboot (veya `su -c "sh /data/adb/service.d/91-gm-tune.sh"`).

## mDNS (gm5plus.local) — neden çalışmadı, root gelince denenecek
zeroconf (Python, `extras/mdns-gm5plus.py`) kuruldu ve **doğru çalışıyor**: kaydoluyor, 5353'e bind ediyor,
`gm5plus._ssh._tcp.local. → 192.168.1.149:8022` yayınlıyor. **Ama Android, `WifiManager.MulticastLock`
olmadan WiFi multicast paketlerini donanım seviyesinde filtreler** — daemon mDNS sorgularını alamıyor,
cevap veremiyor. Kesin kanıt: **cihaz kendi yayınını bile göremedi** (cihaz-içi zeroconf self-query =
LOCAL-NOT-FOUND), yani ağ/WARP değil, cihazda kesiliyor. Termux bu lock'u root/uygulama desteği olmadan alamıyor
(avahi'nin de çalışmama sebebi bu). Cython değil pure-python (`SKIP_CYTHON=1`) kuruldu — Cython build binary-incompatible çıkıyordu.

**Root'la denendi (2026-06-21) → çıkmaz:** `iwpriv` bu ROM'da **yok**; `/sys/module/wlan/parameters`'da multicast filtre knob'u yok. `iw` var ama mDNS multicast lock'u için kullanılamıyor. Qualcomm WCNSS'te multicast filtresi firmware/HAL seviyesinde, shell'den erişilemiyor. **mDNS bu cihazda pratik değil.**

**Çözüm = router'da DHCP rezervasyonu** (en temiz, ponytail): WiFi MAC **`fc:3d:93:7d:1a:72`**'yi router'da `192.168.1.149`'a sabitle → IP hiç değişmez → `ssh gm5plus` (IP ile) kalıcı stabil. mDNS'e gerek kalmaz.

## Önemli cihaz notu — dokunmatik dead-zone
Ekranın **alt kısmı dokunmatik algılamıyor** (panel/render uyuşmazlığı, splash taşmasıyla aynı kök).
Geçici çözüm kuruldu: **J+Touch** (`com.bs.smarttouch.gp`, accessibility+overlay açık) — yüzen kontrol, dead-zone'u bypass eder.
Asıl çözüm (ilerisi): display/touch çözünürlük uyuşmazlığını `wm size` native'e sabitleyerek dene (root/adb ile).

## Rust-tabanlı Python paketleri (pydantic-core, polars, orjson, watchfiles…)
uv/pip bunları kaynaktan derler (PyPI'da Android wheel yok). 3 engel + çözümü (hepsi yapıldı, kalıcı):
1. **"Rust not found / target not supported by rustup"** → `pkg install rust` (Termux rust, `aarch64-linux-android` native; rustup KULLANMA).
2. **maturin "Failed to determine Android API level"** → `export ANDROID_API_LEVEL=24` (`.bashrc`'ye eklendi, kalıcı).
3. **linker "no such file ...rcgu.o"** → yarıda kesilen build'in bayat target dir'i. Çözüm: `rm -rf ~/.cache/uv/sdists-v9/pypi/<paket>` + temiz derle.
`patchelf` de kurulu (maturin için). FastAPI test edildi: `fastapi 0.138 + pydantic 2.13 + uvicorn` çalışıyor (`~/app`).

**Neden derleme çok uzun sürer (diğer kullanıcılara not):** PyPI'da Android (`aarch64-linux-android`/bionic) için wheel YOK — sadece manylinux/glibc var → uv/pip **kaynaktan derler**, indirmez. pydantic-core devasa bir Rust crate'i, **release/optimize** modda, bu **2016 CPU'da (MSM8952, A53 ~1.5GHz)** ~20 dk (modern PC'de ~1-2dk; ~10-20× yavaş). Her başarısız deneme neredeyse baştan derler. **İlk seferden sonra cache'li** → tekrar derlenmez. Sabırlı ol, `nohup ... &` ile arka planda çalıştır, OOM için 2GB zram zaten var.

## Termux-API (sensörler vb.) — diğer kullanıcılara not
İKİ parça gerekir, ikisi de: (1) **termux-api APK** (`com.termux.api`, GitHub'dan, termux-app ile aynı imza) kurulu + (2) **`pkg install termux-api`** (CLI köprüsü). Biri eksikse `termux-sensor`/`termux-battery-status` çalışmaz/asılır. APK `-g` ile kurulduğundan izinler verili. Kullanım: `termux-sensor -l` (liste), `termux-sensor -a -n 1` (tek okuma), `termux-sensor -s "Ad" -d 1000` (sürekli akış). Canlı pano `sensors` bunu arka planda akıtır. **mDNS/multicast** termux-api ile DEĞİL — Android multicast lock (root) gerektirir, çalışmıyor (yukarı bak).

## Anahtar dosyalar
- PC ssh: `~/.ssh/config` (Host gm5plus), anahtar `~/.ssh/id_ed25519`
- Termux kurulum script'i (yeniden kullanılabilir): `AndroidOne/extras/termux-server-setup.sh`
- gm-tune: `AndroidOne/extras/service.d/91-gm-tune.sh` + `gm-tune.conf`
- adb-kalıcı: `AndroidOne/extras/service.d/60-adb-enable.sh` (deploy edilmiş)
