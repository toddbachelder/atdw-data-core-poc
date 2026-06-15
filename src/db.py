import os
import json
import ssl
import urllib.parse

import pg8000
from dotenv import load_dotenv

load_dotenv()


def _parse_url(url: str) -> dict:
    p = urllib.parse.urlparse(url)
    return dict(
        host=p.hostname,
        database=p.path.lstrip("/"),
        user=p.username,
        password=p.password,
        port=p.port or 5432,
    )


def get_conn():
    params = _parse_url(os.environ["DATABASE_URL"])
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE
    return pg8000.connect(**params, ssl_context=ssl_ctx)


def rows_as_dicts(cursor):
    cols = [d[0] for d in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


def init_schema(conn):
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    with open(schema_path) as f:
        sql = f.read()
    cur = conn.cursor()
    cur.execute(sql)
    conn.commit()
    print("Schema initialised.")


def upsert_listing(conn, record: dict):
    sql = """
        INSERT INTO listings (
            source_id, source_number, category, status, name, description,
            image_url, latitude, longitude, address, organisation_id,
            organisation_name, expires_at, source_updated_at, next_occurrence
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb,
            %s, %s, %s, %s, %s
        )
        ON CONFLICT (source_id) DO UPDATE SET
            status            = EXCLUDED.status,
            name              = EXCLUDED.name,
            description       = EXCLUDED.description,
            image_url         = EXCLUDED.image_url,
            latitude          = EXCLUDED.latitude,
            longitude         = EXCLUDED.longitude,
            address           = EXCLUDED.address,
            source_updated_at = EXCLUDED.source_updated_at,
            next_occurrence   = EXCLUDED.next_occurrence,
            ingested_at       = NOW()
    """
    cur = conn.cursor()
    cur.execute(sql, (
        record["source_id"],
        record["source_number"],
        record["category"],
        record["status"],
        record["name"],
        record["description"],
        record["image_url"],
        record["latitude"],
        record["longitude"],
        json.dumps(record.get("address")),
        record["organisation_id"],
        record["organisation_name"],
        record["expires_at"],
        record["source_updated_at"],
        record["next_occurrence"],
    ))


if __name__ == "__main__":
    conn = get_conn()
    init_schema(conn)
    conn.close()
    print("Done.")
