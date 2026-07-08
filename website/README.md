# Isha website

A **static** marketing site — plain HTML/CSS, no framework, no build step, no
tracker. Fast, free to host anywhere. Open `index.html` in a browser to preview.

Isha is **free and fully local** — there is no pricing, no checkout, and no
license flow. The site's only call to action is "download it."

```
website/
  index.html         landing + features + Modes + privacy + FAQ
  how-it-works.html  full feature walkthrough
  privacy.html       privacy policy   ┐ short, because there's little to say —
  terms.html         terms of use     ┘ free software, no data collected
  styles.css         shared "Shizuka" styles — mirrors the app's design/tokens.py
                     (washi/yoru themes, sakura accent, ink-brush blossom motif)
```

The palette, type, radii, and blossom artwork are lifted 1:1 from the desktop
app's `design/tokens.py` and `assets/*.svg`, so the site and the product read as
the same object in both light and dark.

---

## 1. Before you publish — find & replace the placeholders

Every editable spot is written in `[BRACKETS]` or `YOUR-...`. Search the whole
folder and replace:

| Placeholder | Put here |
|---|---|
| `YOUR-DOMAIN.com` | your real domain (in `mailto:` links) |
| `github.com/ec-stasy/isha/releases/latest` | your real download URL, if different |
| `[YOUR LEGAL NAME / COMPANY]`, `[COUNTRY]`, `[YOUR JURISDICTION]` | your details in the legal pages |
| `[DATE]` | today's date on each legal page |

That's the whole checklist.

---

## 2. Host it (pick one — all free)

**Cloudflare Pages (recommended)** — free, fast globally, free SSL, custom domain:
1. Push this repo to GitHub (or just the `website/` folder to its own repo).
2. Cloudflare dashboard → Pages → Connect to Git → pick the repo.
3. Build command: *(leave blank)*. Output directory: `website` (or `/` if these
   files sit at the repo root). Deploy.
4. Add your custom domain under the Pages project → Custom domains.

**Netlify** — same idea: New site from Git, no build command, publish directory
`website`. Or drag-and-drop the `website/` folder onto app.netlify.com.

**GitHub Pages** — free; put the files at the repo root (or `/docs`), enable
Pages in Settings, point your domain's DNS at GitHub. (This repo already has a
Pages deploy workflow under `.github/`.)

No server is needed — it's just files.

---

## 3. The download link

Keep the actual build **out** of the website repo (it's tens of MB and changes
every release). Host each release's `IshaSetup-x.y.z.exe` / portable zip on
GitHub Releases or Cloudflare R2, and point the "Download" buttons in
`index.html` and `how-it-works.html` at it. The default already points at this
repo's GitHub Releases "latest" page.

The user flow is simply: **download → unzip / install → run.** No account, no
key, no activation.
