CREATE TABLE IF NOT EXISTS gk_model_catalog_snapshots (
    catalog_key   TEXT PRIMARY KEY,
    checked_at    TIMESTAMPTZ NOT NULL,
    source        TEXT NOT NULL,
    payload       JSONB NOT NULL,
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
