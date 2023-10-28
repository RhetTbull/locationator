"""Simple MacOS menu bar / status bar app that provides access to reverse geocoding via Location Services. """

from __future__ import annotations

import contextlib
import datetime
import json
import os
import pathlib
import plistlib
import queue
import shlex
import threading
import time
from typing import Any

import objc
import rumps
from AppKit import NSApplication, NSPasteboardTypeFileURL
from Contacts import CNPostalAddress, CNPostalAddressStreetKey
from CoreLocation import (
    CLGeocoder,
    CLLocation,
    CLLocationManager,
    CLPlacemark,
    kCLAuthorizationStatusAuthorized,
    kCLAuthorizationStatusAuthorizedAlways,
    kCLAuthorizationStatusDenied,
    kCLAuthorizationStatusNotDetermined,
    kCLAuthorizationStatusRestricted,
)
from Foundation import (
    NSURL,
    NSDate,
    NSLog,
    NSObject,
    NSRunLoop,
    NSString,
    NSUTF8StringEncoding,
)
from image_metadata import (
    load_image_location,
    load_image_metadata_ref,
    metadata_ref_create_mutable,
    metadata_ref_set_tag,
    metadata_ref_write_to_file,
)
from loginitems import add_login_item, list_login_items, remove_login_item
from pasteboard import Pasteboard
from server import run_server
from utils import (
    flatten_dict,
    get_app_path,
    str_or_none,
    validate_latitude,
    validate_longitude,
)

# do not manually change the version; use bump2version per the README
__version__ = "0.1.0"

APP_NAME = "Locationator"
APP_ICON_WHITE = "icon_white.png"
APP_ICON_BLACK = "icon_black.png"
APP_ICON = APP_ICON_WHITE

# where to store saved state, will reside in Application Support/APP_NAME
CONFIG_FILE = f"{APP_NAME}.plist"

# optional logging to file if debug enabled (will always log to Console via NSLog)
LOG_FILE = f"{APP_NAME}.log"

# what port to run the server on
SERVER_PORT = 8000

AUTH_STATUS = {
    kCLAuthorizationStatusAuthorized: "Authorized",
    kCLAuthorizationStatusAuthorizedAlways: "Authorized Always",
    kCLAuthorizationStatusDenied: "Denied",
    kCLAuthorizationStatusNotDetermined: "Not Determined",
    kCLAuthorizationStatusRestricted: "Restricted",
}

# how long to wait in seconds for reverse geocode to complete
LOCATION_TIMEOUT = 15

# titles for install/remove menu
INSTALL_TOOLS_TITLE = "Install command line tool"
REMOVE_TOOLS_TITLE = "Remove command line tool"

CLI_NAME = "locationator"
TOOLS_INSTALL_PATH = "/usr/local/bin"


class ReverseGeocodeError(Exception):
    """Error raised when reverse geocode fails"""

    pass


