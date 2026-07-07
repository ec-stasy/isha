# Payments & license delivery

How money turns into a working, activated copy of Isha. The guiding rule from
the roadmap: **minimize backend.** Use a Merchant of Record so you never handle
tax or card data, and start with zero servers.

---

## The model

- **One-time purchase**, sold through a **Merchant of Record (MoR)** — Lemon
  Squeezy (recommended) or Paddle. The MoR is the legal seller: they take the
  payment, charge the right VAT/GST for the buyer's country, and remit it. You
  never register for tax anywhere or touch a card number.
- The buyer gets a **real Isha license key** — an Ed25519-signed token your app
  already knows how to verify **offline** (`a_licensing.py`). No activation
  server, no phone-home. This is the whole point of the offline-license design
  built in Cycle 1.
- You keep only the buyer's **name + email**, for delivery and updates. That's
  the entire data footprint (see the website's privacy policy).

---

## Two ways to deliver the key — start manual, automate later

### A) Manual fulfilment (launch with this — no server, no code running)

Perfect for your first sales. Total setup: a Lemon Squeezy account.

1. In Lemon Squeezy, create the product and set the price.
2. Turn on **order notification emails** to yourself.
3. When you get a sale, run (offline, on your own machine):
   ```
   python tools/generate_license.py sign --private-key <YOUR_PRIVATE_KEY_HEX> --email buyer@example.com
   ```
4. Copy the printed key into a reply email to the buyer with the download link.

That's a fully working store. It scales to a sale every few hours comfortably.
When copy-pasting keys becomes a chore, switch on (B).

### B) Automated fulfilment (this folder's webhook)

`license_webhook.py` does steps 3–4 automatically: Lemon Squeezy calls it on
every order, it signs the key and emails it. Setup:

1. **Generate the product keypair once** (if you haven't):
   ```
   python tools/generate_license.py keygen
   ```
   Public half → `a_licensing.py`. Private half → **kept secret**, and given to
   the webhook only via the `ISHA_LICENSE_PRIVATE_KEY_HEX` environment variable.
2. **Deploy** `license_webhook.py` to any Python host with HTTPS — Render,
   Railway, Fly.io, or a small VPS behind Caddy/Nginx. Set these env vars in the
   host's secret store (never in code):
   ```
   ISHA_LICENSE_PRIVATE_KEY_HEX = <private key hex>
   LS_WEBHOOK_SECRET            = <from Lemon Squeezy → Settings → Webhooks>
   SMTP_HOST / SMTP_PORT / SMTP_USER / SMTP_PASS / MAIL_FROM = your email sender
   ISHA_DOWNLOAD_URL            = https://your-domain.com/download
   ```
   Run it with gunicorn: `gunicorn -b 0.0.0.0:8000 license_webhook:app`.
3. In Lemon Squeezy → Settings → **Webhooks**, add
   `https://your-server/webhooks/lemonsqueezy`, subscribe to **order_created**,
   and copy the signing secret into `LS_WEBHOOK_SECRET`.
4. Test with Lemon Squeezy's **test mode** + "send test webhook", then a real
   test purchase. Check the buyer receives the email and `activate license
   <key>` works in the app. `GET /health` should return `ok`.

If SMTP isn't set, the webhook still signs every key and appends it to
`issued_licenses.jsonl` so you can deliver by hand — a paid key is never lost.

---

## Paddle instead of Lemon Squeezy?

Same shape. Paddle is also an MoR. Differences:
- Paddle requires your domain/site to be approved before going live.
- Its webhook is `transaction.completed`, signed differently (Paddle-Signature
  header, HMAC over `ts:body`). Add a `/webhooks/paddle` route mirroring the
  Lemon Squeezy one but with Paddle's verification — the signing/emailing half is
  identical.

## Gumroad?

Fastest to launch and also an MoR, but lower-polish checkout. It can email its
*own* license keys — but those aren't Isha's Ed25519 keys, so use Gumroad only
for payment + its "ping" webhook, and still sign the real key with this server
(or manually). Point its Ping URL at a `/webhooks/gumroad` route.

## India (Razorpay)

Razorpay is **not** a Merchant of Record — you'd be the seller of record and
responsible for GST yourself. Only add it once you have an Indian business
entity and GST registration. For a global indie launch, a single MoR
(Lemon Squeezy/Paddle) covering India-in-local-currency is simpler and legal
out of the box. Revisit Razorpay when India is a big enough share to justify the
compliance overhead.

---

## Security reminders

- The private key lives **only** in the server's env/secret store. Never commit
  it, never put it in the app, never email it.
- The webhook rejects any request whose HMAC signature doesn't match — a random
  caller can't make you sign licenses.
- Keep this service tiny and separate from everything else. It is the only
  place buyer email meets the signing key; that's by design (data minimization).
