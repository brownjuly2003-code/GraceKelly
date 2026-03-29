# Batch 02 Report

## B1-rate-limit-strict
Status: success

Added `require_auth` to `Settings`, wired `GRACEKELLY_REQUIRE_AUTH`, and updated API key middleware so protected endpoints return `503` when strict auth is enabled without an API key. Also marked `/healthz/live` and `/healthz/ready` as public so future probe endpoints are not blocked by strict auth.

## B2-k8s-probes
Status: success

Added `/healthz/live` and `/healthz/ready` to `src/gracekelly/api/routes/health.py` and covered them with tests, including the strict-auth liveness case.

## B3-config-validation
Status: success

Added `Settings.validate()` and called it at the start of `create_app()`. While verifying the batch, existing timeout tests showed that the repo already supports positive sub-second `orchestrate_timeout_seconds` values, so validation was narrowed to reject only non-positive values. This preserves the existing timeout contract while still adding fail-fast startup validation.

Verification:
- `python -m pytest tests/test_rate_limit_strict.py tests/test_k8s_probes.py tests/test_config_startup_validation.py -v`
- `ruff check src/gracekelly/config.py src/gracekelly/middleware.py src/gracekelly/api/routes/health.py src/gracekelly/main.py`
- `mypy src/gracekelly/config.py src/gracekelly/middleware.py src/gracekelly/api/routes/health.py src/gracekelly/main.py`
- `python -m pytest --tb=no -q`

Full suite was run outside sandbox because unrelated tempfile-based tests require write access to the Windows temp directory.