class Locationator(rumps.App):
    """MacOS Menu Bar App to perform reverse geocoding from latitude/longitude."""

    def __init__(self, *args, **kwargs):
        super(Locationator, self).__init__(*args, **kwargs)

        # app version so it can be accessed from the server
        self.version = __version__

        # set "debug" to true in the config file to enable debug logging
        # if set in config, will be updated by load_config()
        self._debug = False

        # what port to run the server on
        # set "port" in the config file to change this
        # if set in config, will be updated by load_config()
        self.port = SERVER_PORT

        # set the icon to a PNG file in the current directory
        # this immediately updates the menu bar icon
        # py2app will place the icon in the app bundle Resources folder
        self.icon = APP_ICON

        # ensure icon matches menu bar dark/light state
        self.template = True

        # the log method uses NSLog to log to the unified log
        self.log("started")
        self.menu_reverse_geocode = rumps.MenuItem(
            "Reverse geocode...", callback=self.on_reverse_geocode
        )
        self.menu_about = rumps.MenuItem(f"About {APP_NAME}", callback=self.on_about)
        self.menu_quit = rumps.MenuItem(f"Quit {APP_NAME}", callback=self.on_quit)
        self.menu_start_on_login = rumps.MenuItem(
            "Start on login", callback=self.on_start_on_login
        )
        self.menu_install_tools = rumps.MenuItem(
            INSTALL_TOOLS_TITLE, callback=self.on_install_remove_tools
        )

        self.menu = [
            # self.menu_auth_status,
            self.menu_reverse_geocode,
            None,
            self.menu_start_on_login,
            self.menu_install_tools,
            self.menu_about,
            self.menu_quit,
        ]

        # load config from plist file and init menu state
        self.load_config()

        # initialize Location Services
        self.location_manager = CLLocationManager.alloc().init()
        self.location_manager.setDelegate_(self)

        # authorize Location Services if needed
        # TODO: doesn't appear to be needed for using reverse geocode
        # self.authorize()

        # start the HTTP server
        self.start_server()

        # initialize the service provider class which handles actions from the Services menu
        # pass reference to self so the service provider can access the app's methods and state
        self.service_provider = ServiceProvider.alloc().initWithApp_(self)
        # register the service provider with the Services menu
        NSApplication.sharedApplication().setServicesProvider_(self.service_provider)

    def authorize(self):
        """Request authorization for Location Services"""
        self.location_manager.requestAlwaysAuthorization()

    def locationManagerDidChangeAuthorization_(self, manager):
        """Called when authorization status changes"""
        self.log(f"authorization status changed: {manager.authorizationStatus()}")

    def on_auth_status(self, sender):
        """Display dialog with authorization status"""
        status = self.location_manager.authorizationStatus()
        status_str = AUTH_STATUS.get(status, "Unknown")
        rumps.alert(
            title=f"Authorization status",
            message=f"{APP_NAME} {__version__} authorization status: {status_str} ({status})",
            ok="OK",
        )

    def on_start_server(self, sender):
        """Start the server"""
        self.log("on_start_server")
        self.start_server()

    def start_server(self):
        # Run the server in a separate thread
        self.log("start_server")
        self.server_thread = threading.Thread(
            target=run_server, args=[self, self.port, LOCATION_TIMEOUT]
        )
        self.server_thread.start()
        self.log(f"start_server done: {self.server_thread}")

    def on_reverse_geocode(self, sender):
        """Perform reverse geocode of user-supplied latitude/longitude"""
        # get input from user
        result = rumps.Window(
            title="Reverse Geocode",
            message="Enter latitude and longitude separated by a comma or space in the text box below:",
            default_text="",
            ok="OK",
            cancel="Cancel",
            dimensions=(320, 40),
        ).run()

        if result.clicked:

            def _geocode_completion_handler(placemarks, error):
                """Handle completion of reverse geocode"""
                self.log(f"geocode_completion_handler: {placemarks}")
                if error:
                    rumps.alert(
                        title="Reverse Geocode Error",
                        message=f"{APP_NAME} {__version__} reverse geocode error: {error}",
                        ok="OK",
                    )
                else:
                    placemark = placemarks[0]
                    placemark_dict = placemark_to_dict(placemark)
                    rumps.alert(
                        title="Reverse Geocode Result",
                        message=format_result_dict(placemark_dict),
                        ok="OK",
                    )

            try:
                lat, lng = get_lat_long_from_string(result.text)
            except ValueError as e:
                rumps.alert(
                    title="Error",
                    message=f"{APP_NAME} {__version__} reverse geocode error: {e}",
                    ok="OK",
                )
                return
            self.log(f"on_reverse_geocode: {lat}, {lng}")
            geocoder = CLGeocoder.alloc().init()
            location = CLLocation.alloc().initWithLatitude_longitude_(
                float(lat), float(lng)
            )
            geocoder.reverseGeocodeLocation_completionHandler_(
                location, _geocode_completion_handler
            )

    def on_install_remove_tools(self, sender):
        """Install or remove the command line tools"""
        if sender.title.startswith("Install"):
            if self.install_tools():
                sender.title = REMOVE_TOOLS_TITLE
                self.config["tools_installed"] = True
                self.save_config()
        elif self.remove_tools():
            sender.title = INSTALL_TOOLS_TITLE
            self.config["tools_installed"] = False
            self.save_config()

    def install_tools(self):
        """Install the command line tools, located in Resources folder of app to /usr/local/bin"""
        self.log("on_install_tools")

        # create commands to install tools
        commands = []
        if not pathlib.Path(TOOLS_INSTALL_PATH).exists():
            commands.append(f"sudo mkdir -p {TOOLS_INSTALL_PATH}")
        app_path = get_app_path()
        src = shlex.quote(f"{app_path}/Contents/Resources/{CLI_NAME}")
        commands.append(f"sudo ln -s {src} {TOOLS_INSTALL_PATH}/{CLI_NAME}")
        command_str = f"osascript -e 'do shell script \"{' && '.join(commands)}\" with administrator privileges'"
        self.log(f"install command: {command_str}")

        command_word = "command" if len(commands) == 1 else "commands"
        message = (
            f"{APP_NAME} includes a command line tool, {CLI_NAME}, for performing reverse geocoding. "
            "To use it, the tool must be installed in your path. "
            f"When you press OK, the following {command_word} will be copied to the clipboard; "
            f"you will need to paste this in a terminal window and hit Return to run the {command_word}:\n\n"
            f"{command_str}\n\n"
            "\nYou may be prompted for your admin password."
        )

        if (
            rumps.alert(
                "Install command line tools",
                message,
                "OK",
                "Cancel",
            )
            != 1
        ):
            self.log("user cancelled install")
            return False

        pasteboard = Pasteboard()
        pasteboard.set_text(command_str)

        message = (
            f"Paste the {command_word} from the clipboard to a terminal window and press Return to run them. "
            "The clipboard contains the following:\n\n"
            f"{command_str}\n\n"
            "You may be prompted for your admin password. "
            "Press OK when done."
        )

        rumps.alert(
            "Install command line tools",
            message,
            "OK",
        )

        if self.tools_installed():
            self.log("on_install_tools done")
            message = (
                "You can now use the command line tool to perform reverse geocoding. "
                f"Run {TOOLS_INSTALL_PATH}/{CLI_NAME} --help for more information."
            )
            rumps.alert("Command line tool installed", message)
            return True
        else:
            self.log("on_install_tools failed")
            rumps.alert("Command line tool was not installed")
            return False

    def remove_tools(self) -> bool:
        """Remove command line tools"""
        self.log("on_remove_tools")

        command = f"sudo rm {TOOLS_INSTALL_PATH}/{CLI_NAME}"
        command_str = f"osascript -e 'do shell script \"{command}\" with administrator privileges'"
        self.log(f"remove command: {command_str}")

        message = (
            "When you press OK, the following command will be copied to the clipboard:\n\n"
            f"{command_str}\n\n"
            "You will need to paste this command into a terminal window and hit Return to run it. "
            "You may be prompted for your admin password."
        )
        if rumps.alert("Remove command line tools", message, "OK", "Cancel") != 1:
            self.log("user cancelled remove")
            return False

        pasteboard = Pasteboard()
        pasteboard.set_text(command_str)

        message = (
            "Paste the command from the clipboard to a terminal window and press Return to run it. "
            "The clipboard contains the following:\n\n"
            f"{command_str}\n\n"
            "You may be prompted for your admin password. "
            "Press OK when done."
        )
        rumps.alert("Remove command line tools", message, "OK")

        if self.tools_installed():
            self.log("on_remove_tools failed")
            rumps.alert(f"Command line tool was not removed")
            return False
        else:
            self.log("on_remove_tools done")
            rumps.alert("Command line tool removed")

        self.log("on_remove_tools done")
        return True

    def tools_installed(self) -> bool:
        """Return True if command line tools installed"""
        install_path = TOOLS_INSTALL_PATH
        # use os.path instead of pathlib because pathlib may raise PermissionError
        return os.path.exists(os.path.join(install_path, CLI_NAME))

    def reverse_geocode(self, latitude: float, longitude: float) -> dict[str, Any]:
        """Perform reverse geocode of latitude/longitude

        Args:
            latitude: latitude to reverse geocode
            longitude: longitude to reverse geocode

        Returns: dict containing the reverse geocode result

        Raises: ReverseGeocodeError if reverse geocode fails

        Note: This method may block for up to LOCATION_TIMEOUT seconds
        while waiting for the reverse geocode to complete.
        """

        class ReverseGeocodeResult:
            """Simple class to hold the result for the completion handler"""

            def __init__(self):
                self.data = {}
                self.error = None
                self.done = False

            def __str__(self):
                return f"ReverseGeocodeResult(data={self.data}, error={self.error}, done={self.done})"

        result = ReverseGeocodeResult()

        with objc.autorelease_pool():

            def _geocode_completion_handler(placemarks, completion_error):
                """Handle completion of reverse geocode"""
                nonlocal result
                self.log(f"geocode_completion_handler: {placemarks}")
                if completion_error:
                    result.error = completion_error
                else:
                    placemark = placemarks[0]
                    result.data = placemark_to_dict(placemark)
                result.done = True
                self.log(f"geocode_completion_handler done: {result=}")

            geocoder = CLGeocoder.alloc().init()
            location = CLLocation.alloc().initWithLatitude_longitude_(
                float(latitude), float(longitude)
            )
            geocoder.reverseGeocodeLocation_completionHandler_(
                location, _geocode_completion_handler
            )

            start_t = time.time()
            while not result.done:
                # wait for completion handler to set result.done
                # use NSRunLoop to allow other events to be processed
                # I tried this with using a threading.Event() and queue.Queue()
                # as in the server but it blocked the run loop
                NSRunLoop.currentRunLoop().runUntilDate_(
                    NSDate.dateWithTimeIntervalSinceNow_(0.05)
                )
                if time.time() - start_t > LOCATION_TIMEOUT:
                    self.log("timeout waiting for reverse geocode")
                    raise ReverseGeocodeError("Timeout waiting for reverse geocode")

            self.log(f"reverse_geocode done: {result=}")

            if result.error:
                raise ReverseGeocodeError(result.error)
            return result.data

    def reverse_geocode_with_queue(
        self, latitude: float, longitude: float, geocode_queue: queue.Queue
    ):
        """Perform reverse geocode of latitude/longitude; return result via queue"""
        self.log(f"reverse_geocode: {latitude}, {longitude}")
        with objc.autorelease_pool():
            geocoder = CLGeocoder.alloc().init()
            location = CLLocation.alloc().initWithLatitude_longitude_(
                latitude, longitude
            )

            placemark_dict = {}
            error_str = None

            def geocode_completion_handler(placemarks, error):
                """Completion handler for reverse geocode"""
                nonlocal placemark_dict
                nonlocal error_str

                self.log(f"geocode_completion_handler: {placemarks=}, {error=}")
                if error:
                    # return error message as JSON
                    self.log(f"geocode_completion_handler error: {error}")
                    error_str = str(error)
                    geocode_queue.put((False, error_str))
                    return

                placemark = placemarks.objectAtIndex_(0)
                placemark_dict = placemark_to_dict(placemark)
                self.log(f"geocode_completion_handler done: {placemark_dict=}")
                geocode_queue.put((True, json.dumps(placemark_dict)))
                self.log(f"geocode_completion_handler done: {geocode_queue=}")

            # start the request then wait for completion
            geocoder.reverseGeocodeLocation_completionHandler_(
                location, geocode_completion_handler
            )
            self.log(f"reverse_geocode done: {geocode_queue=}")

    def log(self, msg: str):
        """Log a message to unified log."""
        NSLog(f"{APP_NAME} {__version__} {msg}")
        # if debug set in config, also log to file
        # file will be created in Application Support folder
        if self._debug:
            with self.open(LOG_FILE, "a", encoding="utf-8") as f:
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
            self.config = {
                "debug": False,
                "port": SERVER_PORT,
                "tools_installed": self.tools_installed(),
            }
        self.log(f"loaded config: {self.config}")

        # update the menu state to match the loaded config
        self._debug = self.config.get("debug", False)
        self.port = self.config.get("port", SERVER_PORT)
        self.config["tools_installed"] = self.tools_installed()
        self.menu_install_tools.title = (
            INSTALL_TOOLS_TITLE
            if not self.config["tools_installed"]
            else REMOVE_TOOLS_TITLE
        )

        # save config because it may have been updated with default values
        self.save_config()

    def save_config(self):
        """Write config to plist file in Application Support folder.

        See docstring on load_config() for additional information.
        """

        self.config["debug"] = self._debug
        self.config["port"] = self.port
        self.config["tools_installed"] = self.tools_installed()

        # self.config["start_on_login"] = self.start_on_login.state
        with self.open(CONFIG_FILE, "wb+") as f:
            plistlib.dump(self.config, f)
        self.log(f"saved config: {self.config}")

    def on_start_on_login(self, sender):
        """Configure app to start on login or toggle this setting."""
        self.menu_start_on_login.state = not self.menu_start_on_login.state
        if self.menu_start_on_login.state:
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
            message=f"{APP_NAME} Version {__version__} on port {self.port}\n\n"
            f"{APP_NAME} is a simple utility to perform reverse geocoding.\n\n"
            f"{APP_NAME} is open source and licensed under the MIT license.\n\n"
            "Copyright 2023 by Rhet Turnbull\n"
            "https://github.com/RhetTbull/locationator",
            ok="OK",
        )

    def on_quit(self, sender):
        """Cleanup before quitting."""
        self.log("quitting")
        if self.location_manager:
            self.location_manager.dealloc()
        rumps.quit_application()

    def notification(self, title, subtitle, message):
        """Display a notification."""
        self.log(f"notification: {title} - {subtitle} - {message}")
        rumps.notification(title, subtitle, message)

    def open(self, *args, encoding=None):
        """Open a file within the application support folder for this application.

        Note: This is a wrapper around open() that prepends the application support folder.
        This is used instead of rumps.App.open() which doesn't allow specifying an encoding.
        """
        open_args = [os.path.join(self._application_support, args[0]), *args[1:]]
        open_kwargs = {}
        if encoding:
            open_kwargs["encoding"] = encoding
        return open(*open_args, **open_kwargs)


