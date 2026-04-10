# Documentation Website

This folder contains the static project website and documentation hub for the
Messaging and Calling Backend SDK.

The GitHub Pages published copy now lives in [`../docs/`](../docs/index.html).
This folder is kept as the editable working copy and local source mirror.

## Purpose

The site is intended to:

- explain what the SDK does
- show how to install and integrate it
- document the built-in feature surface
- provide copyable configuration and code snippets for customization

## Structure

- `index.html`: marketing-style landing page
- `docs.html`: full documentation page with copyable snippets
- `assets/styles.css`: shared visual system
- `assets/app.js`: copy-to-clipboard interactions
- `CNAME`: custom domain for GitHub Pages deployment

## Local preview

You can open `index.html` directly in a browser for a quick preview, or serve
the folder with any static file server.

Example:

```bash
python -m http.server 8080 --directory website
```

Then open `http://127.0.0.1:8080`.

## Production deployment

GitHub Pages is now intended to publish from the committed
[`../docs/`](../docs/index.html) folder on branch `main`.

Intended production domain:

```text
https://messagingandcallingbackend.credianlab.xyz
```

See [DEPLOYMENT.md](../DEPLOYMENT.md) for the full DNS and GitHub setup flow.
