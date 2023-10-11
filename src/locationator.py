"""Simple MacOS menu bar / status bar app that automatically perform text detection on screenshots.

Also detects text on clipboard images and image files via the Services menu.

Runs on Catalina (10.15) and later.
"""

from __future__ import annotations

import contextlib
import datetime
import plistlib

import objc
import rumps
from AppKit import NSApplication, NSPasteboardTypeFileURL
from CoreLocation import (
    CLLocationManager,
    kCLAuthorizationStatusAuthorized,
    kCLAuthorizationStatusAuthorizedAlways,
    kCLAuthorizationStatusDenied,
    kCLAuthorizationStatusNotDetermined,
    kCLAuthorizationStatusRestricted,
    kCLLocationAccuracyBest,
    CLGeocoder,
)
from Foundation import (
    NSURL,
    NSLog,
    NSMetadataQuery,
    NSMetadataQueryDidFinishGatheringNotification,
    NSMetadataQueryDidStartGatheringNotification,
    NSMetadataQueryDidUpdateNotification,
    NSMetadataQueryGatheringProgressNotification,
    NSNotificationCenter,
    NSObject,
    NSPredicate,
    NSString,
    NSUTF8StringEncoding,
)
import threading

from loginitems import add_login_item, list_login_items, remove_login_item
from utils import get_app_path, verify_desktop_access

# do not manually change the version; use bump2version per the README
__version__ = "0.0.1"

APP_NAME = "Locationator"
APP_ICON = "icon.png"

# where to store saved state, will reside in Application Support/APP_NAME
CONFIG_FILE = f"{APP_NAME}.plist"

# optional logging to file if debug enabled (will always log to Console via NSLog)
LOG_FILE = f"{APP_NAME}.log"

AUTH_STATUS = {
    kCLAuthorizationStatusAuthorized: "Authorized",
    kCLAuthorizationStatusAuthorizedAlways: "Authorized Always",
    kCLAuthorizationStatusDenied: "Denied",
    kCLAuthorizationStatusNotDetermined: "Not Determined",
    kCLAuthorizationStatusRestricted: "Restricted",
}