def placemark_to_dict(placemark: CLPlacemark) -> dict:
    """Convert a CLPlacemark to a dict

    Args:
        placemark: CLPlacemark object to convert

    Returns: dict containing the placemark data
    """
    coordinate = placemark.location().coordinate()
    timezone = placemark.timeZone()
    postalAddress = postal_address_to_dict(placemark.postalAddress())

    areasOfInterest = []
    if placemark.areasOfInterest():
        for i in range(placemark.areasOfInterest().count()):
            areasOfInterest.append(
                str_or_none(placemark.areasOfInterest().objectAtIndex_(i))
            )

    placemark_dict = {
        "location": (
            coordinate.latitude,
            coordinate.longitude,
        ),
        "name": str_or_none(placemark.name()),
        "thoroughfare": str_or_none(placemark.thoroughfare()),
        "subThoroughfare": str_or_none(placemark.subThoroughfare()),
        "locality": str_or_none(placemark.locality()),
        "subLocality": str_or_none(placemark.subLocality()),
        "administrativeArea": str_or_none(placemark.administrativeArea()),
        "subAdministrativeArea": str_or_none(placemark.subAdministrativeArea()),
        "postalCode": str_or_none(placemark.postalCode()),
        "ISOcountryCode": str_or_none(placemark.ISOcountryCode()),
        "country": str_or_none(placemark.country()),
        "postalAddress": postalAddress,
        "inlandWater": str_or_none(placemark.inlandWater()),
        "ocean": str_or_none(placemark.ocean()),
        "areasOfInterest": areasOfInterest,
        "timeZoneName": str_or_none(timezone.name()),
        "timeZoneAbbreviation": str_or_none(timezone.abbreviation()),
        "timeZoneSecondsFromGMT": int(timezone.secondsFromGMT()),
    }

    return placemark_dict


