"""
Full national ingest from DAPI.

API constraints:
  - 10 requests per minute (RPM)
  - 3 records (profiles) per request

At 58,151 records / 3 per page = ~19,384 pages.
At 10 RPM (6.5 s sleep for buffer) this takes approximately 32-35 hours.

Resumable: saves the last completed page to .ingest_checkpoint so a restart
continues from where it left off rather than re-fetching from page 1.

Run: python src/ingest_full.py
"""
import os
import sys
import time
import json
import datetime
from collections import defaultdict
from xml.etree import ElementTree as ET

import requests
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(__file__))
from db import get_conn, init_schema, upsert_listing
from translate import record_to_canonical

load_dotenv()

DAPI_URL   = "https://atlas.atdw-online.com.au/api/atlas/products"
DAPI_KEY   = os.environ["DAPI_KEY"]
PAGE_SIZE  = 3      # API limit: 3 profiles per request
SLEEP_SECS = 6.5   # 10 RPM → 6 s minimum; 0.5 s buffer
MAX_PAGES  = 25000  # 58,151 / 3 = ~19,384 needed; cap at 25,000 for safety

CHECKPOINT_FILE = os.path.join(os.path.dirname(__file__), ".ingest_checkpoint")
PID_FILE        = os.path.join(os.path.dirname(__file__), ".ingest_pid")


def write_pid():
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))


def clear_pid():
    if os.path.exists(PID_FILE):
        os.remove(PID_FILE)


def is_already_running() -> bool:
    if not os.path.exists(PID_FILE):
        return False
    try:
        pid = int(open(PID_FILE).read().strip())
        # Check if process is still alive (send signal 0)
        os.kill(pid, 0)
        return True
    except (OSError, ValueError):
        return False


def load_checkpoint() -> int:
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE) as f:
            return int(f.read().strip())
    return 1


def save_checkpoint(page: int):
    with open(CHECKPOINT_FILE, "w") as f:
        f.write(str(page))


def fetch_page(page: int) -> bytes:
    params = {"key": DAPI_KEY, "pge": page, "size": PAGE_SIZE}
    resp = requests.get(DAPI_URL, params=params, timeout=30)
    resp.raise_for_status()
    return resp.content


def fmt_eta(elapsed_s: float, pages_done: int, pages_total: int) -> str:
    if pages_done == 0:
        return "—"
    rate = elapsed_s / pages_done        # seconds per page
    remaining = (pages_total - pages_done) * rate
    eta = datetime.datetime.now() + datetime.timedelta(seconds=remaining)
    h, m = divmod(int(remaining), 3600)[0], divmod(int(remaining), 60)[0] % 60
    return f"{h}h {m:02d}m remaining  (ETA {eta.strftime('%a %H:%M')})"


def get_conn_with_retry(max_attempts: int = 5) -> object:
    from db import get_conn as _get_conn
    for attempt in range(max_attempts):
        try:
            return _get_conn()
        except Exception as e:
            wait = 10 * (attempt + 1)
            print(f"  DB connect error (attempt {attempt+1}/{max_attempts}): {e} — retrying in {wait}s")
            time.sleep(wait)
    raise RuntimeError("Could not connect to database after multiple attempts")


def run():
    if is_already_running():
        print("Another ingest instance is already running (PID file exists). Exiting.")
        sys.exit(0)

    write_pid()

    start_page = load_checkpoint()
    if start_page > 1:
        print(f"Resuming from page {start_page} (checkpoint found).")
    else:
        print("Starting full national ingest from page 1.")

    print(f"Page size: {PAGE_SIZE} records  |  Sleep: {SLEEP_SECS}s  |  Est. pages: ~19,384\n")

    conn = get_conn_with_retry()
    init_schema(conn)

    counts      = defaultdict(int)
    total_seen  = 0
    total_upserted = 0
    total_errors   = 0
    start_time  = time.time()
    page        = start_page

    while page <= MAX_PAGES:
        try:
            raw = fetch_page(page)
        except requests.HTTPError as e:
            print(f"  HTTP error page {page}: {e} — retrying in 30 s")
            time.sleep(30)
            continue
        except Exception as e:
            print(f"  Network error page {page}: {e} — retrying in 30 s")
            time.sleep(30)
            continue

        try:
            root = ET.fromstring(raw)
        except ET.ParseError as e:
            print(f"  XML parse error page {page}: {e} — skipping")
            page += 1
            save_checkpoint(page)
            time.sleep(SLEEP_SECS)
            continue

        records = root.findall(".//product_record")
        if not records:
            print(f"\nNo records returned at page {page} — end of dataset.")
            break

        # Write with reconnect-on-failure (upserts are idempotent — safe to retry)
        for db_attempt in range(5):
            try:
                page_upserted = 0
                page_errors   = 0
                for rec_el in records:
                    try:
                        canonical = record_to_canonical(rec_el)
                        cat = canonical.get("category") or "UNKNOWN"
                        upsert_listing(conn, canonical)
                        counts[cat] += 1
                        page_upserted += 1
                    except Exception as e:
                        source_id = rec_el.findtext("product_id") or "?"
                        print(f"  ERROR {source_id}: {e}")
                        page_errors += 1
                conn.commit()
                total_seen     += len(records)
                total_upserted += page_upserted
                total_errors   += page_errors
                break
            except Exception as e:
                print(f"  DB error on page {page} (attempt {db_attempt+1}/5): {e} — reconnecting")
                try:
                    conn.close()
                except Exception:
                    pass
                time.sleep(5)
                conn = get_conn_with_retry()

        save_checkpoint(page + 1)

        elapsed = time.time() - start_time
        pages_done = page - start_page + 1
        eta_str = fmt_eta(elapsed, pages_done, 19384 - (start_page - 1))
        top_cats = sorted(counts.items(), key=lambda x: -x[1])[:5]
        cat_str  = "  ".join(f"{c}={n}" for c, n in top_cats)
        print(f"Page {page:5d} | upserted {total_upserted:6,d} | {cat_str} | {eta_str}")

        page += 1
        time.sleep(SLEEP_SECS)

    try:
        conn.close()
    except Exception:
        pass

    # Clear checkpoint and PID on clean finish
    if os.path.exists(CHECKPOINT_FILE):
        os.remove(CHECKPOINT_FILE)
    clear_pid()

    elapsed_total = time.time() - start_time
    h, m = divmod(int(elapsed_total), 3600)[0], divmod(int(elapsed_total), 60)[0] % 60
    print(f"\nDone in {h}h {m:02d}m.")
    print(f"Total seen: {total_seen:,}  |  Upserted: {total_upserted:,}  |  Errors: {total_errors}")
    print("\nFinal category counts:")
    for cat, n in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"  {cat:<20} {n:,}")


if __name__ == "__main__":
    run()
