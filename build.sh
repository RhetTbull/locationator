#!/bin/sh

# Build, sign and package Locationator as a DMG file for release
# this requires create-dmg: `brew install create-dmg` to install

# build with py2app
echo "Cleaning up old build files..."
test -d dist && rm -rf dist/
test -d build && rm -rf build/

echo "Running py2app"
python3 setup.py py2app

# sign with ad-hoc certificate (if you have an Apple Developer ID, you can use your developer certificate instead)
# for the app to send AppleEvents to other apps, it needs to be signed and include the
# com.apple.security.automation.apple-events entitlement in the entitlements file
# --force: force signing even if the app is already signed
# --deep: recursively sign all embedded frameworks and plugins
# --options=runtime: Preserve the hardened runtime version
# --entitlements: use specified the entitlements file
# -s -: sign the code at the path(s) given using this identity; "-" means use the ad-hoc certificate
echo "Signing with codesign"
codesign \
  --force \
  --deep \
  --options=runtime \
  --entitlements=script.entitlements entitlements.plist \
  -s - \
  dist/Locationator.app

exit 0

# create installer DMG
# to add a background image to the DMG, add the following to the create-dmg command:
#   --background "installer_background.png" \
echo "Creating DMG"
test -f Locationator-Installer.dmg && rm Locationator-Installer.dmg
create-dmg \
  --volname "Locationator Installer" \
  --volicon "icon.icns" \
  --window-pos 200 120 \
  --window-size 800 400 \
  --icon-size 100 \
  --icon "Locationator.app" 200 190 \
  --hide-extension "Locationator.app" \
  --app-drop-link 600 185 \
  "Locationator-Installer.dmg" \
  "dist/"