class Locationator(rumps.App):
    """MacOS Menu Bar App to perform reverse geocoding from latitude/longitude."""

    def __init__(self, *args, **kwargs):
        super(Locationator, self).__init__(*args, **kwargs)

        # set "debug" to true in the config file to enable debug logging
        self._debug = False

        # pause / resume text detection
        self._paused = False

        # set the icon to a PNG file in the current directory
        # this immediately updates the menu bar icon
        # py2app will place the icon in the app bundle Resources folder
        self.icon = APP_ICON

        # the log method uses NSLog to log to the unified log
        self.log("started")

        # get list of supported languages for language menu

        # menus
        self.auth_status = rumps.MenuItem("Authorization status", self.on_auth_status)
        self.current_location = rumps.MenuItem(
            "Get current location", self.on_get_location
        )
        self.about = rumps.MenuItem(f"About {APP_NAME}", self.on_about)
        self.quit = rumps.MenuItem(f"Quit {APP_NAME}", self.on_quit)
        self.start_on_login = rumps.MenuItem(
            "Start on login", callback=self.on_start_on_login
        )
        self.menu = [
            self.auth_status,
            self.current_location,
            None,
            self.start_on_login,
            self.about,
            self.quit,
        ]

        # stores current location
        self._location = None

        # load config from plist file and init menu state
        self.load_config()

        self.authorize()

    def authorize(self):
        """Request authorization for Location Services"""
        with objc.autorelease_pool():
            self.location_manager = CLLocationManager.alloc().init()
            self.location_manager.setDelegate_(self)
            self.location_manager.requestAlwaysAuthorization()

    def locationManagerDidChangeAuthorization_(self, manager):
        """Called when authorization status changes"""
        NSLog(
            f"{APP_NAME} {__version__} authorization status changed: {manager.authorizationStatus()}"
        )

    def on_auth_status(self, sender):
        """Display dialog with authorization status"""
        status = self.location_manager.authorizationStatus()
        status_str = AUTH_STATUS.get(status, "Unknown")
        rumps.alert(
            title=f"Authorization status",
            message=f"{APP_NAME} {__version__} authorization status: {status_str} ({status})",
            ok="OK",
        )

    def on_get_location(self, sender):
        """Get current location and display it in a dialog"""
        NSLog(f"{APP_NAME} {__version__} on_get_location")
        # self.location_manager.setDesiredAccuracy_(kCLLocationAccuracyBest)
        NSLog(f"{APP_NAME} {__version__} on_get_location waiting for location")
        self.event = threading.Event()
        # self.geocoder = CLGeocoder.alloc().init()
        self.location_manager.startUpdatingLocation()
        self.event.wait(10)
        NSLog(f"{APP_NAME} {__version__} on_get_location done: {self._location}")
        rumps.alert(f"Location: {self._location}")

    def locationManager_didUpdateLocations_(self, manager, locations):
        """Handle location updates"""
        NSLog(f"{APP_NAME} {__version__} locationManager_didUpdateLocations_")
        self.location_manager.stopUpdatingLocation()
        NSLog(f"{APP_NAME} {__version__} locationManager_didUpdateLocations_ stopped")
        NSLog(
            f"{APP_NAME} {__version__} locationManager_didUpdateLocations_ {locations}"
        )
        current_location = locations.objectAtIndex_(0)
        # geocoder = CLGeocoder.alloc().init()
        # geocoder.reverseGeocodeLocation_completionHandler_(
        #     current_location, self.geocode_completion_handler
        # )
        self._location = current_location
        self.event.set()

    def locationManager_didFailWithError_(self, manager, error):
        NSLog(f"{APP_NAME} {__version__} locationManager_didFailWithError_: {error}")
        self.event.set()

    #         - (void)locationManager:(CLLocationManager *)manager didUpdateLocations:(NSArray *)locations {
    #     CLLocation *currentLocation = [locations lastObject];
    #     [locationManager stopUpdatingLocation];

    #     [geocoder reverseGeocodeLocation:currentLocation completionHandler:^(NSArray *placemarks, NSError *error) {
    #       if (error == nil && placemarks.count > 0) {
    #           CLPlacemark *placemark = placemarks[0];
    #           // Do something with the placemark
    #       }
    #       else {
    #           NSLog(@"Couldn't reverse geocode: %@", error);
    #       }
    #     }];
    # }

    def log(self, msg: str):
        """Log a message to unified log."""
        NSLog(f"{APP_NAME} {__version__} {msg}")

        # if debug set in config, also log to file
        # file will be created in Application Support folder
        if self._debug:
            with self.open(LOG_FILE, "a") as f:
                f.write(f"{datetime.datetime.now().isoformat()} - {msg}\n")

    def load_config(self):
        """Load config from plist file in Application Support folder.

        The usual app convention is to store config in ~/Library/Preferences but
        rumps.App.open() provides a convenient self.open() method to access the
        Application Support folder so that's what is used here.

        The config info is saved as a plist file (property list) which is an Apple standard
        for storing structured data. JSON or another format could be used but I stuck with
        plist so that the config file could be easily edited manually if needed and that's
        what is expected by macOS apps.
        """
        self.config = {}
        with contextlib.suppress(FileNotFoundError):
            with self.open(CONFIG_FILE, "rb") as f:
                with contextlib.suppress(Exception):
                    # don't crash if config file is malformed
                    self.config = plistlib.load(f)
        if not self.config:
            # file didn't exist or was malformed, create a new one
            # initialize config with default values
            self.config = {}
        self.log(f"loaded config: {self.config}")

        # update the menu state to match the loaded config
        # self.append.state = self.config.get("append", False)
        # self.linebreaks.state = self.config.get("linebreaks", True)
        # self.show_notification.state = self.config.get("notification", True)
        # self.set_confidence_state(self.config.get("confidence", CONFIDENCE_DEFAULT))
        # self.recognition_language = self.config.get(
        #     "language", self.recognition_language
        # )
        # self.set_language_menu_state(self.recognition_language)
        # self.language_english.state = self.config.get("always_detect_english", True)
        # self.detect_clipboard.state = self.config.get("detect_clipboard", True)
        # self.confirmation.state = self.config.get("confirmation", False)
        # self.qrcodes.state = self.config.get("detect_qrcodes", False)
        # self._debug = self.config.get("debug", False)
        # self.start_on_login.state = self.config.get("start_on_login", False)

        # save config because it may have been updated with default values
        self.save_config()

    def save_config(self):
        """Write config to plist file in Application Support folder.

        See docstring on load_config() for additional information.
        """
        # self.config["linebreaks"] = self.linebreaks.state
        # self.config["append"] = self.append.state
        # self.config["notification"] = self.show_notification.state
        # self.config["confidence"] = self.get_confidence_state()
        # self.config["language"] = self.recognition_language
        # self.config["always_detect_english"] = self.language_english.state
        # self.config["detect_clipboard"] = self.detect_clipboard.state
        # self.config["confirmation"] = self.confirmation.state
        # self.config["detect_qrcodes"] = self.qrcodes.state
        # self.config["debug"] = self._debug
        # self.config["start_on_login"] = self.start_on_login.state
        with self.open(CONFIG_FILE, "wb+") as f:
            plistlib.dump(self.config, f)
        self.log(f"saved config: {self.config}")

    def on_start_on_login(self, sender):
        """Configure app to start on login or toggle this setting."""
        self.start_on_login.state = not self.start_on_login.state
        if self.start_on_login.state:
            app_path = get_app_path()
            self.log(f"adding app to login items with path {app_path}")
            if APP_NAME not in list_login_items():
                add_login_item(APP_NAME, app_path, hidden=False)
        else:
            self.log("removing app from login items")
            if APP_NAME in list_login_items():
                remove_login_item(APP_NAME)
        self.save_config()

    def on_about(self, sender):
        """Display about dialog."""
        rumps.alert(
            title=f"About {APP_NAME}",
            message=f"{APP_NAME} Version {__version__}\n\n"
            f"{APP_NAME} is a simple utility to perform reverse geocoding.\n\n"
            f"{APP_NAME} is open source and licensed under the MIT license.\n\n"
            "Copyright 2023 by Rhet Turnbull\n"
            "https://github.com/RhetTbull/locationator",
            ok="OK",
        )

    def on_quit(self, sender):
        """Cleanup before quitting."""
        self.log("quitting")
        rumps.quit_application()

    def notification(self, title, subtitle, message):
        """Display a notification."""
        self.log(f"notification: {title} - {subtitle} - {message}")
        rumps.notification(title, subtitle, message)


