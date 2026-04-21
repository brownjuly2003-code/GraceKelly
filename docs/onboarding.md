# Onboarding

## Prerequisites

- Run `uv sync --extra dev --extra browser` in `D:/GraceKelly`.
- Install Google Chrome or Chromium.
- Keep your normal Chrome profile closed while bootstrapping the GraceKelly profile.

## First-time setup

1. Copy `.env.example` to `.env`.
2. Run `python scripts/bootstrap_chrome_profile.py --dry-run` to confirm the browser binary and target profile path.
3. Run `python scripts/bootstrap_chrome_profile.py`.
4. In the opened browser window, sign in to Perplexity Pro.
5. Return to the terminal and press Enter so the script can terminate the launched Chrome tree and clear lock files.
6. Set `GRACEKELLY_BROWSER_PROFILE_DIR` in `.env` to the printed path, for example `D:/GraceKelly/chrome-profile`.

## Daily use

1. Do not open `GRACEKELLY_BROWSER_PROFILE_DIR` with your regular Chrome session.
2. Start the app with `python -m uvicorn gracekelly.main:create_app --factory --port 8011`.
3. If startup fails, fix the profile issue first instead of retrying requests.

## Troubleshooting

### HTTP 503 `model_auth_required`

- The dedicated profile is missing a valid Perplexity login.
- Re-run `python scripts/bootstrap_chrome_profile.py` and sign in again.
- Confirm the app uses the dedicated profile path from `.env`, not `.../User Data/Default`.

### `BrowserProfileBusyError` or startup failure about a live Chrome profile

- Another Chrome process is still using `GRACEKELLY_BROWSER_PROFILE_DIR`.
- Close the launched browser tree completely, then restart uvicorn.
- If the path points to `AppData/Local/Google/Chrome/User Data/Default` or another everyday profile, replace it with a dedicated directory created by `python scripts/bootstrap_chrome_profile.py`.
