# Locationator

A simple macOS menubar app that provides access to the macOS Location Services reverse geocoding API.

## Rationale

Why this app? Apple's Location Services API is great and I wanted to be able to use the reverse geocoding API from the command line. Unfortunately, in Ventura, Apple has basically made it impossible to use Location Services from a command line app because the app cannot be granted the necessary permissions in System Settings. This app is a workaround for that problem. It creates a menubar app that can be granted the necessary permissions and then provides a simple API for accessing the reverse geocoding API via a built in web server. This means that you can use the Location Services API from the command line by making a simple HTTP request to the built in web server via curl for example or can use the API end point from any other app that can make HTTP requests.

## Installation

Download the latest release DMG from the [releases page](https://github.com/RhetTbull/locationator/releases) and use the DMG to install the app. Once installed, launch the app and grant it the necessary permissions.

To launch Locationator the first time you'll need to right-click on the app icon and select "Open" otherwise you may get a warning about unknown developer as the app is not signed with an Apple Developer ID. You may need to do this twice.

Alternatively, to build from source:

- clone the repo
- cd into the repo directory
- create a virtual environment and activate it
- python3 -m pip install -r requirements.txt
- python3 setup.py py2app
- Copy dist/Locationator.app to /Applications

## Usage

Locationator server is a very simple HTTP server for handling local requests. It supports two endpoints, `GET /` and `GET /reverse_geocode`.

>*Please note*, this server is for local use and NOT intended to be exposed to the internet. The server does not support any authentication or authorization and is intended to be used on a local machine only.

### GET /

This endpoint provides the current version and the port on which the server is running.

**URL** : `/`

**Method** : `GET`

**Response format** : Content-type is plain text

**Success Response Example** :

*Note*: examples below use the [httpie](https://httpie.io/) command line tool for making HTTP requests. You can also use curl or any other tool that can make HTTP requests.

`http get localhost:8000`

or

`curl -X GET http://localhost:8000/`

```http
HTTP/1.0 200 OK
Content-type: text/plain
Date: Fri, 13 Oct 2023 16:16:42 GMT
Server: SimpleHTTP/0.6 Python/3.11.6

Locationator server version 0.0.1 is running on port 8000
```

### GET /reverse_geocode

Receive geocode queries from the client. This endpoint accepts GET requests with latitude and longitude data as query parameters, performs reverse geocoding and returns the result.

**URL** : `/reverse_geocode?latitude=double&longitude=double`

**Method** : `GET`

**Query Parameters** :

|Parameter|Type|Description|
|---|---|---|
|`latitude`|Double|Latitude of the location to be reverse geocoded|
|`longitude`|Double|Longitude of the location to be reverse geocoded|

**Response format** :

- On Success, Content-type is application/json and a response code of 200 with a JSON object containing the reverse geocoding result is returned
- On Failure, a description of the error is returned with a suitable HTTP response code

**Success Response Example**:

`http GET "http://localhost:8000/reverse_geocode?latitude=33.953636&longitude=-118.338950"`

or

`curl -X GET "http://localhost:8000/reverse_geocode?latitude=33.953636&longitude=-118.338950"`

```http
HTTP/1.0 200 OK
Content-type: application/json
Date: Fri, 13 Oct 2023 19:32:24 GMT
Server: SimpleHTTP/0.6 Python/3.11.6

{
    "ISOcountryCode": "US",
    "administrativeArea": "CA",
    "areasOfInterest": [
        "SoFi Stadium"
    ],
    "country": "United States",
    "inlandWater": "",
    "locality": "Inglewood",
    "location": [
        33.953636,
        -118.33895
    ],
    "name": "SoFi Stadium",
    "ocean": "",
    "postalAddress": {
        "ISOCountryCode": "US",
        "city": "Inglewood",
        "country": "United States",
        "postalCode": "90305",
        "state": "CA",
        "street": "1001 Stadium Dr",
        "subAdministrativeArea": "Los Angeles County",
        "subLocality": "Century"
    },
    "postalCode": "90305",
    "subAdministrativeArea": "Los Angeles County",
    "subLocality": "Century",
    "subThoroughfare": "1001",
    "thoroughfare": "Stadium Dr",
    "timeZoneAbbreviation": "PDT",
    "timeZoneName": "America/Los_Angeles",
    "timeZoneSecondsFromGMT": -25200
}
```

## Command Line Tools

Locationator provides a menu option to "Install Command Line tools" that will install the `locationator` CLI to `/usr/local/bin`. The CLI has 3 commands. `lookup`, `from-exif`, and `write-xmp`.  `lookup` looks up the reverse geocoding for a given latitude & longitude. `from-exif` reads the GPS coordinates from a file using [exiftool](https://exiftool.org) and prints out the reverse geocoding data in JSON format. `write-xmp` reads the GPS coordinates from the file and writes the following fields to the XMP metadata of the file using exiftool:

- XMP:CountryCode (ISOcountryCode)
- XMP:Country (country)
- XMP:State (administrativeArea)
- XMP:City (locality)
- XMP:Location (name)

exiftool must be installed to use `from-exif` or `write-xmp`.

CLI Usage:

```
Usage: locationator [OPTIONS] COMMAND [ARGS]...

Options:
  --debug
  --port INTEGER
  --help          Show this message and exit.

Commands:
  from-exif  Lookup the reverse geolocation for an image/video file using...
  lookup     Lookup the reverse geolocation for a lat/lon pair.
  write-xmp  Lookup the reverse geolocation for an image/video file using...
```

## Notes

- If building with [pyenv](https://github.com/pyenv/pyenv) installed python, you'll need to build the python with framework support:
  - `env PYTHON_CONFIGURE_OPTS="--enable-framework" pyenv install -v 3.11.6`
- Tested on macOS Ventura 13.5.1
- By default, the server runs on port 8000. This can be changed by editing the configuraiton plist file at `~/Library/Application Support/Locationator/Locationator.plist` and changing `port` to the desired port number then restarting the app.

## Building

Locationator uses [doit](https://pydoit.org/) to build the app. To build the app, run `doit` in the root of the repo. Run `doit list` to see list of available tasks.

`pip install -r dev_requirements.txt`
`doit`

## Testing

- The app can be tested by running the tests in the `tests` directory with pytest.
- `pip install -r dev_requirements.txt`
- `pytest -vv tests/`

>**Note**: the tests require the built app to be installed in /Applications

## License

Copyright (c) 2023, Rhet Turnbull  
Licensed under the MIT License
