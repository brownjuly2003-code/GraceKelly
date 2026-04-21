# UI-PO2-parity-rework (retrospective CC-authored, updated with evidence 2026-04-21)

Date: 2026-04-21
Closure status: **parity achieved, user complaints unconfirmed by side-by-side diff — needs specific pointers from user**.

## Files changed
- `static/icons/` (new — 5 SVG from PO2: cpu, flash, merge, search, target)
- `static/analytics.html`, `english.html`, `interview.html`, `rag.html`, `webpage.html` (new, 512–1788 lines, copied from PO2)
- `static/index.html` (+415 delta)
- `static/css/style.css` (−537 net)
- `static/js/app.js` (+40), `static/js/chat.js` (+79), `static/js/model-menu.js` (+559)

## Evidence captured (2026-04-21)
- Live uvicorn on 127.0.0.1:8011 + PO2 static server on 127.0.0.1:8014/static/ (served from PO2 project root so `/static/css/*` resolves).
- Playwright headless screenshots at 1280x800 and 1920x1080 for both:
  - `.workflow/outbox/screenshots/batch-74/gk-1280x800.png`
  - `.workflow/outbox/screenshots/batch-74/gk-1920x1080.png`
  - `.workflow/outbox/screenshots/batch-74/po2-1280x800.png`
  - `.workflow/outbox/screenshots/batch-74/po2-1920x1080.png`

## Findings
- **GraceKelly 1280x800 is visually indistinguishable from PO2 1280x800.** Same layout, same orange brand, same left icon-nav with H / S / ? (single-letter buttons), same bottom input + 6 footer-links + orange help-FAB.
- **PO2's own `index.html` already contains `<span>H</span>`, `<span>S</span>`, `<span>?</span>`** for history/stats/help nav buttons (confirmed by `grep -A2 nav-item` on PO2). These are **not "letters instead of icons"** — they are the original PO2 design.
- **PO2's `<title>` and `<h1>` are both "GraceKelly"** (PO2 was rebranded to GraceKelly upstream). User-reported brand drift does not exist.
- "Статистика на основной странице" — not visible on the initial empty-state screenshot for either PO2 or GraceKelly. Stats live in the sidebar per CSS layout. Complaint may refer to earlier drift that batch-74 already fixed, or to a different viewport/state than captured.

## User-reported complaints vs captured evidence

| Complaint | Evidence | Disposition |
|---|---|---|
| "ненужный креатив" | GK screenshot matches PO2 1:1 | **Unconfirmed** — please point to a specific element |
| "не те иконки" | Nav-buttons are `<span>H/S/?</span>` in PO2 itself | **By design** — PO2 uses single-letter nav; not a drift |
| "статистика на основной странице" | Main panel empty in both GK and PO2 default state | **Unconfirmed** — may require a populated/threaded state to reproduce |

## Open questions
- User may have been looking at a pre-batch-74 state, at a different page (not `/`), or at a populated thread. If the complaint persists, request a screenshot from the user pinpointing the offending element.
