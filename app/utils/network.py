"""Request helpers."""

from starlette.requests import Request


def client_ip(request: Request) -> str:
    """Best available address of the caller.

    Behind a reverse proxy this is the *proxy's* address unless uvicorn is
    started with ``--proxy-headers`` and ``--forwarded-allow-ips`` pointing at
    that proxy (see README → Before deploying). Never read X-Forwarded-For by
    hand: any client can send it.
    """
    return request.client.host if request.client else "unknown"
