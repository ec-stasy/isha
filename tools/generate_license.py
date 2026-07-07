"""
Seller-side offline tool (Phase 6) — NOT imported by the Isha app itself, and
NOT something to ship to customers. Run this by hand, once, to create the
product's Ed25519 keypair, and again per sale to sign a license key for a
buyer. The public key half gets pasted into a_licensing.py's
ISHA_LICENSE_PUBLIC_KEY_HEX; the private key half must never be committed to
this repo or handed to anyone — keep it offline (password manager, hardware
key, encrypted USB drive, whatever your threat model calls for). Anyone who
gets the private key can mint valid licenses for anyone.

Requires the optional 'cryptography' package — fine here since only the
seller runs this, never a customer machine.

Usage:
    python tools/generate_license.py keygen
        Prints a new public/private keypair (hex). Paste the public half into
        a_licensing.ISHA_LICENSE_PUBLIC_KEY_HEX; store the private half offline.

    python tools/generate_license.py sign --private-key <hex> --email a@b.com \\
        [--license-id ID] [--expires-in-days N] [--max-devices N]
        Prints a license key string ready to email to the buyer.
"""
import argparse
import json
import sys
import time
import uuid


def _load_ed25519():
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import (
            Ed25519PrivateKey,
            Ed25519PublicKey,
        )
    except ImportError:
        print(
            "This tool needs the optional 'cryptography' package installed "
            "(pip install cryptography) — it's a seller-only dev tool, not shipped "
            "to customers, so it's fine for it to have a harder dependency.",
            file=sys.stderr,
        )
        sys.exit(1)
    return Ed25519PrivateKey, Ed25519PublicKey


def cmd_keygen(_args) -> None:
    Ed25519PrivateKey, _ = _load_ed25519()
    from cryptography.hazmat.primitives import serialization

    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    private_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )

    print("Public key  (paste into a_licensing.ISHA_LICENSE_PUBLIC_KEY_HEX):")
    print(public_bytes.hex())
    print()
    print("Private key (keep OFFLINE — never commit, never share, needed for 'sign'):")
    print(private_bytes.hex())


def cmd_sign(args) -> None:
    _, _ = _load_ed25519()
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    try:
        private_key = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(args.private_key))
    except ValueError:
        print("--private-key must be 64 hex characters (32 bytes).", file=sys.stderr)
        sys.exit(1)

    payload = {
        "license_id": args.license_id or uuid.uuid4().hex[:12],
        "email": args.email,
        "product": "isha",
        "issued_at": int(time.time()),
        "expires_at": int(time.time() + args.expires_in_days * 86400) if args.expires_in_days else None,
        "max_devices": args.max_devices,
    }
    payload_bytes = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    signature = private_key.sign(payload_bytes)

    license_key = f"{payload_bytes.hex()}.{signature.hex()}"

    print(f"License for {args.email} (id {payload['license_id']}):")
    print(license_key)
    print()
    print(f"Payload: {json.dumps(payload, indent=2)}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("keygen", help="Generate a new Ed25519 product keypair.").set_defaults(func=cmd_keygen)

    sign_parser = sub.add_parser("sign", help="Sign a license key for one buyer.")
    sign_parser.add_argument("--private-key", required=True, help="Hex-encoded Ed25519 private key (from 'keygen').")
    sign_parser.add_argument("--email", required=True, help="Buyer's email address.")
    sign_parser.add_argument("--license-id", default=None, help="Defaults to a random 12-hex-char id.")
    sign_parser.add_argument("--expires-in-days", type=int, default=None, help="Omit for a perpetual (one-time-purchase) license.")
    sign_parser.add_argument("--max-devices", type=int, default=2, help="Informational only — not enforced without an activation server.")
    sign_parser.set_defaults(func=cmd_sign)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
