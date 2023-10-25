"""Get EXIF/IPTC/XMP metadata from an image file on macOS using CoreGraphics via pyobjc.

Requires installation of the following [pyobjc](https://pyobjc.readthedocs.io/en/latest/index.html) packages:

`pip install pyobjc-core pyobjc-framework-Quartz`

This module provides 3 public functions:

- get_image_properties(): Returns the metadata properties dictionary from the image at the given path.
- get_image_xmp_metadata(): Returns the XMP metadata dictionary from the image at the given path.
- get_image_location(): Returns the GPS latitude/longitude coordinates from the image at the given path.

To use this on the command line:
    
    ```bash
    python3 image_metadata.py <image_path>
    ```

This code is an alternative to using a third-party tool like the excellent [exiftool](https://exiftool.org/)
and uses Apple's native ImageIO APIs. It should be able to read metadata from any file format supported
by ImageIO.
"""

from __future__ import annotations

import os
import pathlib
from typing import Any

import objc
import Quartz
from CoreFoundation import (
    CFArrayGetCount,
    CFArrayGetTypeID,
    CFArrayGetValueAtIndex,
    CFDictionaryGetTypeID,
    CFGetTypeID,
    CFStringGetTypeID,
)
from Foundation import (
    NSURL,
    NSArray,
    NSData,
    NSDictionary,
    NSMutableArray,
    NSMutableDictionary,
)
from Quartz import (
    CGImageMetadataCopyTags,
    CGImageMetadataRef,
    CGImageMetadataTagCopyName,
    CGImageMetadataTagCopyPrefix,
    CGImageMetadataTagCopyValue,
    CGImageMetadataTagGetTypeID,
    CGImageSourceCopyMetadataAtIndex,
    CGImageSourceCopyPropertiesAtIndex,
    CGImageSourceCreateWithURL,
)


def get_image_properties(
    image_path: str | pathlib.Path | os.PathLike,
) -> dict[str, Any]:
    """Return the metadata properties dictionary from the image at the given path.

    Args:
        image_path: Path to the image file.

    Returns:
        A dictionary of metadata properties from the image file.

    Note:
        The dictionary keys are named '{IPTC}', '{TIFF}', etc.
        Reference: https://developer.apple.com/documentation/imageio/image_properties?language=objc
        for more information.

        This function is useful for retrieving EXIF and IPTC metadata.
        See also get_image_xmp_metadata() for XMP metadata.
    """
    with objc.autorelease_pool():
        image_url = NSURL.fileURLWithPath_(str(image_path))
        image_source = CGImageSourceCreateWithURL(image_url, None)

        metadata = CGImageSourceCopyPropertiesAtIndex(image_source, 0, None)
        return NSDictionary_to_dict_recursive(metadata)


def get_image_xmp_metadata(
    image_path: str | pathlib.Path | os.PathLike,
) -> dict[str, Any]:
    """Get the XMP metadata from the image at the given path

    Args:
        image_path: Path to the image file.

    Returns:
        A dictionary of XMP metadata properties from the image file.
        The dictionary keys are in form "prefix:name", e.g. "dc:creator".
    """
    metadata = get_image_xmp_metadata_ref(str(image_path))
    return metadata_dictionary_from_image_metadata_ref(metadata)


def get_image_xmp_metadata_ref(
    image_path: str | pathlib.Path | os.PathLike,
) -> CGImageMetadataRef:
    """Get the XMP metadata from the image at the given path

    Args:
        image_path: Path to the image file.

    Returns:
        A CGImageMetadataRef containing the XMP metadata.
    """
    with objc.autorelease_pool():
        image_url = NSURL.fileURLWithPath_(str(image_path))
        image_source = CGImageSourceCreateWithURL(image_url, None)

        return CGImageSourceCopyMetadataAtIndex(image_source, 0, None)


