# Batch 81 SMART Report

Дата: 2026-04-22
Task: SMOKE-smart-live
Статус: failure

## Что подтверждено

- Pre-check перед запуском был чистый: процессов chrome.exe с CommandLine, содержащим chrome-profile, не найдено; lock-файлы в D:/GraceKelly/chrome-profile отсутствовали.
- uvicorn поднят на http://127.0.0.1:8011/ с GRACEKELLY_BROWSER_ENABLED=true, GRACEKELLY_BROWSER_AUTOMATION_BACKEND=playwright, GRACEKELLY_BROWSER_PROFILE_DIR=D:/GraceKelly/chrome-profile, GRACEKELLY_EXECUTION_PROFILE=hybrid.
- GET /api/v1/models подтвердил, что browser catalog жив и best доступен.
- Перед submit UI selection был зафиксирован как:
  - id = smart
  - pattern = smart
  - model = best
- Живой POST /api/v1/smart действительно ушёл в browser.perplexity path и вернул 200.
- auth-banner на SPA не показывался.

## Failure Mode

- Browser adapter не смог стабильно выбрать Best в реальном меню Perplexity:
  - первая попытка завершилась model_mismatch: requested Best, but UI shows Sonar;
  - вторая попытка прошла без verified model selection и вытащила body_after_prompt shell text;
  - третья попытка снова завершилась model_mismatch: requested Best, but UI shows Sonar.
- Response body:
  - answer = "Thinking / Ask a follow-up / Model"
  - pattern_used = single
  - used_roles = true
  - total_llm_calls = 3
  - model_id = best
- Это уже не environment/profile-lock blocker из batch-80, а live selector/response-extraction blocker в browser path.

## Вывод

- Perplexity quota spent = 1 SMART submit.
- По hard rules batch-а после этого live failure DEBATE и DOCS-phase-17-refresh не выполнялись.
- Для follow-up batch нужен backend fix в browser model selection / response extraction, затем новый SMART rerun и только после него DEBATE + roadmap refresh.
