"""Test Locationator server"""

import subprocess
import time

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


@pytest.fixture(scope="function")
def wifi_off():
    """test fixture that turns off wifi at start of test and back on at end of test"""
    subprocess.run(["networksetup", "-setairportpower", "en0", "off"])
    time.sleep(10)
    yield
    subprocess.run(["networksetup", "-setairportpower", "en0", "on"])
    time.sleep(15)  # takes longer to turn back on that to turn off


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


def test_get_reverse_geocode_server_error(port, wifi_off):
    """Test GET /reverse_geocode with error (no network, assumes network is via WiFi"""
    with httpx.Client() as client:
        response = client.get(
            f"http://localhost:{port}/reverse_geocode?latitude={LATITUDE}&longitude={LONGITUDE}"
        )
        assert response.status_code == 500
        assert "Error" in response.text


def test_get_current_location_no_accuracy(port):
    """Test GET /current_location"""
    with httpx.Client() as client:
        response = client.get(f"http://localhost:{port}/current_location")
        assert response.status_code == 200
        assert response.json().get("latitude") is not None
        assert response.json().get("longitude") is not None
        assert response.json().get("error") is None


def test_get_current_location_with_accuracy(port):
    """Test GET /current_location?accuracy=reduced"""
    with httpx.Client() as client:
        response = client.get(
            f"http://localhost:{port}/current_location?accuracy=reduced"
        )
        assert response.status_code == 200
        assert response.json().get("latitude") is not None
        assert response.json().get("longitude") is not None
        assert response.json().get("error") is None


def test_get_current_location_invalid_accuracy(port):
    """Test GET /current_location?accuracy=invalid"""
    with httpx.Client() as client:
        response = client.get(
            f"http://localhost:{port}/current_location?accuracy=invalid"
        )
        assert response.status_code == 400
        assert "Invalid accuracy" in response.text


def test_get_current_location_server_error(port, wifi_off):
    """Test GET /current_location with error (no network, assumes network is via WiFi"""
    with httpx.Client() as client:
        response = client.get(f"http://localhost:{port}/current_location?timeout=0")
        assert response.status_code == 500
        assert "Error" in response.text