def get_image_location(
    image_path: str | pathlib.Path | os.PathLike,
) -> tuple[float, float]:
    """Return the GPS latitude/longitude coordinates from the image at the given path.

    Args:
        image_path: Path to the image file.

    Returns:
        A tuple of latitude and longitude.

    Raises:
        ValueError: If the image does not contain GPS data or if the GPS data does not contain latitude and longitude.
    """
    metadata = get_image_properties(image_path)
    gps_data = metadata.get(Quartz.kCGImagePropertyGPSDictionary)
    if not gps_data:
        raise ValueError("This image does not contain GPS data")

    latitude = gps_data.get(Quartz.kCGImagePropertyGPSLatitude)
    longitude = gps_data.get(Quartz.kCGImagePropertyGPSLongitude)

    if latitude is None or longitude is None:
        raise ValueError("Could not extract latitude and/or longitude from GPS data")

    try:
        latitude = float(latitude)
        longitude = float(longitude)
    except ValueError:
        raise ValueError("Could not extract latitude and/or longitude from GPS data")

    if gps_data.get(Quartz.kCGImagePropertyGPSLatitudeRef) == "S":
        latitude *= -1
    if gps_data.get(Quartz.kCGImagePropertyGPSLongitudeRef) == "W":
        longitude *= -1

    return latitude, longitude


def NSDictionary_to_dict_recursive(ns_dict: NSDictionary) -> dict[str, Any]:
    """Convert an NSDictionary to a Python dict recursively; handles subset of types needed for image metadata."""
    py_dict = {}
    for key, value in ns_dict.items():
        if isinstance(value, NSDictionary):
            py_dict[key] = NSDictionary_to_dict_recursive(value)
        elif isinstance(value, NSArray):
            py_dict[key] = NSArray_to_list_recursive(value)
        elif isinstance(value, NSData):
            py_dict[key] = value.bytes().tobytes()
        else:
            py_dict[key] = str(value)
    return py_dict


def NSArray_to_list_recursive(ns_array: NSArray) -> list[Any]:
    """Convert an NSArray to a Python list recursively; handles subset of types needed for image metadata."""
    py_list = []
    for value in ns_array:
        if isinstance(value, NSDictionary):
            py_list.append(NSDictionary_to_dict_recursive(value))
        elif isinstance(value, NSArray):
            py_list.append(NSArray_to_list_recursive(value))
        elif isinstance(value, NSData):
            py_list.append(value.bytes().tobytes())
        else:
            py_list.append(str(value))
    return py_list


def metadata_dictionary_from_image_metadata_ref(metadata_ref):
    with objc.autorelease_pool():
        tags = CGImageMetadataCopyTags(metadata_ref)
        if not tags:
            return None

        metadata_dict = {}
        for i in range(CFArrayGetCount(tags)):
            tag = CFArrayGetValueAtIndex(tags, i)

            prefix = CGImageMetadataTagCopyPrefix(tag)
            name = CGImageMetadataTagCopyName(tag)
            value = CGImageMetadataTagCopyValue(tag)

            key = f"{prefix}:{name}"
            object_value = _recursive_parse_metadata_value(value)
            metadata_dict[key] = object_value

        return metadata_dict.copy()


def _recursive_parse_metadata_value(value):
    if CFGetTypeID(value) == CFStringGetTypeID():
        return str(value)
    elif CFGetTypeID(value) == CFDictionaryGetTypeID():
        value_dict = NSMutableDictionary.dictionary()
        original_dict = NSDictionary.dictionaryWithDictionary_(value)
        for key in original_dict.allKeys():
            value_dict[key] = _recursive_parse_metadata_value(original_dict[key])
        return NSDictionary_to_dict_recursive(value_dict)
    elif CFGetTypeID(value) == CFArrayGetTypeID():
        value_array = NSMutableArray.array()
        original_array = NSArray.arrayWithArray_(value)
        for element in original_array:
            value_array.addObject_(_recursive_parse_metadata_value(element))
        return NSArray_to_list_recursive(value_array)
    elif CFGetTypeID(value) == CGImageMetadataTagGetTypeID():
        tag_value = CGImageMetadataTagCopyValue(value)
        return _recursive_parse_metadata_value(tag_value)
    else:
        return value
