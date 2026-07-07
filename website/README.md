# Isha website

A **static** marketing + purchase site — plain HTML/CSS, no framework, no build
step, no tracker. That means it's fast, cheap (free, in practice), and you can
host it anywhere. Open `index.html` in a browser right now to preview it.

```
website/
  index.html     landing + pricing + FAQ (the page that sells)
  privacy.html   privacy policy   ┐  required before most payment
  terms.html     terms of service ├  providers will approve you —
  refund.html    refund policy    ┘  don't skip these
  styles.css     shared styles (calm palette, mirrors the app's ui_theme.py)
```

---

## 1. Before you publish — find & replace the placeholders

Every editable spot is written in `[BRACKETS]` or `YOUR-...`. Search the whole
folder for these and replace:

| Placeholder | Put here |
|---|---|
| `YOUR-DOMAIN.com` | your real domain (in `mailto:` links) |
| `YOUR-STORE.lemonsqueezy.com/checkout/buy/YOUR-PRODUCT-ID` | your real checkout URL (see §3) |
| `$19` | your real price (appears a few times in `index.html`) |
| `[YOUR LEGAL NAME / COMPANY]`, `[COUNTRY]`, `[YOUR JURISDICTION]` | your details in the legal pages |
| `[Lemon Squeezy / Paddle]`, `[MoR privacy policy URL]` | your chosen payment partner |
| `[DATE]` | today's date on each legal page |

That's the whole checklist. Nothing else needs editing to go live.

---

## 2. Host it (pick one — all have a free tier)

**Cloudflare Pages (recommended)** — free, fast globally, free SSL, custom domain:
1. Push this repo to GitHub (or just the `website/` folder to its own repo).
2. Cloudflare dashboard → Pages → Connect to Git → pick the repo.
3. Build command: *(leave blank)*. Output directory: `website` (or `/` if you
   put these files at the repo root). Deploy.
4. Add your custom domain under the Pages project → Custom domains.

**Netlify** — same idea: New site from Git, no build command, publish directory
`website`. Or literally drag-and-drop the `website/` folder onto app.netlify.com.

**GitHub Pages** — free, but put the files at the repo root (or `/docs`), enable
Pages in repo Settings, and point your domain's DNS at GitHub. Slightly fiddlier
custom-domain setup than the two above.

You do **not** need a server for the website itself — it's just files. The only
server-side piece in this whole project is the optional license webhook, which
lives in `../server/` and is separate.

---

## 3. Wire up checkout

The site is payment-provider-agnostic: it's just a link. Recommended provider is
a **Merchant of Record (MoR)** so you never touch tax/VAT/GST yourself — see
`../server/README.md` for the full why and the license-delivery setup. Short
version for the *website*:

**Lemon Squeezy (simplest):**
1. Create the product in Lemon Squeezy, set the price.
2. Copy its "Buy" / checkout URL.
3. In `index.html`, replace the `href` on both "Buy Isha" buttons with it.
4. *(Optional, nicer)* For an on-page overlay instead of a redirect:
   uncomment the `lemon.js` `<script>` in `<head>` and add
   `class="lemonsqueezy-button"` to the buy button. Then `?embed=1` on the URL.

**Paddle:** create a product, use Paddle.js `Checkout.open({ items: [...] })` on
the button, or a Payment Link URL. Paddle needs your domain approved first.

**Gumroad (fastest to launch, less polished):** create the product, paste its
permalink URL on the buttons. Gumroad is also an MoR and can auto-generate &
email license keys — but its keys aren't Isha's Ed25519 keys, so you'd use the
manual/webhook signing flow in `../server/` to send the *real* key.

After wiring, click your own buy button end-to-end in the provider's **test
mode** before going live.

---

## 4. A note on the download link

Keep the actual installer **out** of the website repo (it's tens of MB and
changes every release). Host each release's `IshaSetup-x.y.z.exe` on GitHub
Releases, Cloudflare R2, or your MoR's "deliverables" attachment, and put that
URL in the post-purchase email (your MoR sends it automatically once configured).
The buyer flow is: pay → email with download link + license key → install →
`activate license <key>` in the app.
