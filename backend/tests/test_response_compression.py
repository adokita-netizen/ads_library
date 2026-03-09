import gzip

from app.core.response_compression import (
    brotli,
    choose_encoding,
    compress_payload,
    is_compressible_content_type,
    merge_vary_accept_encoding,
)


def test_is_compressible_content_type():
    assert is_compressible_content_type("application/json; charset=utf-8")
    assert is_compressible_content_type("text/plain")
    assert not is_compressible_content_type("image/png")


def test_choose_encoding_prefers_brotli_when_available():
    selected = choose_encoding(
        "gzip, br",
        allow_brotli=True,
        allow_gzip=True,
    )
    if brotli is not None:
        assert selected == "br"
    else:
        assert selected == "gzip"


def test_compress_payload_gzip_roundtrip():
    source = b'{"hello":"world"}' * 300
    compressed = compress_payload(source, "gzip", gzip_level=6, brotli_quality=5)
    restored = gzip.decompress(compressed)
    assert restored == source


def test_merge_vary_accept_encoding():
    assert merge_vary_accept_encoding(None) == "Accept-Encoding"
    assert merge_vary_accept_encoding("Origin") == "Origin, Accept-Encoding"
    assert merge_vary_accept_encoding("Origin, Accept-Encoding") == "Origin, Accept-Encoding"

