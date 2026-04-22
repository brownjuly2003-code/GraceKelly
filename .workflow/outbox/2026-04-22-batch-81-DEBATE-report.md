# Batch 81 DEBATE Report

Дата: 2026-04-22
Task: SMOKE-debate-live
Статус: blocked

## Причина блокировки

- SMOKE-debate-live зависит от успешного SMOKE-smart-live.
- Первый live SMART submit уже потратил SMART quota и завершился failure на browser selector / response-extraction blocker.
- По hard rules batch-а после этого DEBATE не запускался, чтобы не тратить оставшийся submit на заведомо некорректную ветку.

## Итог

- DEBATE через реальный UI не выполнялся.
- Дополнительная Perplexity quota на DEBATE в этом batch не тратилась.
