"""Work with CLLocation objects in Python."""

import datetime
import json
from dataclasses import asdict, dataclass

from CoreLocation import CLLocation
from Foundation import NSDate


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
