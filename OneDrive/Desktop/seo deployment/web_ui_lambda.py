"""
Site Monitor Lambda Wrapper
Adds WSGI-to-ASGI shim for Mangum + Flask compatibility on Lambda.
"""
import os
import json
import io as _io

IS_LAMBDA = bool(os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))

# Import the Flask app from the existing web_ui module
from web_ui import app, send_daily_reports


class _FlaskAsgi:
    """Minimal WSGI-to-ASGI adapter for Flask on Lambda."""
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "lifespan":
            while True:
                message = await receive()
                if message["type"] == "lifespan.startup":
                    await send({"type": "lifespan.startup.complete"})
                elif message["type"] == "lifespan.shutdown":
                    await send({"type": "lifespan.shutdown.complete"})
                    return
                else:
                    return
        elif scope["type"] == "http":
            await self._handle_http(scope, receive, send)

    async def _handle_http(self, scope, receive, send):
        body_parts = []
        while True:
            message = await receive()
            body_parts.append(message.get("body", b""))
            if not message.get("more_body", False):
                break
        body = b"".join(body_parts)
        headers = dict(scope.get("headers", []))
        environ = {
            "REQUEST_METHOD": scope["method"],
            "SCRIPT_NAME": "",
            "PATH_INFO": scope["path"],
            "QUERY_STRING": scope.get("query_string", b"").decode("utf-8"),
            "SERVER_NAME": headers.get(b"host", b"localhost").decode("utf-8").split(":")[0],
            "SERVER_PORT": str(scope.get("server", ("", 80))[1]) if scope.get("server") else "80",
            "SERVER_PROTOCOL": "HTTP/{}".format(scope.get("http_version", "1.1")),
            "wsgi.version": (1, 0),
            "wsgi.url_scheme": scope.get("scheme", "https"),
            "wsgi.input": _io.BytesIO(body),
            "wsgi.errors": _io.BytesIO(),
            "wsgi.multithread": False,
            "wsgi.multiprocess": False,
            "wsgi.run_once": False,
            "CONTENT_LENGTH": str(len(body)),
        }
        for hdr_name, hdr_val in scope.get("headers", []):
            name = hdr_name.decode("utf-8").lower()
            val = hdr_val.decode("utf-8")
            if name == "content-type":
                environ["CONTENT_TYPE"] = val
            else:
                key = "HTTP_{}".format(name.upper().replace("-", "_"))
                environ[key] = val

        response_headers = []
        status_code = [500]

        def start_response(status, resp_headers, exc_info=None):
            status_code[0] = int(status.split(" ", 1)[0])
            response_headers.clear()
            response_headers.extend(resp_headers)

        output = self.wsgi_app(environ, start_response)
        body_out = b"".join(output)
        if hasattr(output, "close"):
            output.close()

        await send({
            "type": "http.response.start",
            "status": status_code[0],
            "headers": [(k.lower().encode(), v.encode()) for k, v in response_headers],
        })
        await send({
            "type": "http.response.body",
            "body": body_out,
        })


if IS_LAMBDA:
    from mangum import Mangum
    handler = Mangum(_FlaskAsgi(app), lifespan="off")
else:
    handler = None


def scheduled_report_handler(event, context):
    """Lambda handler for EventBridge scheduled rule (daily reports)."""
    result = send_daily_reports()
    return {"statusCode": 200, "body": json.dumps(result)}
