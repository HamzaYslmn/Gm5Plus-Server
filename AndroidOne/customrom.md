# GM 5 Plus (shamrock) — Android One Experience (hazır derleme)

> Not: `buildnotes.md` (kendi derlememizin notları) **silindi** — artık kendi build'imizi değil,
> topluluğun **hazır derlediği temiz ROM**'u kuruyoruz. Bu dosya o hazır ROM'un kaydı.

## Ne kuruyoruz
- **ROM:** Android One Experience (PixelExperience 10 tabanlı), **Android 10**.
- **Cihaz:** General Mobile GM 5 Plus — kod adı **shamrock** (MSM8952 / Snapdragon 617, A53×8, Adreno 405, 3GB RAM).
- **Mimari:** **arm64 (AArch64)** — 64-bit ROM, 2. mimari olarak 32-bit (cortex-a53). Kernel **3.10, ARM64**.
- **GApps:** **DAHİL** (tam Google: GMS Core, Play Store, GSF, Dialer, Chrome…). "Google'sız" değil. RAM için sonradan kısılabilir (`pm disable-user`).

## Kaynak
- Wiki: <https://github.com/GM-AndroidOne-Archive/Android-One-Experience-Project/wiki/General-Mobile-GM-5-Plus>
- İndirilen dosya (Telegram üzerinden alındı): Google Drive
  <https://drive.google.com/file/d/1h_zHbvudiQIE3_a1pH_hbZOoiEBWFLW0/view?usp=drive_link>

## SHA-256 (indirdiğin doğru/temiz dosya mı — doğrula)

| Dosya | Boyut | SHA-256 |
|---|---|---|
| **Q.GM5P.0616-packages.tar** (tüm paket) | 844.756.480 | `98DFB7B9BCFF4FBC6DF7BF7882AEA50CD25DD638D686CCA5AC9A8237645040E4` |
| androidone_shamrock-Q.GM5P.0616-release1.zip (ROM) | 819.405.352 | `408E761F223E4E5A3965D9A071C9F7D265A060073E2F13FEA949A31B6FCE3ED5` |
| GM5Plus-Partition-Resizer.zip | 251.465 | `F5189F25DFE11B82E8D1622F1625819B9C2BAB160B0E48991DC53B7E33A33BB0` |
| twrp-3.7.0_9-0-shamrock.img | 25.096.192 | `75FEFD739D755635222187E4F5472E15C769319EA832CB11D1458410413C5C38` |

**Doğrulama (Windows PowerShell):**
```powershell
Get-FileHash .\Q.GM5P.0616-packages.tar -Algorithm SHA256
```
**Linux/Mac:**
```bash
sha256sum Q.GM5P.0616-packages.tar
```
Çıkan değer yukarıdakiyle **birebir aynıysa** dosya bozulmamış/değiştirilmemiştir.

## Güvenlik taraması — TEMİZ ✅
Kurulan imaj recovery'den statik tarandı (2026-06-21), backdoor/trojan/casus yazılım **bulunmadı**:

- Önyüklü APK envanteri: hepsi standart AOSP / PixelExperience / Qualcomm / Moto + **resmi** GApps.
- init.rc / addon.d / build.prop / odm-vendor init: temiz (curl/wget/IP/gizli su/exec yok).
- Gömülü su/superuser yok (sadece sonradan eklediğimiz Magisk). /etc/hosts hijack yok. Rogue CA yok.
- **APK imza doğrulaması (en kritik):**
  - GMS Core / Play Store / GoogleServicesFramework → SHA1 `38918A45…CED5788` = **Google'ın resmi imza sertifikası** → kurcalanmamış, gerçek Google paketleri.
  - NexusLauncher → gerçek Google (nexuslauncher) anahtarı.
  - SystemUI / Settings → AOSP public **test-key** (`27196E38…`) — resmi olmayan ROM'larda **normal**; ikisi de aynı cert (tutarlı). Tek güvenlik notu: platform imzası güven kökü değil → dışarıdan platform-imzalı APK yandan yükleme.
- boot ramdisk: Magisk "Stock boot image detected" → önceden enjekte edilmiş gizli root yok.

## Kurulum (özet — bu cihazda REPARTITION şart)
ROM büyük partition için derlenmiş; **stok partition'a kurulmaz** (system 3.2GB / vendor 524MB ister).

1. Bootloader **unlock** (custom ROM için şart). Recovery = **OrangeFox** (img "twrp-…" adında), geçici: `fastboot boot twrp-3.7.0_9-0-shamrock.img`.
2. OrangeFox'ta **GM5Plus-Partition-Resizer.zip** flash → yeni aboot + `parted` ile system→3.2GB / vendor→524MB / userdata→24.8GB. (Tek seferlik; otomatik reboot eder.)
3. Tekrar `fastboot boot` ile OrangeFox'a gir. Wipe: data + cache + dalvik (+ system/vendor format).
4. **ROM zip** flash: `adb shell twrp install /sdcard/<rom>.zip` (imza doğrulama kapalı: `twrp set tw_signed_zip_verify 0`). ROM ayrıca `boot.img` + `splash.img` yazar (boot logosu da düzelir).
5. (İsteğe bağlı) **Magisk** flash (root): `twrp install /sdcard/magisk.zip`.
6. `adb reboot` → ilk açılış (5-15 dk normal, dex2oat derler).

