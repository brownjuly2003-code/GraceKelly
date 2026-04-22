# Batch 80 DEBATE Report

Дата: 2026-04-22
Task: SMOKE-debate-live
Статус: blocked

## Причина блокировки

- `SMOKE-debate-live` зависит от успешного `SMOKE-smart-live`.
- `SMOKE-smart-live` остановился на реальном browser-profile blocker:
  `Browser profile directory 'D:/GraceKelly/chrome-profile' is already in use by another Chrome process.`
- По hard rules batch-а дополнительный live submit после этого не выполнялся.

## Итог

- DEBATE через реальный UI не запускался.
- Дополнительная квота Perplexity не тратилась.
