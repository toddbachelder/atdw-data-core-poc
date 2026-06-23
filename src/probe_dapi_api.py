"""
Probe the raw DAPI surface itself (not the translated/ingested listings table) —
for the DAPI component of the platform re-architecture assessment.

Hits /products (list, already used by ingest.py), then /product (single detailed
record) and /productservice (service-level detail) for one real product ID, and
dumps the raw XML so we can see exactly what DAPI exposes beyond what ingest.py
currently parses out.

Run: python src/probe_dapi_api.py [CATEGORY]
"""
import os
import sys
from xml.etree import ElementTree as ET
import requests
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(__file__))
load_dotenv()

BASE = "https://atlas.atdw-online.com.au/api/atlas"
KEY = os.environ["DAPI_KEY"]

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "docs", "dapi_raw")
os.makedirs(OUT_DIR, exist_ok=True)


def fetch(endpoint: str, **params) -> bytes:
    params["key"] = KEY
    resp = requests.get(f"{BASE}/{endpoint}", params=params, timeout=30)
    resp.raise_for_status()
    return resp.content


def pretty_save(name: str, raw: bytes):
    path = os.path.join(OUT_DIR, name)
    try:
        root = ET.fromstring(raw)
        ET.indent(root, space="  ")
        ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)
    except ET.ParseError:
        with open(path, "wb") as f:
            f.write(raw)
    print(f"  wrote {path} ({len(raw):,} bytes)")


def main():
    category = sys.argv[1] if len(sys.argv) > 1 else None

    print("1. /products (list) — one page, to grab a real product_id")
    list_params = {"pge": 1, "size": 5}
    if category:
        list_params["productType"] = category
    raw = fetch("products", **list_params)
    pretty_save("products_sample.xml", raw)

    root = ET.fromstring(raw)
    records = root.findall(".//product_record")
    if not records:
        print("No records returned — check DAPI_KEY / connectivity.")
        return
    product_id = records[0].findtext("product_id")
    cat = records[0].findtext("product_category_id") or records[0].findtext("category")
    print(f"  -> sample product_id={product_id} category={cat}")
    print(f"  -> top-level child tags in a /products record: {sorted({c.tag for c in records[0]})}")

    print("\n2. /product (single detailed record) for that product_id")
    raw = fetch("product", productId=product_id)
    pretty_save("product_detail_sample.xml", raw)
    detail_root = ET.fromstring(raw)
    detail_rec = detail_root.find(".//product_record")
    if detail_rec is None:
        detail_rec = detail_root
    print(f"  -> top-level child tags in a /product record: {sorted({c.tag for c in detail_rec})}")
    print(f"  -> ALL tags anywhere in a /product record (incl. nested services): {len(sorted({c.tag for c in detail_root.iter()}))}")

    service_id = detail_root.findtext(".//service_id")
    if service_id:
        print(f"\n3. /productservice for product_id={product_id}, service_id={service_id}")
        print("   (requires BOTH ids — DAPI returns 'Product Id and Service Id are mandatory' otherwise)")
        try:
            raw = fetch("productservice", productId=product_id, serviceId=service_id)
            pretty_save("productservice_sample.xml", raw)
            svc_root = ET.fromstring(raw)
            print(f"  -> ALL tags anywhere in a /productservice record: {len(sorted({c.tag for c in svc_root.iter()}))}")
        except requests.HTTPError as e:
            print(f"  /productservice failed: {e}")
    else:
        print("\n3. /productservice skipped — sample product has no embedded service_id to test with")

    print(f"\nDone. Raw samples in {os.path.abspath(OUT_DIR)}")


if __name__ == "__main__":
    main()
