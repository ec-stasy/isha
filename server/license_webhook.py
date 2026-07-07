"""
Isha license-fulfilment webhook (Cycle 3 / Track D2).

This is the ONE small server in the whole project. It closes the loop between
"customer paid" and "customer has a real Isha license key", automatically:

    Merchant of Record (Lemon Squeezy) --order_created webhook--> this server
        -> verify the webhook signature (so only your MoR can trigger it)
        -> sign an Ed25519 license for the buyer's email (same format as
           tools/generate_license.py and a_licensing.py verify)
        -> email the key to the buyer (or hand it back to the MoR)

It holds the product PRIVATE KEY, so it is the most security-sensitive piece of
the project. Read the SECURITY notes below before deploying.

------------------------------------------------------------------------------
YOU MAY NOT NEED THIS ON DAY ONE. Manual fulfilment works fine for your first
sales and needs no server at all — see server/README.md ("Manual fulfilment").
Automate with this webhook once the volume makes manual annoying.
------------------------------------------------------------------------------

Run (local test):
    pip install -r server/requirements.txt
    export ISHA_LICENSE_PRIVATE_KEY_HEX=...   # from: python tools/generate_license.py keygen
    export LS_WEBHOOK_SECRET=...              # from Lemon Squeezy webhook settings
    export SMTP_HOST=... SMTP_USER=... SMTP_PASS=... MAIL_FROM=you@your-domain.com
    python server/license_webhook.py         # dev server on :8000
Deploy: any host that runs Python behind HTTPS (Render, Railway, Fly.io, a small
VPS). Put it behind TLS; never expose it over plain HTTP.

SECURITY:
  * The private key comes ONLY from the ISHA_LICENSE_PRIVATE_KEY_HEX environment
    variable — never hardcode it, never commit it. Anyone with this key can mint
    valid Isha licenses for anyone.
  * Every request is rejected unless its HMAC signature matches LS_WEBHOOK_SECRET,
    so a random internet caller can't make you sign licenses.
  * Keep the deploy locked down (secrets in the host's secret store, minimal
    access). This box signing keys is exactly the "minimal separate service"
    the roadmap's data-minimization section calls for.
"""
import hashlib
import hmac
import json
import os
import smtplib
import sys
import time
import uuid
from email.message import EmailMessage

from flask import Flask, request, abort

app = Flask(__name__)

# --- config from environment (never hardcode secrets) ------------------------
PRIVATE_KEY_HEX = os.environ.get("ISHA_LICENSE_PRIVATE_KEY_HEX", "")
LS_WEBHOOK_SECRET = os.environ.get("LS_WEBHOOK_SECRET", "")
EXPIRES_IN_DAYS = int(os.environ.get("ISHA_LICENSE_EXPIRES_IN_DAYS", "0")) or None  # 0/unset = perpetual
MAX_DEVICES = int(os.environ.get("ISHA_LICENSE_MAX_DEVICES", "2"))
DOWNLOAD_URL = os.environ.get("ISHA_DOWNLOAD_URL", "https://YOUR-DOMAIN.com/download")

SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")
MAIL_FROM = os.environ.get("MAIL_FROM", SMTP_USER)

# Fallback store: if email isn't configured, issued keys are appended here so you
# can still deliver them by hand and nothing is ever lost.
ISSUED_LOG = os.environ.get("ISHA_ISSUED_LOG", "issued_licenses.jsonl")


def _sign_license(email: str, license_id: str) -> str:
    """Produce a license key byte-for-byte compatible with a_licensing.py's
    verifier and tools/generate_license.py's signer: canonical JSON payload,
    Ed25519 signature, hex-encoded, joined by a dot."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    private_key = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(PRIVATE_KEY_HEX))
    payload = {
        "license_id": license_id,
        "email": email,
        "product": "isha",
        "issued_at": int(time.time()),
        "expires_at": int(time.time() + EXPIRES_IN_DAYS * 86400) if EXPIRES_IN_DAYS else None,
        "max_devices": MAX_DEVICES,
    }
    payload_bytes = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    signature = private_key.sign(payload_bytes)
    return f"{payload_bytes.hex()}.{signature.hex()}"


def _verify_ls_signature(raw_body: bytes, header_sig: str) -> bool:
    """Lemon Squeezy signs each webhook with HMAC-SHA256(secret, raw_body),
    sent hex in the X-Signature header. Reject anything that doesn't match —
    this is what stops a stranger from making us sign licenses."""
    if not LS_WEBHOOK_SECRET or not header_sig:
        return False
    expected = hmac.new(LS_WEBHOOK_SECRET.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header_sig)


def _deliver(email: str, license_key: str, license_id: str) -> None:
    """Email the key to the buyer; if SMTP isn't configured, persist it so it
    can be delivered by hand. Never drop a paid-for key on the floor."""
    record = {"ts": int(time.time()), "email": email, "license_id": license_id, "key": license_key}

    if not (SMTP_HOST and MAIL_FROM):
        with open(ISSUED_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
        print(f"[issued] {email} (no SMTP configured — logged to {ISSUED_LOG})", file=sys.stderr)
        return

    msg = EmailMessage()
    msg["Subject"] = "Your Isha license key"
    msg["From"] = MAIL_FROM
    msg["To"] = email
    msg.set_content(
        f"""Thank you for buying Isha!

1. Download Isha:  {DOWNLOAD_URL}
2. Install and open it (look for the tray icon).
3. Press the palette hotkey and type:

       activate license {license_key}

That's it — activation happens entirely on your machine, offline.

Keep this key safe; you can use it on up to {MAX_DEVICES} of your own devices.

Need help? Just reply to this email.
"""
    )
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
        s.starttls()
        if SMTP_USER:
            s.login(SMTP_USER, SMTP_PASS)
        s.send_message(msg)
    # Also keep a local record for your books / re-sends.
    with open(ISSUED_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
    print(f"[issued] emailed key to {email} (license {license_id})", file=sys.stderr)


@app.route("/webhooks/lemonsqueezy", methods=["POST"])
def lemonsqueezy_webhook():
    raw = request.get_data()
    if not _verify_ls_signature(raw, request.headers.get("X-Signature", "")):
        abort(401, "bad signature")

    event = request.headers.get("X-Event-Name", "")
    payload = json.loads(raw)

    # Only fulfil on a completed order. Ignore refunds/subscription events here.
    if event not in ("order_created",):
        return ("ignored", 200)

    attrs = payload.get("data", {}).get("attributes", {})
    email = attrs.get("user_email") or attrs.get("customer_email")
    if not email:
        abort(400, "no buyer email in payload")

    # Idempotency: reuse the MoR's order id as the license id where possible, so a
    # re-delivered webhook doesn't mint a second key for the same order.
    order_id = str(payload.get("data", {}).get("id") or uuid.uuid4().hex[:12])
    license_id = f"ls-{order_id}"

    if not PRIVATE_KEY_HEX:
        abort(500, "server misconfigured: ISHA_LICENSE_PRIVATE_KEY_HEX not set")

    license_key = _sign_license(email, license_id)
    _deliver(email, license_key, license_id)
    return ("ok", 200)


@app.route("/health", methods=["GET"])
def health():
    return ("ok" if PRIVATE_KEY_HEX and LS_WEBHOOK_SECRET else "unconfigured", 200)


if __name__ == "__main__":
    if not PRIVATE_KEY_HEX:
        print("WARNING: ISHA_LICENSE_PRIVATE_KEY_HEX is not set — signing will fail.", file=sys.stderr)
    app.run(host="127.0.0.1", port=8000, debug=False)
