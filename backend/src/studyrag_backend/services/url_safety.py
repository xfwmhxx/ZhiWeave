import asyncio
import ipaddress
import socket
from collections.abc import Sequence
from urllib.parse import SplitResult, urlsplit, urlunsplit


class UnsafeUrlError(ValueError):
    """Raised when a crawler URL could reach a private or unsupported target."""


def canonicalize_url(value: str) -> str:
    parsed = urlsplit(value.strip())
    if parsed.scheme.lower() not in {"http", "https"}:
        raise UnsafeUrlError("only http and https URLs are supported")
    if not parsed.hostname:
        raise UnsafeUrlError("URL must include a hostname")
    if parsed.username or parsed.password:
        raise UnsafeUrlError("URLs containing credentials are not allowed")

    scheme = parsed.scheme.lower()
    host = parsed.hostname.rstrip(".").lower()
    try:
        port = parsed.port
    except ValueError as exc:
        raise UnsafeUrlError("URL contains an invalid port") from exc
    if port not in {None, 80, 443}:
        raise UnsafeUrlError("only standard HTTP and HTTPS ports are allowed")

    default_port = (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
    netloc = host if port is None or default_port else f"{host}:{port}"
    path = parsed.path or "/"
    return urlunsplit(SplitResult(scheme, netloc, path, parsed.query, ""))


def is_public_ip(address: str, trusted_proxy_cidrs: Sequence[str] = ()) -> bool:
    ip = ipaddress.ip_address(address)
    if ip.is_global:
        return True
    return any(ip in ipaddress.ip_network(cidr) for cidr in trusted_proxy_cidrs)


async def validate_public_url(value: str, *, trusted_proxy_cidrs: Sequence[str] = ()) -> str:
    canonical = canonicalize_url(value)
    parsed = urlsplit(canonical)
    hostname = parsed.hostname
    if hostname is None:
        raise UnsafeUrlError("URL must include a hostname")

    try:
        literal_address = ipaddress.ip_address(hostname)
    except ValueError:
        literal_address = None
    if literal_address is not None:
        if not literal_address.is_global:
            raise UnsafeUrlError("private and reserved network addresses are not allowed")
        return canonical

    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    loop = asyncio.get_running_loop()
    try:
        results = await loop.getaddrinfo(
            hostname,
            port,
            family=socket.AF_UNSPEC,
            type=socket.SOCK_STREAM,
        )
    except socket.gaierror as exc:
        raise UnsafeUrlError("hostname could not be resolved") from exc
    addresses = {str(result[4][0]) for result in results}
    if not addresses or any(
        not is_public_ip(address, trusted_proxy_cidrs) for address in addresses
    ):
        raise UnsafeUrlError("hostname resolves to a private or reserved network address")
    return canonical
