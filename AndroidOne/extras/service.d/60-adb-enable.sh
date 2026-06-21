#!/system/bin/sh
# USB debugging'i KALICI olarak ac (her boot'ta framework uzerinden).
# Offline settings_*.xml duzenlemesi SettingsProvider tarafindan boot'ta GERI ALINIR;
# o yuzden `settings put` ile dogru yoldan, boot_completed sonrasi uygulanir.
# adb_keys YAZILMAZ -> baglanan bilgisayar telefon ekranindaki onayla yetkilendirilir
# (cihaza ozel onceden-paylasilan anahtar girilmez).
# Kurulum: bu dosya -> /data/adb/service.d/  (chmod 0755, root:root, con u:object_r:adb_data_file:s0)
until [ "$(getprop sys.boot_completed)" = "1" ]; do sleep 2; done
sleep 5
settings put global adb_enabled 1
