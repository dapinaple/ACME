# ACME Coupon Clipper

Automatically clip **ACME Markets** digital coupons based on your grocery list — on **iPhone**, without Xcode or a separate login.

## Important: how login works

ACME does **not** let third-party apps sign in the way their app and website do. If you created your account with **phone text verification**, you generally **cannot** sign into external tools directly.

**The supported approach:** use the **Safari clipper** while logged into [acmemarkets.com](https://www.acmemarkets.com) with your normal phone login.

## iPhone setup (recommended)

1. Run this project locally or on a server you control (`docker compose up --build`)
2. Open the app URL in Safari on your iPhone
3. Install the free [Userscripts](https://apps.apple.com/app/userscripts/id1463298887) app
4. In Userscripts, add this script URL from your server:

   `http://<your-server>/static/acme-clipper.user.js`

5. Open [ACME Coupons & Deals](https://www.acmemarkets.com/foru/coupons-deals.html) in Safari
6. Sign in with your **phone number** on ACME's site
7. Tap the red **A** button → enter your grocery list → **Clip Matching Coupons**

You can plan your list in this app's home screen and tap **Copy list for ACME site**.

## What it does

1. You stay logged in on ACME's own website (phone verification works)
2. The userscript adds a clipper panel on coupon pages
3. It matches coupons to your grocery list and clicks Clip for you

## Quick start (Docker)

```bash
docker compose up --build
```

Then open `http://<your-computer-ip>:8000` on your iPhone.

### Add to Home Screen

1. Open the app URL in **Safari**
2. Tap **Share** → **Add to Home Screen**

This home screen app is mainly for instructions and grocery-list planning. The actual clipping happens on acmemarkets.com.

## Finding your store

You don't need a store ID for the Safari clipper — ACME's site already knows your store when you're signed in.

The ZIP-based store finder in the backend is only for the legacy server login mode, which no longer works because ACME rotated their private API credentials.

## How coupon matching works

The clipper compares keywords from your grocery list (e.g. "milk", "chicken", "cereal") against coupon text on the page and clicks Clip on matches.

## Project structure

```
frontend/
  acme-clipper.user.js   # Runs on acmemarkets.com in Safari (main clipper)
  index.html             # iPhone guide + grocery list planner
backend/                 # Legacy server mode (login currently broken)
```

## Limitations

- Requires the Userscripts Safari extension (free)
- Only clips coupons visible on the current ACME coupons page (use "Load More" in the panel)
- Unofficial tool — not affiliated with ACME Markets or Albertsons
- ACME may change their website layout, which can break the clipper until it's updated

## Development

```bash
cd backend && python3 -m pytest tests/ -q
```

## License

MIT
