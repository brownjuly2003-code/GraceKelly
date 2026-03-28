FROM python:3.12-slim AS builder
WORKDIR /app

RUN pip install --upgrade pip wheel

COPY pyproject.toml ./
COPY src/ ./src/
RUN pip install --no-cache-dir --target /install .

FROM python:3.12-slim

RUN groupadd -r gracekelly && useradd -r -g gracekelly gracekelly

WORKDIR /app

COPY --from=builder /install /usr/local/lib/python3.12/dist-packages/
COPY --from=builder /app/src ./src/

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8011/health')"

USER gracekelly

EXPOSE 8011

CMD ["python", "-m", "uvicorn", "gracekelly.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8011"]
