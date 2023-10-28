"""Get EXIF/IPTC/XMP metadata from an image file on macOS using CoreGraphics via pyobjc.

Requires installation of the following [pyobjc](https://pyobjc.readthedocs.io/en/latest/index.html) packages:

`pip install pyobjc-core pyobjc-framework-Quartz`

This module provides the following public functions:

- load_image_properties(): Returns the metadata properties dictionary from the image at the given path.
- load_image_metadata(): Returns the XMP metadata dictionary from the image at the given path.
- load_image_location(): Returns the GPS latitude/longitude coordinates from the image at the given path.

This code is an alternative to using a third-party tool like the excellent [exiftool](https://exiftool.org/)
and uses Apple's native ImageIO APIs. It should be able to read metadata from any file format supported
by ImageIO.

Implementation Note: Core Foundation objects created with Create or Copy functions must be released;
this is done with `del Object` in pyobjc.
"""

from __future__ import annotations

import os
import pathlib
from typing import Any, TypeVar

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
    CGImageDestinationAddImageAndMetadata,
    CGImageDestinationCreateWithURL,
    CGImageDestinationFinalize,
    CGImageMetadataCopyTags,
    CGImageMetadataCreateMutableCopy,
    CGImageMetadataCreateXMPData,
    CGImageMetadataRef,
    CGImageMetadataSetValueWithPath,
    CGImageMetadataTagCopyName,
    CGImageMetadataTagCopyPrefix,
    CGImageMetadataTagCopyValue,
    CGImageMetadataTagGetTypeID,
    CGImageSourceCopyMetadataAtIndex,
    CGImageSourceCopyPropertiesAtIndex,
    CGImageSourceCreateImageAtIndex,
    CGImageSourceCreateWithURL,
    CGImageSourceGetType,
)
from wurlitzer import pipes

# Create a custom type for CGMutableImageMetadataRef
# This is used to indicate which functions require a mutable copy of the metadata
# The Quartz package doesn't provide a CGMutableImageMetadataRef type
CGMutableImageMetadataRef = CGImageMetadataRef

FilePath = TypeVar("FilePath", str, pathlib.Path, os.PathLike)


class MetadataError(Exception):
    """Error calling CGImageMetadata functions."""

    pass


def load_image_properties(
    image_path: FilePath,
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
        del image_source
        return NSDictionary_to_dict_recursive(metadata)


def load_image_metadata(
    image_path: FilePath,
) -> dict[str, Any]:
    """Get the XMP metadata from the image at the given path

    Args:
        image_path: Path to the image file.

    Returns:
        A dictionary of XMP metadata properties from the image file.
        The dictionary keys are in form "prefix:name", e.g. "dc:creator".
    """
    metadata = load_image_metadata_ref(str(image_path))
    return metadata_dictionary_from_image_metadata_ref(metadata)


def load_image_metadata_ref(
    image_path: FilePath,
) -> CGImageMetadataRef:
    """Get the CGImageMetadataRef from the image at the given path

    Args:
        image_path: Path to the image file.

    Returns:
        A CGImageMetadataRef containing the XMP metadata.
    """
    with objc.autorelease_pool():
        image_url = NSURL.fileURLWithPath_(str(image_path))
        image_source = CGImageSourceCreateWithURL(image_url, None)

        metadata = CGImageSourceCopyMetadataAtIndex(image_source, 0, None)
        del image_source
    return metadata


def load_image_location(
    image_path: FilePath,
) -> tuple[float, float]:
    """Return the GPS latitude/longitude coordinates from the image at the given path.

    Args:
        image_path: Path to the image file.

    Returns:
        A tuple of latitude and longitude.

    Raises:
        ValueError: If the image does not contain GPS data or if the GPS data does not contain latitude and longitude.
    """
    properties = load_image_properties(image_path)
    gps_data = properties.get(Quartz.kCGImagePropertyGPSDictionary)
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


def metadata_ref_create_xmp(metadata_ref: CGImageMetadataRef) -> bytes:
    """Create serialized XMP from a CGImageMetadataRef."""
    with objc.autorelease_pool():
        data = CGImageMetadataCreateXMPData(metadata_ref, None)
        if not data:
            raise MetadataError("Could not create XMP data")
        xmp = bytes(data)
        del data
        return bytes(xmp)


def metadata_ref_create_mutable(
    metadata_ref: CGImageMetadataRef | CGMutableImageMetadataRef,
) -> CGMutableImageMetadataRef:
    """Create a CGMutableImageMetadataRef from a CGImageMetadataRef."""
    with objc.autorelease_pool():
        return CGImageMetadataCreateMutableCopy(metadata_ref)


def metadata_ref_set_tag(
    metadata_ref: CGMutableImageMetadataRef,
    tag_path: str,
    value: Any,
) -> CGMutableImageMetadataRef:
    """Set a metadata tag to value in a CGMutableImageMetadataRef

    Args:
        metadata_ref: A CGMutableImageMetadataRef
        tag_path: The tag path to set
        value: The value to set

    Returns: CGMutableImageMetadataRef with the tag set to value

    Note: This f
    """
    with objc.autorelease_pool():
        if CGImageMetadataSetValueWithPath(metadata_ref, None, tag_path, value):
            return metadata_ref
        raise MetadataError(
            f"Could not set tag {tag_path} to {value}; "
            "verify the tag and value are valid and that metadata_ref is a CGMutableImageMetadataRef"
        )


def metadata_ref_write_to_file(
    image_path: FilePath, metadata_ref: CGImageMetadataRef
) -> None:
    with objc.autorelease_pool():
        image_url = NSURL.fileURLWithPath_(str(image_path))
        image_source = CGImageSourceCreateWithURL(image_url, None)
        if not image_source:
            raise MetadataError(f"Could not create image source for {image_path}")
        image_type = CGImageSourceGetType(image_source)
        print(f"image_type: {image_type}")
        destination = CGImageDestinationCreateWithURL(image_url, image_type, 1, None)
        if not destination:
            raise MetadataError(f"Could not create image destination for {image_path}")
        with pipes() as (_out, _err):
            # On some versions of macOS this causes error to stdout
            # of form: AVEBridge Info: AVEEncoder_CreateInstance: Received CreateInstance (from VT)...
            # even though the operation succeeds
            # Use pipes() to suppress this error
            image_data = CGImageSourceCreateImageAtIndex(image_source, 0, None)
            CGImageDestinationAddImageAndMetadata(
                destination,
                image_data,
                metadata_ref,
                None,
            )
            CGImageDestinationFinalize(destination)
        del image_source
        del image_data
        del destination


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
