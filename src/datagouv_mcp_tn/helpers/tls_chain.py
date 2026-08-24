"""TLS chain repair for servers that omit intermediate certificates.

Some portals (notably ``catalog.data.gov.tn``) present a leaf certificate
whose issuing intermediate is missing from the served chain, so standard
verification fails with ``unable to get local issuer certificate``.

``resolve_chain_context`` recovers by fetching the missing intermediates
via the certificate's AIA "CA Issuers" URLs (RFC 5280 §4.2.2.1) and
building an ``ssl.SSLContext`` that carries them. Verification strength
is unchanged: the assembled path must still anchor to a root in the
system trust store, otherwise the probe handshake fails and no context
is returned.
"""

import asyncio
import logging
import ssl
import warnings

import httpx
from cryptography import x509
from cryptography.hazmat.primitives.serialization import Encoding, pkcs7
from cryptography.x509.oid import AuthorityInformationAccessOID, ExtensionOID

logger = logging.getLogger(__name__)

_MAX_AIA_DEPTH = 3
_PROBE_TIMEOUT = 15.0

_resolved_hosts: dict[str, ssl.SSLContext] = {}


def is_cert_verify_error(exc: BaseException) -> bool:
    """True if the exception (or its cause chain) is a TLS certificate verification failure."""
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, ssl.SSLCertVerificationError):
            return True
        current = current.__cause__ or current.__context__
    return False


def extract_aia_issuer_urls(cert_der: bytes) -> list[str]:
    """Return the AIA 'CA Issuers' http(s) URLs advertised by a certificate."""
    cert = _load_cert(cert_der)
    try:
        aia = cert.extensions.get_extension_for_oid(ExtensionOID.AUTHORITY_INFORMATION_ACCESS).value
    except x509.ExtensionNotFound:
        return []
    if not isinstance(aia, x509.AuthorityInformationAccess):
        return []
    urls: list[str] = []
    for desc in aia:
        if desc.access_method != AuthorityInformationAccessOID.CA_ISSUERS:
            continue
        location = desc.access_location
        if isinstance(location, x509.UniformResourceIdentifier) and location.value.startswith(
            ("http://", "https://")
        ):
            urls.append(location.value)
    return urls


async def _fetch_leaf_cert(host: str, port: int) -> bytes:
    """Connect with verification disabled and return the peer certificate (DER).

    Only the public certificate blob is used; every byte of it is later
    re-verified against system roots before the resulting context is usable.
    """
    insecure = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    insecure.check_hostname = False
    insecure.verify_mode = ssl.CERT_NONE
    reader, writer = await asyncio.wait_for(
        asyncio.open_connection(host, port, ssl=insecure, server_hostname=host),
        timeout=_PROBE_TIMEOUT,
    )
    del reader
    try:
        ssl_object = writer.get_extra_info("ssl_object")
        der = ssl_object.getpeercert(binary_form=True)
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except OSError:
            pass
    if not der:
        raise ValueError(f"No peer certificate presented by {host}:{port}")
    return der


def _load_cert(raw: bytes) -> x509.Certificate:
    """Load a certificate from DER, PEM, or PKCS#7/.p7c bytes."""
    try:
        if b"-----BEGIN CERTIFICATE-----" in raw:
            return x509.load_pem_x509_certificate(raw)
        return x509.load_der_x509_certificate(raw)
    except ValueError:
        pass
    if b"-----BEGIN" in raw:
        certs = pkcs7.load_pem_pkcs7_certificates(raw)
    else:
        with warnings.catch_warnings():
            # Some CAs ship slightly non-canonical .p7c files; the fallback is fine
            warnings.simplefilter("ignore", UserWarning)
            certs = pkcs7.load_der_pkcs7_certificates(raw)
    if not certs:
        raise ValueError("PKCS#7 payload contains no certificates")
    return certs[0]


def _cert_to_pem(cert: x509.Certificate) -> str:
    """Serialize a certificate as PEM text."""
    return cert.public_bytes(Encoding.PEM).decode("ascii")


async def resolve_chain_context(host: str, port: int = 443) -> ssl.SSLContext | None:
    """Build an SSLContext carrying intermediates fetched via AIA for ``host``.

    Returns a context proven by a verified probe handshake, a cached context
    from an earlier resolution, or ``None`` when recovery is impossible.

    Self-signed certificates encountered while walking the AIA chain are
    never added as trust anchors: verification must anchor to a root that
    is already trusted locally.
    """
    cache_key = f"{host}:{port}"
    cached = _resolved_hosts.get(cache_key)
    if cached is not None:
        return cached

    pem_parts: list[str] = []
    try:
        current_der = await _fetch_leaf_cert(host, port)
        for _ in range(_MAX_AIA_DEPTH):
            cert = _load_cert(current_der)
            if cert.issuer == cert.subject:
                break
            urls = extract_aia_issuer_urls(current_der)
            if not urls:
                break
            async with httpx.AsyncClient(timeout=_PROBE_TIMEOUT, follow_redirects=True) as client:
                response = await client.get(urls[0])
                response.raise_for_status()
                raw = response.content
            issuer = _load_cert(raw)
            if issuer.issuer == issuer.subject:
                # Root reached; it must already be in the local trust store.
                break
            pem_parts.append(_cert_to_pem(issuer))
            current_der = issuer.public_bytes(Encoding.DER)
    except Exception:
        logger.debug("AIA chain resolution failed for %s:%s", host, port, exc_info=True)
        return None

    if not pem_parts:
        return None

    context = ssl.create_default_context()
    try:
        context.load_verify_locations(cadata="\n".join(pem_parts))
    except ssl.SSLError:
        logger.debug("Fetched intermediates for %s failed to parse", host)
        return None

    if not await _probe_ok(context, host, port):
        return None

    _resolved_hosts[cache_key] = context
    logger.info("Recovered missing TLS intermediate certificates for %s via AIA", host)
    return context


async def _probe_ok(context: ssl.SSLContext, host: str, port: int) -> bool:
    """True if a full TLS handshake verifies against this context."""
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port, ssl=context, server_hostname=host),
            timeout=_PROBE_TIMEOUT,
        )
        del reader
        writer.close()
        await writer.wait_closed()
    except Exception:
        logger.debug("Probe handshake failed for %s:%s", host, port, exc_info=True)
        return False
    return True


def reset_cache() -> None:
    """Clear resolved contexts (for tests)."""
    _resolved_hosts.clear()