def postal_address_to_dict(postalAddress: CNPostalAddress) -> dict:
    """Convert a CNPostalAddress to a dict

    Args:
        postalAddress: CNPostalAddress object to convert

    Returns: dict containing the postalAddress data
    """
    if not postalAddress:
        return {
            "street": "",
            "city": "",
            "state": "",
            "country": "",
            "postalCode": "",
            "ISOCountryCode": "",
            "subAdministrativeArea": "",
            "subLocality": "",
        }

    postalAddress_dict = {
        "street": str_or_none(postalAddress.street()),
        "city": str_or_none(postalAddress.city()),
        "state": str_or_none(postalAddress.state()),
        "country": str_or_none(postalAddress.country()),
        "postalCode": str_or_none(postalAddress.postalCode()),
        "ISOCountryCode": str_or_none(postalAddress.ISOCountryCode()),
        "subAdministrativeArea": str_or_none(postalAddress.subAdministrativeArea()),
        "subLocality": str_or_none(postalAddress.subLocality()),
    }

    return postalAddress_dict


def get_lat_long_from_string(s: str) -> tuple[float, float]:
    """Get latitude and longitude from a string

    Args:
        s: string with values which may be separated by comma or space

    Returns: tuple of latitude and longitude as floats

    Raises:
        ValueError: if latitude or longitude is invalid or cannot be parsed
    """
    try:
        lat, lng = s.split(",")
    except ValueError:
        try:
            lat, lng = s.split(" ")
        except ValueError:
            raise ValueError(f"Could not parse latitude/longitude from string: {s}")
    lat = lat.strip()
    lng = lng.strip()
    if not validate_latitude(lat):
        raise ValueError(f"Invalid latitude: {lat}")
    if not validate_longitude(lng):
        raise ValueError(f"Invalid longitude: {lng}")
    return lat, lng


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
    def getReverseGeocoding_userData_error_(
        self, pasteboard, userdata, error
    ) -> str | None:
        """Get reverse geocoding for an image on the clipboard.

        This method will be called by the Services menu when the user selects "Locationator: reverse geocode".
        It is specified in the setup.py NSMessage attribute. The method name in NSMessage is `getReverseGeocoding`
        but the actual Objective-C signature is `getReverseGeocoding:userData:error:` hence the matching underscores
        in the python method name.

        Args:
            pasteboard: NSPasteboard object containing the URLs of the image files to process
            userdata: Unused, passed by the Services menu as value of NSUserData attribute in setup.py;
                can be used to pass additional data to the service if needed
            error: Unused; in Objective-C, error is a pointer to an NSError object that will be set if an error occurs;
                when using pyobjc, errors are returned as str values and the actual error argument is ignored.

        Returns:
            error: str value containing the error message if an error occurs, otherwise None
        """
        self.app.log("getReverseGeocoding_userData_error_ called via Services menu")

        with objc.autorelease_pool():
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
                    try:
                        latitude, longitude = load_image_location(pb_url.path())
                    except ValueError as e:
                        self.app.log(f"error processing file: {e}")
                        rumps.alert("Locationator Error", str(e), ok="OK")
                        return ErrorValue(e)

                    try:
                        result = self.app.reverse_geocode(latitude, longitude)
                        self.app.log(f"reverse geocode result: {result}")
                    except ReverseGeocodeError as e:
                        self.app.log(f"reverse geocode error: {e}")
                        rumps.alert("Locationator Error", str(e), ok="OK")
                        return ErrorValue(e)

                    # place result on pasteboard
                    result_str = format_result_dict(result)
                    pasteboard = Pasteboard()
                    pasteboard.set_text(result_str)
                    rumps.alert(
                        title="Reverse Geocode Result", message=result_str, ok="OK"
                    )
            except Exception as e:
                rumps.alert("Locationator Error", str(e), ok="OK")
                return ErrorValue(e)

        return None

    @serviceSelector
    def writeReverseGeocodingToXMP_userData_error_(
        self, pasteboard, userdata, error
    ) -> str | None:
        """Write reverse geocode location data to XMP metadata in a file.

        This method will be called by the Services menu when the user selects "Locationator: write XMP data".
        It is specified in the setup.py NSMessage attribute. The method name in NSMessage is `getReverseGeocoding`
        but the actual Objective-C signature is `getReverseGeocoding:userData:error:` hence the matching underscores
        in the python method name.

        Args:
            pasteboard: NSPasteboard object containing the URLs of the image files to process
            userdata: Unused, passed by the Services menu as value of NSUserData attribute in setup.py;
                can be used to pass additional data to the service if needed
            error: Unused; in Objective-C, error is a pointer to an NSError object that will be set if an error occurs;
                when using pyobjc, errors are returned as str values and the actual error argument is ignored.

        Returns:
            error: str value containing the error message if an error occurs, otherwise None
        """
        self.app.log("getReverseGeocoding_userData_error_ called via Services menu")

        with objc.autorelease_pool():
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
                    try:
                        latitude, longitude = load_image_location(pb_url.path())
                    except ValueError as e:
                        self.app.log(f"error processing file: {e}")
                        rumps.alert("Locationator Error", str(e), ok="OK")
                        return ErrorValue(e)

                    try:
                        result = self.app.reverse_geocode(latitude, longitude)
                        self.app.log(f"reverse geocode result: {result}")
                        xmp = write_xmp_metadata(pb_url.path(), result)
                        self.app.log(f"XMP metadata written: {json.dumps(xmp)}")
                    except ReverseGeocodeError as e:
                        self.app.log(f"reverse geocode error: {e}")
                        rumps.alert("Locationator Error", str(e), ok="OK")
                        return ErrorValue(e)

            except Exception as e:
                rumps.alert("Locationator Error", str(e), ok="OK")
                return ErrorValue(e)

        return None