def serviceSelector(fn):
    """Decorator to convert a method to a selector to handle an NSServices message."""
    return objc.selector(fn, signature=b"v@:@@o^@")


def ErrorValue(e):
    """Handler for errors returned by the service."""
    NSLog(f"{APP_NAME} {__version__} error: {e}")
    return e


class ServiceProvider(NSObject):
    """Service provider class to handle messages from the Services menu

    Initialize with ServiceProvider.alloc().initWithApp_(app)
    """

    app: Locationator | None = None

    def initWithApp_(self, app: Locationator):
        self = objc.super(ServiceProvider, self).init()
        self.app = app
        return self

    @serviceSelector
    def detectTextInImage_userData_error_(
        self, pasteboard, userdata, error
    ) -> str | None:
        """Detect text in an image on the clipboard.

        This method will be called by the Services menu when the user selects "Detect text with Locationator".
        It is specified in the setup.py NSMessage attribute. The method name in NSMessage is `detectTextInImage`
        but the actual Objective-C signature is `detectTextInImage:userData:error:` hence the matching underscores
        in the python method name.

        Args:
            pasteboard: NSPasteboard object containing the URLs of the image files to process
            userdata: Unused, passed by the Services menu as value of NSUserData attribute in setup.py;
                can be used to pass additional data to the service if needed
            error: Unused; in Objective-C, error is a pointer to an NSError object that will be set if an error occurs;
                when using pyobjc, errors are returned as str values and the actual error argument is ignored.

        Returns:
            error: str value containing the error message if an error occurs, otherwise None

        Note: because this method is explicitly invoked by the user via the Services menu, it will
        be called and files processed even if the app is paused.

        """
        self.app.log("detectTextInImage_userData_error_ called via Services menu")

        try:
            for item in pasteboard.pasteboardItems():
                # pasteboard will contain one or more URLs to image files passed by the Services menu
                pb_url_data = item.dataForType_(NSPasteboardTypeFileURL)
                pb_url = NSURL.URLWithString_(
                    NSString.alloc().initWithData_encoding_(
                        pb_url_data, NSUTF8StringEncoding
                    )
                )
                self.app.log(f"processing file from Services menu: {pb_url.path()}")
                image = Quartz.CIImage.imageWithContentsOfURL_(pb_url)
                detected_text = self.app.process_image(image)
                if self.app.show_notification.state:
                    self.app.notification(
                        title="Processed Image",
                        subtitle=f"{pb_url.path()}",
                        message=f"Detected text: {detected_text}"
                        if detected_text
                        else "No text detected",
                    )
        except Exception as e:
            return ErrorValue(e)

        return None


if __name__ == "__main__":
    Locationator(name=APP_NAME, quit_button=None).run()
