"""Tests for the AIA TLS chain-repair helper and the download retry path."""

import datetime
import ssl
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import AuthorityInformationAccessOID, ExtendedKeyUsageOID, NameOID

from datagouv_mcp_tn.helpers import file_parser, tls_chain
from datagouv_mcp_tn.helpers.config import get_settings


def _make_cert(
    common_name: str,
    issuer_name: x509.Name | None = None,
    aia_url: str | None = None,
) -> x509.Certificate:
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
    issuer = issuer_name if issuer_name is not None else subject
    key = ec.generate_private_key(ec.SECP256R1())
    builder = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime(2025, 1, 1))
        .not_valid_after(datetime.datetime(2026, 1, 1))
    )
    if aia_url is not None:
        builder = builder.add_extension(
            x509.AuthorityInformationAccess(
                [
                    x509.AccessDescription(
                        AuthorityInformationAccessOID.CA_ISSUERS,
                        x509.UniformResourceIdentifier(aia_url),
                    ),
                    x509.AccessDescription(
                        AuthorityInformationAccessOID.OCSP,
                        x509.UniformResourceIdentifier("http://ocsp.example.com"),
                    ),
                ]
            ),
            critical=False,
        )
    signing_key = key if issuer == subject else ec.generate_private_key(ec.SECP256R1())
    return builder.sign(signing_key, hashes.SHA256())


class TestExtractAiaIssuerUrls:
    def test_returns_ca_issuers_url_only(self):
        cert = _make_cert("leaf.example", aia_url="http://crt.example/intermediate.crt")
        urls = tls_chain.extract_aia_issuer_urls(cert.public_bytes(serialization.Encoding.DER))
        assert urls == ["http://crt.example/intermediate.crt"]

    def test_no_aia_extension(self):
        cert = _make_cert("bare.example")
        der = cert.public_bytes(serialization.Encoding.DER)
        assert tls_chain.extract_aia_issuer_urls(der) == []

    def test_accepts_pem_input(self):
        cert = _make_cert("pem.example", aia_url="https://crt.example/ca.pem")
        assert tls_chain.extract_aia_issuer_urls(cert.public_bytes(serialization.Encoding.PEM)) == [
            "https://crt.example/ca.pem"
        ]


class TestLoadCert:
    def test_der_and_pem(self):
        cert = _make_cert("dual.example")
        der = cert.public_bytes(serialization.Encoding.DER)
        pem = cert.public_bytes(serialization.Encoding.PEM)
        assert tls_chain._load_cert(der).subject == cert.subject
        assert tls_chain._load_cert(pem).subject == cert.subject


class TestIsCertVerifyError:
    def test_direct(self):
        err = ssl.SSLCertVerificationError(20, "unable to get local issuer certificate")
        assert tls_chain.is_cert_verify_error(err)

    def test_wrapped_in_connect_error(self):
        inner = ssl.SSLCertVerificationError(20, "unable to get local issuer certificate")
        wrapped = httpx.ConnectError("boom")
        wrapped.__cause__ = inner
        assert tls_chain.is_cert_verify_error(wrapped)

    def test_unrelated_error(self):
        assert not tls_chain.is_cert_verify_error(ValueError("nope"))
        assert not tls_chain.is_cert_verify_error(httpx.ConnectError("timeout-ish"))


