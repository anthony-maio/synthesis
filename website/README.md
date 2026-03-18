# Synthesis Website

Static website package for Synthesis.

## Deploy Model

This site is intentionally no-build:

- `index.html`
- `style.css`
- `app.js`

That makes it suitable for:

- GitHub Pages
- Cloudflare Pages
- any static file host

## Local Preview

```bash
cd website
python -m http.server 8000
```

Then open `http://localhost:8000`.

## Publishing

You can publish this in two straightforward ways:

1. keep it in this repo and deploy `website/`
2. copy `website/` into a dedicated site repo such as `synthesis-web`
