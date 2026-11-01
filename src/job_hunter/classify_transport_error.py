from enum import Enum
import httpx


class HttpTransportCategory(str, Enum):
    TRANSIENT = "transient"
    PERMANENT = "permanent"

def classify_transport_error(error: Exception) -> HttpTransportCategory:
    if isinstance(
        error,
        (
            httpx.ConnectTimeout,
            httpx.ReadTimeout,
            httpx.ConnectError,
            httpx.RemoteProtocolError,
        ),
    ):
        return HttpTransportCategory.TRANSIENT

    return HttpTransportCategory.PERMANENT
