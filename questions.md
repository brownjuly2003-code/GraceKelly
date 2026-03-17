# Open Questions

Updated: 2026-03-17

1. Authenticated browser profile blocker
The thin Playwright backend, selector module, and manual live smoke harness are now in place. A real smoke run against the copied profile at `D:\GraceKelly\tmp\browser-recon\chrome-user-data` reaches prompt entry but is blocked at submit by a `Sign in or create an account` overlay, which now maps cleanly to `auth_failed` and skips the live smoke.

To continue the next plan item (`prompt -> response` proof on the live browser path), GraceKelly now needs a dedicated unlocked and authenticated Perplexity browser profile directory, not a copy of a live Chrome `Default` profile.
