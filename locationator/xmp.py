"""Write XMP metadata to an image file"""

from __future__ import annotations

from typing import Any

from image_metadata import (
    load_image_location,
    load_image_metadata_ref,
    metadata_ref_create_mutable,
    metadata_ref_set_tag,
    metadata_ref_write_to_file,
)


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
