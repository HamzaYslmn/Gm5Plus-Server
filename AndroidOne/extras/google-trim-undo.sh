#!/usr/bin/env bash
# GM5 Plus sunucu: Google stack trim'ini GERI AL (reversible).
# PC'den calistir:  bash google-trim-undo.sh
# (Root/adb.exe kullanir; cihaz adb ile bagli olmali.)
set -e
ADB="$(dirname "$0")/../../Root/adb.exe"
[ -x "$ADB" ] || ADB="adb"

PKGS=(
  com.google.android.gms
  com.google.android.gsf
  com.google.android.gms.location.history
  com.google.android.gms.policy_sidecar_aps
  com.android.vending
  com.google.android.apps.turbo
  com.google.android.feedback
  com.google.android.partnersetup
  com.google.android.onetimeinitializer
  com.google.android.syncadapters.contacts
  com.google.android.apps.pixelmigrate
  com.google.android.printservice.recommendation
  com.google.android.markup
  com.google.android.as
  com.google.android.apps.messaging
  com.google.android.ims
)
echo "Google stack geri aciliyor (Play Store + GMS dahil)..."
for p in "${PKGS[@]}"; do
  echo "  enable $p"
  "$ADB" shell pm enable "$p" 2>&1 | tr -d '\r'
done
echo "Bitti. GMS senkronu icin reboot onerilir: $ADB reboot"
echo "NOT: setupwizard bilerek kapali birakildi (geri acmak setup'i geri getirir)."
