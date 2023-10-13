"""
This is a setup.py script generated by py2applet

Usage:
    python setup.py py2app
"""

from setuptools import setup

# The version number; do not change this manually! It is updated by bumpversion (https://github.com/c4urself/bump2version)
__version__ = "0.0.1"

# The file that contains the main application
APP = ["src/locationator.py"]

# Include additional python modules here; probably not the best way to do this
# but I couldn't figure out how else to get py2app to include modules in the src/ folder
DATA_FILES = [
    "src/icon_white.png",
    "src/icon_black.png",
    "src/loginitems.py",
    "src/utils.py",
]

# These values will be included by py2app into the Info.plist file in the App bundle
# See https://developer.apple.com/documentation/bundleresources/information_property_list?language=objc
# for more information
PLIST = {
    # LSUIElement tells the OS that this app is a background app that doesn't appear in the Dock
    "LSUIElement": True,
    # CFBundleShortVersionString is the version number that appears in the App's About box
    "CFBundleShortVersionString": __version__,
    # CFBundleVersion is the build version (here we use the same value as the short version)
    "CFBundleVersion": __version__,
    # NSAppleEventsUsageDescription is the message that appears when the app asks for permission to send Apple events
    "NSAppleEventsUsageDescription": "Locationator needs permission to send AppleScript events to add itself to Login Items.",
    # NSLocationWhenInUseUsageDescription is the message that appears when the app asks for permission to use location services
    "NSLocationWhenInUseUsageDescription": "Locationator needs access to your location to detect your current location and to perform reverse geocoding.",
    # NSServices is a list of services that the app provides that will appear in the Services menu
    # For more information on NSServices, see: https://developer.apple.com/documentation/bundleresources/information_property_list/nsservices?language=objc
    # "NSServices": [
    #     {
    #         "NSMenuItem": {"default": "Detect text with Locationator"},
    #         "NSMessage": "detectTextInImage",
    #         "NSPortName": "Locationator",
    #         "NSUserData": "detectTextInImage",
    #         "NSRequiredContext": {"NSTextContent": "FilePath"},
    #         "NSSendTypes": ["NSPasteboardTypeURL"],
    #         "NSSendFileTypes": ["public.image"],
    #     },
    # ],
}

# Options for py2app
OPTIONS = {
    # The icon file to use for the app (this is App icon in Finder, not the status bar icon)
    "iconfile": "icon.icns",
    "plist": PLIST,
}

setup(
    app=APP,
    data_files=DATA_FILES,
    name="Locationator",
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