class TestFetchResourceBytesFallback:
    async def test_retries_with_resolved_context(self, monkeypatch):
        tls_chain.reset_cache()
        calls: list[object] = []

        async def fake_stream(url, *, limit_mb, verify=True):
            calls.append(verify)
            if verify is True:
                err = httpx.ConnectError("ssl bad")
                err.__cause__ = ssl.SSLCertVerificationError(
                    20, "unable to get local issuer certificate"
                )
                raise err
            return b"csv,data\n1,2\n"

        sentinel_ctx = MagicMock(spec=ssl.SSLContext)

        async def fake_resolve(host, port=443):
            return sentinel_ctx

        monkeypatch.setattr(file_parser, "_stream_download", fake_stream)
        monkeypatch.setattr(file_parser, "resolve_chain_context", fake_resolve)
        result = await file_parser.fetch_resource_bytes("https://host.example/file.csv")
        assert result == b"csv,data\n1,2\n"
        assert calls[0] is True
        assert calls[1] is sentinel_ctx

    async def test_no_retry_when_resolution_fails(self, monkeypatch):
        tls_chain.reset_cache()

        async def fake_stream(url, *, limit_mb, verify=True):
            err = httpx.ConnectError("ssl bad")
            err.__cause__ = ssl.SSLCertVerificationError(20, "verify failed")
            raise err

        async def fake_resolve(host, port=443):
            return None

        monkeypatch.setattr(file_parser, "_stream_download", fake_stream)
        monkeypatch.setattr(file_parser, "resolve_chain_context", fake_resolve)
        with pytest.raises(httpx.ConnectError):
            await file_parser.fetch_resource_bytes("https://host.example/file.csv")

    async def test_no_retry_when_disabled(self, monkeypatch):
        settings = get_settings()
        monkeypatch.setattr(settings, "tls_aia_fallback", False)
        calls: list[object] = []

        async def fake_stream(url, *, limit_mb, verify=True):
            calls.append(verify)
            err = httpx.ConnectError("ssl bad")
            err.__cause__ = ssl.SSLCertVerificationError(20, "verify failed")
            raise err

        resolve_spy = AsyncMock(side_effect=AssertionError("should not be called"))

        monkeypatch.setattr(file_parser, "_stream_download", fake_stream)
        monkeypatch.setattr(file_parser, "resolve_chain_context", resolve_spy)
        with pytest.raises(httpx.ConnectError):
            await file_parser.fetch_resource_bytes("https://host.example/file.csv")
        assert len(calls) == 1

    async def test_no_retry_for_non_tls_errors(self, monkeypatch):
        async def fake_stream(url, *, limit_mb, verify=True):
            raise httpx.ConnectError("connection refused")

        monkeypatch.setattr(file_parser, "_stream_download", fake_stream)
        with pytest.raises(httpx.ConnectError):
            await file_parser.fetch_resource_bytes("https://host.example/file.csv")

    async def test_http_urls_never_trigger_fallback(self, monkeypatch):
        async def fake_stream(url, *, limit_mb, verify=True):
            raise httpx.ConnectError("refused")

        monkeypatch.setattr(file_parser, "_stream_download", fake_stream)
        resolve_spy = AsyncMock()
        monkeypatch.setattr(tls_chain, "resolve_chain_context", resolve_spy)
        with pytest.raises(httpx.ConnectError):
            await file_parser.fetch_resource_bytes("http://host.example/file.csv")


class TestResolveChainContextUnit:
    async def test_returns_cached_context(self, monkeypatch):
        tls_chain.reset_cache()
        sentinel_ctx = MagicMock(spec=ssl.SSLContext)
        tls_chain._resolved_hosts["cached.example:443"] = sentinel_ctx

        fetch_spy = AsyncMock(side_effect=AssertionError("should not hit network"))

        monkeypatch.setattr(tls_chain, "_fetch_leaf_cert", fetch_spy)
        result = await tls_chain.resolve_chain_context("cached.example")
        assert result is sentinel_ctx
        tls_chain.reset_cache()

    async def test_none_when_leaf_has_no_aia(self, monkeypatch):
        tls_chain.reset_cache()
        cert = _make_cert("noaia.example")

        async def fake_fetch(host, port=443):
            return cert.public_bytes(serialization.Encoding.DER)

        monkeypatch.setattr(tls_chain, "_fetch_leaf_cert", fake_fetch)
        assert await tls_chain.resolve_chain_context("noaia.example") is None

    async def test_self_signed_root_is_not_trusted_as_anchor(self, monkeypatch):
        """A fetched self-signed 'root' must never become a trust anchor."""
        tls_chain.reset_cache()
        root = _make_cert("Evil Root Example")
        leaf = _make_cert(
            "leaf.example", issuer_name=root.subject, aia_url="http://crt.example/root.p7c"
        )

        async def fake_fetch(host, port=443):
            return leaf.public_bytes(serialization.Encoding.DER)

        async def fake_get(url, **kwargs):
            response = MagicMock()
            response.raise_for_status = lambda: None
            response.content = root.public_bytes(serialization.Encoding.DER)
            return response

        monkeypatch.setattr(tls_chain, "_fetch_leaf_cert", fake_fetch)
        with patch.object(tls_chain.httpx, "AsyncClient") as client_cls:
            client = MagicMock()
            client.get = fake_get
            client.__aenter__ = AsyncMock(return_value=client)
            client.__aexit__ = AsyncMock(return_value=False)
            client_cls.return_value = client

            probe_spy = AsyncMock(return_value=False)
            monkeypatch.setattr(tls_chain, "_probe_ok", probe_spy)
            result = await tls_chain.resolve_chain_context("evil.example")

        assert result is None
        # The self-signed root was fetched but never added as an anchor
        assert tls_chain._resolved_hosts == {}

    async def test_network_failure_returns_none(self, monkeypatch):
        tls_chain.reset_cache()

        async def fail_fetch(host, port=443):
            raise TimeoutError("connect timed out")

        monkeypatch.setattr(tls_chain, "_fetch_leaf_cert", fail_fetch)
        assert await tls_chain.resolve_chain_context("unreachable.example") is None


class TestExtendedKeyUsageOidSanity:
    """Guards against accidental removal of imports used by cert generation."""

    def test_oid_present(self):
        assert ExtendedKeyUsageOID.SERVER_AUTH.dotted_string == "1.3.6.1.5.5.7.3.1"
