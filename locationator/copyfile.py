"""Copy a file on macOS using native API.
This allows copied files to use copy-on-write when used on a volume formatted with APFS.

When used on an APFS volume, a file copied with this function will be copied almost instantly
and will not use any additional disk space until the file is modified.

To use, you will need to install pyobjc-core and pyobjc-framework-Cocoa:

    `python3 -m pip install pyobjc-core pyobjc-framework-Cocoa`

This function uses teh native [NSFileManager](https://developer.apple.com/documentation/foundation/nsfilemanager) API to perform the copy.
The Objective-C function is called via [pyobjc](https://pyobjc.readthedocs.io/en/latest/).
"""

from __future__ import annotations

import os
import pathlib

import Foundation


def copyfile(
    src: str | pathlib.Path | os.PathLike, dest: str | pathlib.Path | os.PathLike
):
    """Copy file from src to dest.

    Args:
        src: Source file path.
        dest: Destination file path. If dest is a directory, src will be copied into it.
            If dest is a file, the src will be copied to dest.

    Raises:
        OSError: If the copy fails.
        FileExistsError: If dest file already exists.
    """
    if not isinstance(src, pathlib.Path):
        src = pathlib.Path(src)

    if not isinstance(dest, pathlib.Path):
        dest = pathlib.Path(dest)

    if dest.is_dir():
        dest /= src.name

    if dest.exists():
        raise FileExistsError(f"{dest} already exists")

    filemgr = Foundation.NSFileManager.defaultManager()
    success, error = filemgr.copyItemAtPath_toPath_error_(str(src), str(dest), None)
    if not success:
        raise OSError(error)


def removefile(path: str | pathlib.Path | os.PathLike):
    """Remove file at path.

    Args:
        path: Path to file to remove.

    Raises:
        OSError: If the remove fails.
    """
    if not isinstance(path, pathlib.Path):
        path = pathlib.Path(path)

    filemgr = Foundation.NSFileManager.defaultManager()
    success, error = filemgr.removeItemAtPath_error_(str(path), None)
    if not success:
        raise OSError(error)
