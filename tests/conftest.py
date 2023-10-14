"""Test configuration for pytest for Locationator tests."""

import os
import pathlib
import plistlib
import shutil
import time
import typing as t
from contextlib import contextmanager
from io import TextIOWrapper

import applescript
import pytest
from applescript import kMissingValue

from .loginitems import add_login_item, list_login_items, remove_login_item

APP_NAME = "Locationator"


def click_menu_item(menu_item: str, sub_menu_item: t.Optional[str] = None) -> bool:
    """Click menu_item in app's status bar menu.

    This uses AppleScript and System Events to click on the menu item.

    Args:
        menu_item: Name of menu item to click.
        sub_menu_item: Name of sub menu item to click or None if no sub menu item.

    Returns:
        True if menu item was successfully clicked, False otherwise.

    Note: in many status bar apps, the actual menu bar you want to click is menu bar 2;
    menu bar 1 is the Apple menu. In RUMPS apps, it appears that the menu bar you want is
    menu bar 1. This may be different for other apps.
    """
    scpt = applescript.AppleScript(
        """
    on click_menu_item(process_, menu_item_name_, submenu_item_name_)
        try
            tell application "System Events" to tell process process_
                tell menu bar item 1 of menu bar 1
                    click
                    click menu item menu_item_name_ of menu 1
                    if submenu_item_name_ is not missing value then
                        click menu item submenu_item_name_ of menu 1 of menu item menu_item_name_ of menu 1
                    end if
                end tell
            end tell
        on error
            return false
        end try
        return true
    end click_menu_item
    """
    )
    sub_menu_item = sub_menu_item or kMissingValue
    return scpt.call("click_menu_item", APP_NAME, menu_item, sub_menu_item)


def click_window_button(window: int, button: int) -> bool:
    """ "Click a button in an app window.

    Args:
        window: window number (1 = first window)
        button: button number (1 = first button, if yes/no, 1 = yes, 2 = no)

    Returns:
        True if successful, False otherwise
    """
    scpt = applescript.AppleScript(
        """
        on click_window_button(process_, window_number_, button_number_)
            try
                tell application "System Events" to tell process process_
                    tell button button_number_ of window window_number_
                        click
                    end tell
                end tell
            on error
                return false
            end try
            return true
        end click_window_button
    """
    )
    return scpt.call("click_window_button", APP_NAME, window, button)


def process_is_running(process_name: str) -> bool:
    """Return True if process_name is running, False otherwise"""
    scpt = applescript.AppleScript(
        """
        on process_is_running(process_name_)
            tell application "System Events"
                set process_list to (name of every process)
            end tell
            return process_name_ is in process_list
        end process_is_running
    """
    )
    return scpt.call("process_is_running", process_name)


def app_support_dir() -> pathlib.Path:
    """Return path to Textinator's app support directory"""
    return pathlib.Path(f"~/Library/Application Support/{APP_NAME}").expanduser()


@contextmanager
def log_file() -> TextIOWrapper:
    """Return Apps's log file, opened for reading from end"""
    log_filepath = app_support_dir() / f"{APP_NAME}.log"
    lf = log_filepath.open("r")
    lf.seek(0, os.SEEK_END)
    yield lf
    lf.close()


def backup_log():
    """Backup log file"""
    log_path = app_support_dir() / f"{APP_NAME}.log"
    if log_path.exists():
        log_path.rename(log_path.with_suffix(".log.bak"))


def restore_log():
    """Restore log file from backup"""
    log_path = app_support_dir() / f"{APP_NAME}.log.bak"
    if log_path.exists():
        log_path.rename(log_path.parent / log_path.stem)


def backup_plist():
    """Backup plist file"""
    plist_path = app_support_dir() / f"{APP_NAME}.plist"
    if plist_path.exists():
        plist_path.rename(plist_path.with_suffix(".plist.bak"))


def restore_plist():
    """Restore plist file from backup"""
    plist_path = app_support_dir() / f"{APP_NAME}.plist.bak"
    if plist_path.exists():
        plist_path.rename(plist_path.parent / plist_path.stem)


@pytest.fixture(autouse=True, scope="session")
def setup_teardown():
    """Fixture to execute asserts before and after test session is run"""
    # setup
    os.system(f"killall {APP_NAME}")

    # backup_log()
    backup_plist()

    shutil.copy(f"tests/data/{APP_NAME}.plist", app_support_dir() / f"{APP_NAME}.plist")

    login_item = f"{APP_NAME}" in list_login_items()
    if login_item:
        remove_login_item(f"{APP_NAME}")

    os.system(f"open -a {APP_NAME}")
    time.sleep(5)

    yield  # run tests

    # teardown
    os.system(f"killall {APP_NAME}")

    # restore_log()
    restore_plist()

    if login_item:
        add_login_item(f"{APP_NAME}", f"/Applications/{APP_NAME}.app", False)

    os.system(f"open -a {APP_NAME}")


@pytest.fixture
def suspend_capture(pytestconfig):
    """Context manager fixture that suspends capture of stdout/stderr for the duration of the context manager."""

    class suspend_guard:
        def __init__(self):
            self.capmanager = pytestconfig.pluginmanager.getplugin("capturemanager")

        def __enter__(self):
            self.capmanager.suspend_global_capture(in_=True)

        def __exit__(self, _1, _2, _3):
            self.capmanager.resume_global_capture()

    yield suspend_guard()


@pytest.fixture
def port() -> int:
    """Return port number to use for server"""
    data = plistlib.load(open(f"tests/data/{APP_NAME}.plist", "rb"))
    return data["port"]
