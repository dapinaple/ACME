# ACME Coupon Clipper

A mobile-friendly web app that automatically clips **ACME Markets** digital coupons based on your grocery list. Open it in Safari on your iPhone and add it to your Home Screen — no App Store or Xcode required.

## What it does

1. Signs in with your existing **ACME for U** account
2. Lets you build a grocery list (or sync items from your ACME app list)
3. Finds digital coupons that match items on your list
4. Clips those coupons to your loyalty card with one tap

ACME does **not** offer a public developer API. This app uses the same internal platform that powers the ACME/Safeway mobile apps (Albertsons Okta login + Nimbus coupon services). That means:

- You need your ACME for U **phone number or email** and a **password**
- You need your local **Store ID** (use ZIP lookup in the app — see below)
- The app should be run on a server **you control** (your computer, a VPS, or Docker) — credentials are sent to Albertsons' login service from that server, not stored permanently

## App-only account? (phone verification, no password)

If you created your ACME account in the mobile app using **text message verification** and never set a password, this clipper cannot sign you in yet — it uses password login, not SMS codes.

**Fix (one time, ~2 minutes):**

1. Go to [acmemarkets.com Forgot Password](https://www.acmemarkets.com/account/forgot-password.html)
2. Enter the **phone number** tied to your ACME for U account
3. Complete the verification text and **create a password**
4. Return to this app and sign in with that **phone number + password**

ACME's own FAQ recommends the Forgot Password flow when you have an account but don't know your password.

**Why not SMS login in this app?** The ACME app uses a private phone-verification flow that isn't available to third-party tools. Password login is the supported workaround.

## Quick start (Docker)

```bash
docker compose up --build
```

Then open `http://localhost:8000` on your phone (same Wi‑Fi) or computer.

### iPhone: Add to Home Screen

1. Open the app URL in **Safari**
2. Tap the **Share** button
3. Choose **Add to Home Screen**
4. Launch it like a native app

## Quick start (without Docker)

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

Visit `http://<your-computer-ip>:8000` from your iPhone.

## Finding your Store ID

You no longer need to hunt for a store code on the website. On the sign-in screen:

1. Enter your **ZIP code**
2. Tap **Find Stores**
3. Tap your ACME location from the list

The app fills in the Store ID automatically.

**Other ways to find it:**
- In the **ACME app**: Account → My Store (store number may appear there)
- On **acmemarkets.com**: if you're signed in, open the Weekly Ad — the URL may contain `storeId=####`

To refresh the built-in store list later, run:

```bash
cd backend && python3 scripts/build_store_index.py
```

## How coupon matching works

The app compares keywords from your grocery list (e.g. "milk", "chicken", "cereal") against coupon titles, brands, and descriptions. Only unclipped coupons with a strong keyword overlap are suggested.

You can also use **Clip All Available** to load every coupon on your account (similar to other community coupon clippers).

## Project structure

```
backend/
  acme_client.py   # Albertsons/ACME API integration
  matcher.py       # Grocery list → coupon matching
  main.py          # FastAPI server
frontend/
  index.html       # Mobile UI
  app.js           # App logic
  styles.css       # iPhone-friendly styling
  manifest.json    # PWA manifest
  sw.js            # Offline shell caching
```

## Security notes

- Sessions expire after 8 hours
- Passwords are used only for the initial Okta login and are not saved to disk
- For best security, self-host on your home network or a private server
- This is an unofficial tool and is not affiliated with ACME Markets or Albertsons

## Limitations

- ACME may change their internal APIs at any time
- Grocery list sync depends on what the ACME backend exposes for your account; you can always add items manually
- Accounts created app-only with SMS verification require setting a password via Forgot Password before this app can sign in
- Multi-factor authentication on your ACME account may block password-based login

## Development

Run matcher tests:

```bash
cd backend
python -m pytest tests/ -q
```

## License

MIT
