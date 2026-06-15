CREATE TABLE IF NOT EXISTS listings (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id         TEXT UNIQUE NOT NULL,
    source_number     TEXT,
    category          TEXT,
    status            TEXT,
    name              TEXT,
    description       TEXT,
    image_url         TEXT,
    latitude          FLOAT,
    longitude         FLOAT,
    address           JSONB,
    organisation_id   TEXT,
    organisation_name TEXT,
    expires_at        DATE,
    source_updated_at TIMESTAMPTZ,
    next_occurrence   TEXT,
    ingested_at       TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS listings_category_idx ON listings (category);
CREATE INDEX IF NOT EXISTS listings_status_idx   ON listings (status);
