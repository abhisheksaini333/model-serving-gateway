"""Bound request buffering and constrain the same-origin operator browser."""
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse


class TransportBoundary:
    def __init__(self, app, max_body=131072):
        self.app = app
        self.max_body = max_body

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = dict(scope.get("headers", []))
        length = headers.get(b"content-length", b"0")
        try:
            oversized = int(length) > self.max_body
        except ValueError:
            oversized = True
        if oversized:
            return await JSONResponse(
                {
                    "error": {
                        "code": "body_too_large",
                        "message": "Request body exceeds 128 KiB.",
                    }
                },
                status_code=413,
            )(scope, receive, send)
        consumed = 0

        async def bounded_receive():
            nonlocal consumed
            message = await receive()
            if message["type"] == "http.request":
                consumed += len(message.get("body", b""))
                if consumed > self.max_body:
                    raise HTTPException(413, "Request body exceeds 128 KiB.")
            return message

        async def secured_send(message):
            if message["type"] == "http.response.start":
                additions = [
                    (b"x-content-type-options", b"nosniff"),
                    (b"referrer-policy", b"no-referrer"),
                    (
                        b"content-security-policy",
                        b"default-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'",
                    ),
                ]
                message = dict(
                    message, headers=list(message.get("headers", [])) + additions
                )
            await send(message)

        await self.app(scope, bounded_receive, secured_send)
