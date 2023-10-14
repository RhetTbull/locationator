"""HTTP Server for Locationator API"""

from __future__ import annotations

import contextlib
import http.server
import json
import queue
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from locationator import Locationator


def run_server(app: Locationator, port: int, timeout: int):
    """Run the HTTP server

    Args:
        app: Locationator instance
        port: Port to listen on
        timeout: Timeout in seconds for reverse geocode requests
    """

    # Handler class defined here so it can access the app instance and the port

    class Handler(http.server.SimpleHTTPRequestHandler):
        """Very simple HTTP server to receive reverse geocode requests.

        This should be sufficient for handling local requests but do not
        expose this server to the internet.
        """

        # Would be nice to use FastAPI, etc. but I couldn't make that work when
        # called from the Rumps app.

        def do_GET(self):
            app.log(f"do_GET: {self.path=}")
            if self.path == "/":
                self.send_success(
                    f"Locationator server version {app.version} is running on port {port}\n",
                    content_type="text/plain",
                )
            elif self.path.split("?")[0] == "/reverse_geocode":
                query_dict = self.get_query_args()
                if "latitude" not in query_dict or "longitude" not in query_dict:
                    self.send_bad_request("Missing latitude or longitude query arg")
                    return
                if not validate_latitude(query_dict["latitude"]):
                    self.send_bad_request("Invalid latitude")
                    return
                if not validate_longitude(query_dict["longitude"]):
                    self.send_bad_request("Invalid longitude")
                    return
                success, result = self.reverse_geocode(
                    float(query_dict["latitude"]), float(query_dict["longitude"])
                )
                app.log(f"do_PUT: {success=}, {result=}")
                if success:
                    self.send_success(result)
                else:
                    self.send_server_error(result)
            else:
                self.send_not_found(self.path)

        def do_PUT(self):
            if self.path == "/reverse_geocode":
                content_length = int(self.headers["Content-Length"])
                body = json.loads(self.rfile.read(content_length))
                app.log(f"do_PUT: {body=}")
                if "latitude" in body and "longitude" in body:
                    if not validate_latitude(body["latitude"]):
                        self.send_bad_request("Invalid latitude")
                        return
                    if not validate_longitude(body["longitude"]):
                        self.send_bad_request("Invalid longitude")
                        return
                    success, result = self.handle_reverse_geocode_put(body)
                    app.log(f"do_PUT: {success=}, {result=}")
                    if success:
                        self.send_success(result)
                    else:
                        self.send_server_error(result)
                else:
                    self.send_bad_request("Missing latitude or longitude in body")

        def send_bad_request(self, error_str: str):
            """Send bad request response"""
            self._send_response(400, "text/plain", "Bad request: " + error_str)

        def send_not_found(self, error_str: str):
            """Send not found response"""
            self._send_response(404, "text/plain", "Not found: " + error_str)

        def send_success(self, result: str, content_type: str = "application/json"):
            """Send success response"""
            self._send_response(200, content_type, result)

        def send_server_error(self, result: str):
            """Send server error response"""
            self._send_response(500, "text/plain", result)

        def _send_response(self, code: int, content_type: str, body: str):
            """Send response with given code, content type and body"""
            self.send_response(code)
            self.send_header("Content-type", content_type)
            self.end_headers()
            self.wfile.write(body.encode())

        def get_query_args(self) -> dict[str, str]:
            """Parse query string and return dict of query args."""
            try:
                query = self.path.split("?")[1]
                return dict(qc.split("=") for qc in query.split("&"))
            except (IndexError, ValueError):
                return {}

        def handle_reverse_geocode_put(self, body: dict) -> tuple[bool, str]:
            """Perform reverse geocode of latitude/longitude in body."""
            success = False
            try:
                latitude = float(body["latitude"])
                longitude = float(body["longitude"])
                success = True
            except ValueError as e:
                result = f"Invalid latitude/longitude: {e}"

            if not success:
                return success, result

            return self.reverse_geocode(latitude, longitude)

        def reverse_geocode(
            self, latitude: float, longitude: float
        ) -> tuple[bool, str]:
            """Perform reverse geocode of latitude/longitude."""
            geocode_queue = queue.Queue()
            app.log(f"reverse_geocode: {geocode_queue=}, calling reverse_geocode")
            app.reverse_geocode(latitude, longitude, geocode_queue)

            try:
                success, result = geocode_queue.get(block=True, timeout=timeout)
                geocode_queue.task_done()
            except geocode_queue.Empty:
                success = False
                result = "Timeout waiting for reverse geocode to complete"
            return success, result

    http.server.ThreadingHTTPServer.allow_reuse_address = True
    with http.server.ThreadingHTTPServer(("", port), Handler) as httpd:
        app.log(f"serving at port {port}, with timeout {timeout}")
        with contextlib.suppress(KeyboardInterrupt):
            httpd.serve_forever()
        httpd.server_close()


def validate_latitude(latitude: str | float) -> bool:
    """Return True if latitude is valid, False otherwise"""
    try:
        latitude = float(latitude)
        return -90 <= latitude <= 90
    except ValueError:
        return False


def validate_longitude(longitude: str | float) -> bool:
    """Return True if longitude is valid, False otherwise"""
    try:
        longitude = float(longitude)
        return -180 <= longitude <= 180
    except ValueError:
        return False
