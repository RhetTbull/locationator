#!/bin/bash

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
"dist/Locationator.app"

# move the DMG to the dist folder
test -f Locationator-Installer.dmg && mv Locationator-Installer.dmg dist/
