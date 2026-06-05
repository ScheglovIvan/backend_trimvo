import base64
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.ec import ECDSA, EllipticCurvePublicKey
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
from cryptography.hazmat.primitives.asymmetric import padding as rsa_padding

logger = logging.getLogger(__name__)

# Apple Root CA - G3 (used for StoreKit 2 JWS certificate chain verification)
# Source: https://www.apple.com/certificateauthority/
APPLE_ROOT_CA_G3_PEM = b"""-----BEGIN CERTIFICATE-----
MIICQzCCAcmgAwIBAgIILcX8iNLFS5UwCgYIKoZIzj0EAwMwZzEbMBkGA1UEAxMS
QXBwbGUgUm9vdCBDQSAtIEczMSYwJAYDVQQLEx1BcHBsZSBDZXJ0aWZpY2F0aW9u
IEF1dGhvcml0eTETMBEGA1UEChMKQXBwbGUgSW5jLjELMAkGA1UEBhMCVVMwHhcN
MTQwNDMwMTgxOTA2WhcNMzkwNDMwMTgxOTA2WjBnMRswGQYDVQQDExJBcHBsZSBS
b290IENBIC0gRzMxJjAkBgNVBAsTHUFwcGxlIENlcnRpZmljYXRpb24gQXV0aG9y
aXR5MRMwEQYDVQQKEwpBcHBsZSBJbmMuMQswCQYDVQQGEwJVUzB2MBAGByqGSM49
AgEGBSuBBAAiA2IABJjpLz1AcqTtkyJygnnkNkA/T2m9YH0/VAb7RFkFCkKZD47j
U7j1aVGIJdZrW4fA2yRYLrRVMSIlpMnqAUfhpDBVkLBzMcWJ9jAKFI5Z3qZA36an
7DzZYiJH1bqXU6NjMGEwHQYDVR0OBBYEFLuw3qFYM4iapIqZ3r6sABzXqFzfMA8G
A1UdEwEB/wQFMAMBAf8wDgYDVR0PAQH/BAQDAgEGMB8GA1UdIwQYMBaAFLuw3qFY
M4iapIqZ3r6sABzXqFzfMAoGCCqGSM49BAMDA2gAMGUCMQCD6cHEFl4aXTQY2e3v
9GwOAEZLuN/yxC2/Z60JdEP36FMOR1kT6m7X/ItDJ5LFzHACMDR2LhWb+J7d8t8+
LMoGOWiL7vSDIBMvGJHEXEhiEcECpXJ9z3DUeJEsM5XOAA==
-----END CERTIFICATE-----"""

_APPLE_ROOT_CA_G3_FINGERPRINT: Optional[bytes] = None


def _get_root_fingerprint() -> bytes:
    global _APPLE_ROOT_CA_G3_FINGERPRINT
    if _APPLE_ROOT_CA_G3_FINGERPRINT is None:
        cert = x509.load_pem_x509_certificate(APPLE_ROOT_CA_G3_PEM, default_backend())
        _APPLE_ROOT_CA_G3_FINGERPRINT = cert.fingerprint(hashes.SHA256())
    return _APPLE_ROOT_CA_G3_FINGERPRINT


def _b64url_decode(s: str) -> bytes:
    padding = 4 - len(s) % 4
    if padding != 4:
        s += "=" * padding
    return base64.urlsafe_b64decode(s)


def _load_cert_from_b64der(b64_der: str) -> x509.Certificate:
    der_bytes = base64.b64decode(b64_der)
    return x509.load_der_x509_certificate(der_bytes, default_backend())


def _verify_cert_signed_by(child: x509.Certificate, issuer: x509.Certificate) -> None:
    issuer_pub = issuer.public_key()
    if isinstance(issuer_pub, EllipticCurvePublicKey):
        issuer_pub.verify(
            child.signature,
            child.tbs_certificate_bytes,
            ECDSA(child.signature_hash_algorithm),
        )
    elif isinstance(issuer_pub, RSAPublicKey):
        issuer_pub.verify(
            child.signature,
            child.tbs_certificate_bytes,
            rsa_padding.PKCS1v15(),
            child.signature_hash_algorithm,
        )
    else:
        raise ValueError(f"Unsupported issuer key type: {type(issuer_pub)}")


def _verify_cert_chain(x5c: List[str]) -> x509.Certificate:
    """Verify x5c cert chain against Apple Root CA G3. Returns leaf cert."""
    if len(x5c) < 2:
        raise ValueError("Certificate chain must have at least 2 entries")

    certs = [_load_cert_from_b64der(c) for c in x5c]

    for i in range(len(certs) - 1):
        try:
            _verify_cert_signed_by(certs[i], certs[i + 1])
        except (InvalidSignature, Exception) as e:
            raise ValueError(f"Certificate chain broken at index {i}: {e}")

    root = certs[-1]
    if root.fingerprint(hashes.SHA256()) != _get_root_fingerprint():
        raise ValueError("Root certificate does not match Apple Root CA G3")

    return certs[0]


def decode_and_verify_jws(jws: str) -> Dict[str, Any]:
    """
    Verify an Apple StoreKit 2 signed JWS and return its payload.
    Raises ValueError if the signature or cert chain is invalid.
    """
    parts = jws.split(".")
    if len(parts) != 3:
        raise ValueError("Invalid JWS: expected 3 parts")

    header_b64, payload_b64, signature_b64 = parts

    header: Dict = json.loads(_b64url_decode(header_b64))
    alg = header.get("alg", "")
    x5c: List[str] = header.get("x5c", [])

    if not x5c:
        raise ValueError("JWS header missing x5c certificate chain")

    _alg_to_hash = {"ES256": hashes.SHA256(), "ES384": hashes.SHA384(), "ES512": hashes.SHA512()}
    hash_algo = _alg_to_hash.get(alg)
    if hash_algo is None:
        raise ValueError(f"Unsupported JWS algorithm: {alg}")

    leaf_cert = _verify_cert_chain(x5c)

    signing_input = f"{header_b64}.{payload_b64}".encode()
    signature = _b64url_decode(signature_b64)

    leaf_pub = leaf_cert.public_key()
    if not isinstance(leaf_pub, EllipticCurvePublicKey):
        raise ValueError("Leaf certificate must use an EC key")

    try:
        leaf_pub.verify(signature, signing_input, ECDSA(hash_algo))
    except InvalidSignature:
        raise ValueError("JWS signature verification failed")

    return json.loads(_b64url_decode(payload_b64))


def ms_to_datetime(ms: Optional[int]) -> Optional[datetime]:
    """Convert Apple millisecond timestamp to UTC datetime."""
    if ms is None:
        return None
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)


def parse_transaction_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize raw JWS payload into a clean transaction dict."""
    return {
        "transaction_id": payload.get("transactionId"),
        "original_transaction_id": payload.get("originalTransactionId"),
        "bundle_id": payload.get("bundleId"),
        "product_id": payload.get("productId"),
        "quantity": int(payload.get("quantity", 1)),
        "type": payload.get("type"),  # Consumable, Auto-Renewable Subscription, etc.
        "purchase_date": ms_to_datetime(payload.get("purchaseDate")),
        "original_purchase_date": ms_to_datetime(payload.get("originalPurchaseDate")),
        "expires_date": ms_to_datetime(payload.get("expiresDate")),
        "environment": payload.get("environment"),  # Sandbox | Production
        "in_app_ownership_type": payload.get("inAppOwnershipType"),
        "transaction_reason": payload.get("transactionReason"),
        "revocation_date": ms_to_datetime(payload.get("revocationDate")),
        "revocation_reason": payload.get("revocationReason"),
    }
