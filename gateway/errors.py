"""Stable safe errors; backend exception text never crosses the public API."""


class GatewayError(Exception):
    def __init__(self, code: str, message: str, status: int = 503):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status

    def payload(self):
        return {"error": {"code": self.code, "message": self.message}}
