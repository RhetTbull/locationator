"""Test Locationator server"""

import httpx
import pytest

# test coordinates for SoFi stadium
LAT_LONG = (33.953636, -118.338950)
LATITUDE = LAT_LONG[0]
LONGITUDE = LAT_LONG[1]
REVERSE_GEOCODE = {
    "location": [33.953636, -118.33895],
    "name": "SoFi Stadium",
    "thoroughfare": "Stadium Dr",
    "subThoroughfare": "1001",
    "locality": "Inglewood",
    "subLocality": "Century",
    "administrativeArea": "CA",
    "subAdministrativeArea": "Los Angeles County",
    "postalCode": "90305",
    "ISOcountryCode": "US",
    "country": "United States",
    "postalAddress": {
        "street": "1001 Stadium Dr",
        "city": "Inglewood",
        "state": "CA",
        "country": "United States",
        "postalCode": "90305",
        "ISOCountryCode": "US",
        "subAdministrativeArea": "Los Angeles County",
        "subLocality": "Century",
    },
    "inlandWater": "",
    "ocean": "",
    "areasOfInterest": ["SoFi Stadium"],
    "timeZoneName": "America/Los_Angeles",
    "timeZoneAbbreviation": "PDT",
    "timeZoneSecondsFromGMT": -25200,
}


def test_get_root(port):
    """Test GET /"""
    with httpx.Client() as client:
        response = client.get(f"http://localhost:{port}/")
        assert response.status_code == 200
        assert response.text.startswith("Locationator server version")


def test_get_reverse_geocode_bad_1(port):
    """Test GET /reverse_geocode"""
    with httpx.Client() as client:
        response = client.get(f"http://localhost:{port}/reverse_geocode")
        assert response.status_code == 400
        assert response.text == "Bad request: Missing latitude or longitude query arg"


def test_get_reverse_geocode_missing_longitude(port):
    """Test GET /reverse_geocode?latitude="""
    with httpx.Client() as client:
        response = client.get(
            f"http://localhost:{port}/reverse_geocode?latitude={LATITUDE}"
        )
        assert response.status_code == 400
        assert response.text == "Bad request: Missing latitude or longitude query arg"


def test_get_reverse_geocode_missing_latitude(port):
    """Test GET /reverse_geocode?longitude="""
    with httpx.Client() as client:
        response = client.get(
            f"http://localhost:{port}/reverse_geocode?longitude={LONGITUDE}"
        )
        assert response.status_code == 400
        assert response.text == "Bad request: Missing latitude or longitude query arg"


def test_get_reverse_geocode_bad_latitude(port):
    """Test GET /reverse_geocode?latitude=bad&longitude="""
    with httpx.Client() as client:
        response = client.get(
            f"http://localhost:{port}/reverse_geocode?latitude=100&longitude={LONGITUDE}"
        )
        assert response.status_code == 400
        assert response.text == "Bad request: Invalid latitude"


def test_get_reverse_geocode_bad_longitude(port):
    """Test GET /reverse_geocode?latitude=&longitude=bad"""
    with httpx.Client() as client:
        response = client.get(
            f"http://localhost:{port}/reverse_geocode?latitude={LATITUDE}&longitude=300"
        )
        assert response.status_code == 400
        assert response.text == "Bad request: Invalid longitude"


def test_get_reverse_geocode_valid(port):
    """Test GET /reverse_geocode?latitude=&longitude="""
    with httpx.Client() as client:
        response = client.get(
            f"http://localhost:{port}/reverse_geocode?latitude={LATITUDE}&longitude={LONGITUDE}"
        )
        assert response.status_code == 200
        assert response.json() == REVERSE_GEOCODE
