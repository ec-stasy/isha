"""
Seller-side offline tool (Track A3) — NOT imported by the Isha app itself,
and NOT something to ship to customers. Run this by hand to create the
update-manifest Ed25519 keypair (kept separate from the license keypair in
tools/generate_license.py — a compromised manifest key only lets someone
forge a fake update, a different blast radius than a compromised license
key) and again per release to sign a version manifest.

The public key half gets pasted into a_updater.py's
ISHA_UPDATE_PUBLIC_KEY_HEX; the private half must never be committed to this
repo — keep it offline. Anyone who gets it can sign a manifest pointing at a
malicious installer that Isha's updater would trust.

Signs the *canonical* JSON encoding of {version, url, sha256} (sorted keys,
no whitespace) — see a_updater.canonical_manifest_payload — not a
delimiter-joined string, so a field containing '|' can't make the signed
boundaries ambiguous.

Requires the optional 'cryptography' package — fine here since only the
seller runs this, never a customer machine.

Usage:
    python tools/sign_manifest.py keygen
        Prints a new public/private keypair (hex). Paste the public half into
        a_updater.ISHA_UPDATE_PUBLIC_KEY_HEX; store the private half offline.

    python tools/sign_manifest.py sign --private-key <hex> \\
        --version 1.2.0 --url https://cdn.example.com/isha-1.2.0.exe \\
        --sha256 <hex> [--notes "..."]
        Prints a ready-to-publish manifest JSON document.
"""
import argparse
import json
import sys


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


def _canonical_payload(version: str, url: str, sha256: str) -> bytes:
    return json.dumps(
        {"version": str(version), "url": str(url), "sha256": str(sha256)},
        sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")


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

    print("Public key  (paste into a_updater.ISHA_UPDATE_PUBLIC_KEY_HEX):")
    print(public_bytes.hex())
    print()
    print("Private key (keep OFFLINE — never commit, never share, needed for 'sign'):")
    print(private_bytes.hex())


def cmd_sign(args) -> None:
    _, _ = _load_ed25519()
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    import base64

    try:
        private_key = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(args.private_key))
    except ValueError:
        print("--private-key must be 64 hex characters (32 bytes).", file=sys.stderr)
        sys.exit(1)

    payload_bytes = _canonical_payload(args.version, args.url, args.sha256)
    signature = private_key.sign(payload_bytes)

    manifest = {
        "version": args.version,
        "url": args.url,
        "sha256": args.sha256,
        "signature": base64.b64encode(signature).decode("ascii"),
    }
    if args.notes:
        manifest["notes"] = args.notes

    print(json.dumps(manifest, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("keygen", help="Generate a new Ed25519 update-manifest keypair.").set_defaults(func=cmd_keygen)

    sign_parser = sub.add_parser("sign", help="Sign a version manifest for release.")
    sign_parser.add_argument("--private-key", required=True, help="Hex-encoded Ed25519 private key (from 'keygen').")
    sign_parser.add_argument("--version", required=True, help='e.g. "1.2.0"')
    sign_parser.add_argument("--url", required=True, help="HTTPS URL to the signed installer.")
    sign_parser.add_argument("--sha256", required=True, help="sha256 of the installer file, hex-encoded.")
    sign_parser.add_argument("--notes", default="", help="Optional release notes shown to users.")
    sign_parser.set_defaults(func=cmd_sign)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