def format_result_dict(d: dict) -> str:
    """Format a reverse geocode result dict for display"""
    result_dict = flatten_dict(d)
    for key, value in result_dict.items():
        if isinstance(value, (list, tuple)):
            result_dict[key] = ", ".join(str(v) for v in value)
    return "\n".join(f"{key}: {value}" for key, value in result_dict.items())


def write_xmp_metadata(filepath: str, results: dict[str, Any]) -> dict[str, Any]:
    """Write reverse geolocation-related fields to file metadata

    Args:
        filename (str): Path to file
        results (dict): Reverse geocode results

    Note: The following XMP fields are written (parentheses indicate the corresponding
    reverse geocode result field):

    - XMP:CountryCode / Iptc4xmpCore:CountryCode (ISOcountryCode)
    - XMP:Country / photoshop:Country (country)
    - XMP:State / photoshop:State (administrativeArea)
    - XMP:City / photoshop:City (locality)
    - XMP:Location / Iptc4xmpCore:Location (name)
    """

    metadata = {
        "Iptc4xmpCore:CountryCode": results["ISOcountryCode"],
        "photoshop:Country": results["country"],
        "photoshop:State": results["administrativeArea"],
        "photoshop:City": results["locality"],
        "Iptc4xmpCore:Location": results["name"],
    }

    metadata_ref = load_image_metadata_ref(filepath)
    metadata_ref_mutable = metadata_ref_create_mutable(metadata_ref)
    for key, value in metadata.items():
        metadata_ref_mutable = metadata_ref_set_tag(metadata_ref_mutable, key, value)

    metadata_ref_write_to_file(filepath, metadata_ref_mutable)

    # These are Core Foundation objects that need to be released
    del metadata_ref
    del metadata_ref_mutable

    return metadata


if __name__ == "__main__":
    Locationator(name=APP_NAME, quit_button=None).run()
