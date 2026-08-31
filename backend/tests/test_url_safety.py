import pytest

from studyrag_backend.services.url_safety import (
    UnsafeUrlError,
    canonicalize_url,
    is_public_ip,
    validate_public_url,
)


def test_canonicalize_url_normalizes_host_port_and_fragment() -> None:
    assert (
        canonicalize_url("HTTPS://WWW.RUNOOB.COM:443/mysql/mysql-tutorial.html#intro")
        == "https://www.runoob.com/mysql/mysql-tutorial.html"
    )


@pytest.mark.parametrize(
    "value",
    [
        "file:///etc/passwd",
        "https://user:password@example.com/",
        "https://example.com:8443/",
        "https:///missing-host",
    ],
)
def test_canonicalize_url_rejects_unsafe_shapes(value: str) -> None:
    with pytest.raises(UnsafeUrlError):
        canonicalize_url(value)


@pytest.mark.asyncio
async def test_validate_public_url_rejects_private_literal() -> None:
    with pytest.raises(UnsafeUrlError):
        await validate_public_url("http://127.0.0.1/admin")


def test_public_ip_classification() -> None:
    assert is_public_ip("8.8.8.8") is True
    assert is_public_ip("10.0.0.1") is False
    assert is_public_ip("198.18.1.29") is False
    assert is_public_ip("198.18.1.29", ["198.18.0.0/15"]) is True
