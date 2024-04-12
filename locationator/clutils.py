"""Utilities for working with CLLocation and Contacts objects."""

from __future__ import annotations

import datetime
import json
import textwrap
from dataclasses import asdict, dataclass

from Contacts import CNPostalAddress, CNPostalAddressStreetKey
from CoreLocation import (
    CLLocation,
    CLPlacemark,
    kCLLocationAccuracyBest,
    kCLLocationAccuracyBestForNavigation,
    kCLLocationAccuracyHundredMeters,
    kCLLocationAccuracyKilometer,
    kCLLocationAccuracyNearestTenMeters,
    kCLLocationAccuracyReduced,
    kCLLocationAccuracyThreeKilometers,
)
from Foundation import NSDate
from utils import flatten_dict, str_or_none


@dataclass
class Location:
    latitude: float
    longitude: float
    altitude: float
    horizontal_accuracy: float
    vertical_accuracy: float
    speed: float
    course: float
    timestamp: datetime.datetime

    def asdict(self) -> dict:
        return asdict(self)

    def json(self) -> str:
        def _default(obj):
            if isinstance(obj, datetime.datetime):
                return obj.isoformat()
            raise TypeError(
                f"Object of type {obj.__class__.__name__} is not JSON serializable"
            )

        return json.dumps(self.asdict(), default=_default)

    def as_str(self) -> str:
        """Format string represenation of location"""
        return textwrap.dedent(
            f"""
            latitude: {self.latitude} degrees
            longitude: {self.longitude} degrees
            altitude: {self.altitude} meters
            horizontal accuracy: {self.horizontal_accuracy} meters
            vertical accuracy: {self.vertical_accuracy} meters
            speed: {self.speed} meters/second
            course: {self.course} degrees
            timestamp: {self.timestamp}
            """
        )


def Location_from_CLLocation(location: CLLocation) -> Location:
    """Convert a CLLocation object to a Location dataclass object."""
    timestamp = datetime.datetime.fromtimestamp(
        location.timestamp().timeIntervalSince1970()
    )
    return Location(
        latitude=location.coordinate().latitude,
        longitude=location.coordinate().longitude,
        altitude=location.altitude(),
        horizontal_accuracy=location.horizontalAccuracy(),
        vertical_accuracy=location.verticalAccuracy(),
        speed=location.speed(),
        course=location.course(),
        timestamp=timestamp,
    )


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


def format_result_dict(d: dict) -> str:
    """Format a reverse geocode result dict for display"""
    result_dict = flatten_dict(d)
    for key, value in result_dict.items():
        if isinstance(value, (list, tuple)):
            result_dict[key] = ", ".join(str(v) for v in value)
    return "\n".join(f"{key}: {value}" for key, value in result_dict.items())


def validate_accuracy(accuracy: float) -> bool:
    """Validate a desiredAccuracy value"""
    if accuracy not in {
        kCLLocationAccuracyBest,
        kCLLocationAccuracyBestForNavigation,
        kCLLocationAccuracyHundredMeters,
        kCLLocationAccuracyKilometer,
        kCLLocationAccuracyNearestTenMeters,
        kCLLocationAccuracyReduced,
        kCLLocationAccuracyThreeKilometers,
    }:
        return False
    return True


def accuracy_from_str(accuracy: str) -> float:
    """Return a valid kCLLocationAccuracy constant given a string value"""
    match accuracy:
        case "best":
            return kCLLocationAccuracyBest
        case "navigation":
            return kCLLocationAccuracyBestForNavigation
        case "100m":
            return kCLLocationAccuracyHundredMeters
        case "1km":
            return kCLLocationAccuracyKilometer
        case "10m":
            return kCLLocationAccuracyNearestTenMeters
        case "reduced":
            return kCLLocationAccuracyReduced
        case "3km":
            return kCLLocationAccuracyThreeKilometers
        case _:
            raise ValueError(f"Unknown accuracy value: {accuracy}")
