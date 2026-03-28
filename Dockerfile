# python:3.12-slim — pinned to 3.12 for reproducibility; upgrade intentionally
FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
COPY src/ src/

RUN pip install --no-cache-dir -e .

# Non-root user for security hardening — must come after pip install
RUN addgroup --system gracekelly && adduser --system --ingroup gracekelly --no-create-home gracekelly
USER gracekelly

EXPOSE 8011

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8011/health')" || exit 1

CMD ["uvicorn", "gracekelly.main:app_factory", "--host", "0.0.0.0", "--port", "8011", "--factory"]
