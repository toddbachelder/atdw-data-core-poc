"""
Fetch DAPI records and upsert into DB.
productType filter is silently ignored by the API, so we paginate the full
result set and collect until we have enough of each target category.

Run: python src/ingest.py
"""
import os
import sys
import time
import requests
from collections import defaultdict
from xml.etree import ElementTree as ET
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(__file__))
from db import get_conn, init_schema, upsert_listing
from translate import record_to_canonical

load_dotenv()

DAPI_URL = "https://atlas.atdw-online.com.au/api/atlas/products"
DAPI_KEY = os.environ["DAPI_KEY"]

TARGET_CATEGORIES = {"TOUR", "ATTRACTION", "ACCOMM", "RESTAURANT", "EVENT"}
TARGET_PER_CATEGORY = 40  # aim for ~40 of each
PAGE_SIZE = 50
MAX_PAGES = 200  # safety cap — FOOD doesn't exist; RESTAURANT is the correct code


def fetch_page(page: int = 1, size: int = PAGE_SIZE) -> bytes:
    params = {"key": DAPI_KEY, "pge": page, "size": size}
    resp = requests.get(DAPI_URL, params=params, timeout=30)
    resp.raise_for_status()
    return resp.content


def run():
    conn = get_conn()
    init_schema(conn)

    counts = defaultdict(int)
    page = 1
    total_upserted = 0
    total_errors = 0

    print("Paginating DAPI — collecting until target met per category...")
    print(f"Target: {TARGET_PER_CATEGORY} each of {sorted(TARGET_CATEGORIES)}\n")

    while page <= MAX_PAGES:
        # Stop if all target categories are satisfied
        satisfied = {c for c in TARGET_CATEGORIES if counts[c] >= TARGET_PER_CATEGORY}
        if satisfied == TARGET_CATEGORIES:
            break

        raw = fetch_page(page=page)
        root = ET.fromstring(raw)
        records = root.findall(".//product_record")

        if not records:
            print(f"No more records at page {page}.")
            break

        for rec_el in records:
            try:
                canonical = record_to_canonical(rec_el)
                cat = canonical.get("category") or "UNKNOWN"

                if cat in TARGET_CATEGORIES and counts[cat] >= TARGET_PER_CATEGORY:
                    continue  # already have enough of this type

                upsert_listing(conn, canonical)
                counts[cat] += 1
                total_upserted += 1
            except Exception as e:
                source_id = rec_el.findtext("product_id")
                print(f"  ERROR {source_id}: {e}")
                total_errors += 1

        conn.commit()

        progress = ", ".join(f"{c}={counts[c]}" for c in sorted(TARGET_CATEGORIES))
        print(f"Page {page:3d} | {progress}")

        page += 1
        time.sleep(0.3)

    conn.close()
    print(f"\nDone. {total_upserted} upserted, {total_errors} errors.")
    print("Final counts:")
    for cat in sorted(counts):
        print(f"  {cat:20} {counts[cat]}")


if __name__ == "__main__":
    run()