Partition boyutları (resizer sonrası, doğrulandı): system **3.221.453.312**, vendor **524.083.712**, userdata **24.792.732.160**.

## Wiki'deki özellikler (geliştiricinin notları)
- **Yeni ARM64 kernel** → 2016 cihazda kararlılık/performans artışı.
- **Aggressive Power HAL 2.0** → Snapdragon 617 için güç yönetimi + uyarlanabilir çekirdek kontrolü.
- **Ekran 810p'ye düşürülmüş** → arayüz takılması ve ısınmayı azaltmak için.
- Eski **Google Kamera** sürümü (AOSP kamera yerine, daha iyi HDR).
- **Hızlı şarj** tam çözülmüş (9V/2A adaptör desteği). GPS iyileştirmeleri. Fazla diller kaldırılmış.
- **Şifreleme (encryption) kapalı** (kurulumda zorluk çıkardığı için).
- Uyarı: bootloader **unlock** gerekir (kilitliyken kullanılamaz).

## Kalıcı ADB (USB debugging) — `extras/service.d/60-adb-enable.sh`

Bu ROM'da ilk açılışta **Setup Wizard portrait'e kilitli** + ekranın **alt kısmı dokunmatik dead-zone**
(panel/render uyuşmazlığı) → "İleri" butonuna basılamıyor, setup geçilemiyor. Çözüm: **ADB'yi kalıcı aç**,
sonra **scrcpy ile mouse**'la (dead-zone'u bypass eder, input event'i her koordinata enjekte eder) setup'ı geç.

**Neden boot script'i:** `adb_enabled`'ı offline `settings_global.xml` düzenleyerek açmak **tutmuyor** —
SettingsProvider boot'ta dosyayı yeniden yazıp değişikliği geri alıyor (ve `id`'leri değiştiriyor). Doğru yol
framework üzerinden `settings put`; Magisk service.d (root) bunu her boot'ta uygular → **kalıcı**.

`extras/service.d/60-adb-enable.sh`:
```sh
until [ "$(getprop sys.boot_completed)" = "1" ]; do sleep 2; done
sleep 5
settings put global adb_enabled 1
```
**adb_keys YAZILMAZ** — bağlanan bilgisayar, telefon ekranındaki "Allow USB debugging" onayıyla yetkilendirilir
(cihaza özel önceden-paylaşılan anahtar girilmez; ilk onaydan sonra kalıcı yetkili).

**Onay penceresini hiç görmeden geçmek (opsiyonel):** Ekranda OK'a basamıyorsan (alt dead-zone'a denk
gelirse) onayı tamamen atlamanın **tek yolu**, kendi bilgisayarının **public** adb anahtarını cihaza önceden
koymak. Bu anahtar gizli/parola değil — sadece **o makineyi** önceden güvenilir yapar:
```bash
# recovery'de, /data mount edip:
adb push ~/.android/adbkey.pub /data/misc/adb/adb_keys      # Windows: C:\Users\<sen>\.android\adbkey.pub
adb shell 'chown system:shell /data/misc/adb/adb_keys; \
           chmod 0640 /data/misc/adb/adb_keys; \
           chcon u:object_r:adb_data_file:s0 /data/misc/adb/adb_keys'
adb reboot
```
Sonuç: açılışta `adb devices` doğrudan `device` (unauthorized değil), pencere hiç çıkmaz. Onay penceresi
zaten "hiçbir anahtar önceden güvenilir değil" diye çıkar; bu dosya o boşluğu doldurur.

**Kurulum (recovery'den, /data mount edip):**
```bash
adb push 60-adb-enable.sh /data/adb/service.d/60-adb-enable.sh
adb shell 'chmod 0755 /data/adb/service.d/60-adb-enable.sh; \
           chown root:root /data/adb/service.d/60-adb-enable.sh; \
           chcon u:object_r:adb_data_file:s0 /data/adb/service.d/60-adb-enable.sh'
adb reboot
```
Açılış + ~10-15 sn sonra USB debugging açık. Bağlan → ekranda onayla ("Always allow") → `scrcpy` ile sür.
> Aynı kalıp diğer runtime ayarları için de geçerli (`extras/service.d/91-gm-tune.sh` = CPU/zram/ekran).
> Magisk root şart (bu pakette ROM'dan sonra ayrıca flash'lanır).

## Yedek (sigorta)
- `AndroidOne/backup/` tam firmware dd (47/47 sha256 doğrulandı) + `backup/data/` (Termux). Bootloop → `fastboot flash` / dd ile stok'a dön.
