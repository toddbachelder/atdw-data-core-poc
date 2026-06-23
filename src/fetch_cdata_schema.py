"""
Fetch ATDW PlatformDB schema from CData Connect Cloud.
Outputs static/cdata_schema.json — served directly so the browser never hits CData live.
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(__file__))
from cdata_conn import get_cdata_conn, cdata_rows_as_dicts

OUT = os.path.join(os.path.dirname(__file__), "..", "static", "cdata_schema.json")

conn = get_cdata_conn(timeout=60)
cur  = conn.cursor()

def q(sql):
    cur.execute(sql)
    return cur.fetchall()

# ── 1. All tables in the workspace ─────────────────────────────
print("Fetching tables...")
cur.execute("""
    SELECT TABLE_NAME, TABLE_TYPE
    FROM INFORMATION_SCHEMA.TABLES
    WHERE TABLE_CATALOG = 'ATDW_PlatformDB'
    ORDER BY TABLE_NAME
""")
tables = [(r[0], r[1]) for r in cur.fetchall()]
print(f"  {len(tables)} tables found")

# ── 2. All columns with description ────────────────────────────
print("Fetching columns...")
cur.execute("""
    SELECT TABLE_NAME, COLUMN_NAME, ORDINAL_POSITION,
           DATA_TYPE, CHARACTER_MAXIMUM_LENGTH,
           IS_NULLABLE, COLUMN_DEFAULT,
           COLUMN_COMMENT
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_CATALOG = 'ATDW_PlatformDB'
    ORDER BY TABLE_NAME, ORDINAL_POSITION
""")
raw_cols = cur.fetchall()
print(f"  {len(raw_cols)} columns found")

# ── 3. Fields captured via DAPI (actual CData column names) ────
# These are the CData PlatformDB columns that map to fields we
# ingest via the ATDW DAPI. Any column NOT in this set is not
# available through the public DAPI for this distributor key.
DAPI_FIELDS = {
    "listing": {
        "_id", "UID", "name", "description", "category",
        "status", "expiry",
        "physicalAddress.geoCodeLocation.latitude",
        "physicalAddress.geoCodeLocation.longitude",
        "physicalAddress.city_suburb", "physicalAddress.state",
        "physicalAddress.country", "physicalAddress.postcode",
        "physicalAddress.addrLine1", "physicalAddress.addrLine2",
        "physicalAddress.area", "physicalAddress.region",
    },
    "media": {"_id", "listingId", "url", "type", "altText"},
    "organisation": {"_id", "name"},
}

# ── 3b. Curated descriptions for key fields ────────────────────
# CData INFORMATION_SCHEMA.COLUMN_COMMENT is empty for all columns.
# These curated descriptions cover the highest-value non-DAPI fields.
CURATED = {
    # listing table
    "listing._id":                                        "MongoDB internal document ID",
    "listing.UID":                                        "Unique listing identifier (same as product_id in DAPI)",
    "listing.category":                                   "Product category code (ACCOMM, TOUR, RESTAURANT, etc.) — exposed via DAPI",
    "listing.name":                                       "Listing name — exposed via DAPI",
    "listing.description":                                "Listing description — exposed via DAPI",
    "listing.status":                                     "Listing status (ACTIVE/INACTIVE) — exposed via DAPI",
    "listing.expiry":                                     "Expiry date — exposed via DAPI",
    "listing.listingType":                                "Internal listing type classification within a category",
    "listing.productNumber":                              "ATDW internal product number (not exposed via DAPI)",
    "listing.uploadedThroughBulk":                        "Whether the record was created via bulk import rather than the operator portal",
    "listing.ABN":                                        "Australian Business Number — business registration identifier (not in DAPI)",
    "listing.profitStatus":                               "Business profit/not-for-profit classification",
    "listing.facilities":                                 "Array of facility codes (e.g. parking, accessible, wifi) not structured in DAPI",
    "listing.adminActivities":                            "Internal admin activity log — change history for the record",
    "listing.externalSystemCodes":                        "Codes linking the record to external booking or property management systems",
    "listing.socialExternalReferences.tripAdvisorURL":    "TripAdvisor listing URL — not exposed via DAPI",
    "listing.socialExternalReferences.facebookURL":       "Facebook page URL — not exposed via DAPI",
    "listing.socialExternalReferences.twitterURL":        "Twitter/X profile URL — not exposed via DAPI",
    "listing.socialExternalReferences.instagramURL":      "Instagram profile URL — not exposed via DAPI",
    "listing.socialExternalReferences.websiteURL":        "Operator website URL — not exposed via DAPI",
    "listing.socialExternalReferences.youtubeURL":        "YouTube channel URL — not exposed via DAPI",
    "listing.physicalAddress.city_suburb":                "City or suburb of the physical location — exposed via DAPI",
    "listing.physicalAddress.state":                      "State/territory code — exposed via DAPI",
    "listing.physicalAddress.country":                    "Country code — exposed via DAPI",
    "listing.physicalAddress.postcode":                   "Postcode of the physical address — exposed via DAPI",
    "listing.physicalAddress.addrLine1":                  "Street address line 1 — exposed via DAPI",
    "listing.physicalAddress.addrLine2":                  "Street address line 2 — exposed via DAPI",
    "listing.physicalAddress.area":                       "Tourism region or area name — exposed via DAPI",
    "listing.physicalAddress.region":                     "Broader region classification — exposed via DAPI",
    "listing.physicalAddress.geoCodeLocation.latitude":   "Latitude coordinate — exposed via DAPI",
    "listing.physicalAddress.geoCodeLocation.longitude":  "Longitude coordinate — exposed via DAPI",
    "listing.physicalAddress.type":                       "Address type classification",
    "listing.physicalAddress.isNewListing":               "Flag indicating the listing was recently created",
    "listing.postalAddress.addrLine1":                    "Postal address line 1 — separate from physical address, not in DAPI",
    "listing.postalAddress.city_suburb":                  "City/suburb of the postal address",
    "listing.postalAddress.state":                        "State of the postal address",
    "listing.postalAddress.postcode":                     "Postcode of the postal address",
    "listing.postalAddress.country":                      "Country of the postal address",
    # organisation table
    "organisation._id":                                   "MongoDB internal ID for the organisation record",
    "organisation.name":                                  "Organisation (custodian) name — exposed via DAPI",
    "organisation.ABN":                                   "Organisation ABN — not exposed via DAPI",
    "organisation.phone":                                 "Organisation phone number — not exposed via DAPI",
    "organisation.email":                                 "Organisation contact email — not exposed via DAPI",
    "organisation.website":                               "Organisation website — not exposed via DAPI",
    "organisation.state":                                 "State the organisation is registered in",
    # media table
    "media._id":                                          "MongoDB internal ID for the media record",
    "media.listingId":                                    "Foreign key linking to the listing — exposed via DAPI",
    "media.url":                                          "Image URL (contains distributor payload in &q= parameter)",
    "media.type":                                         "Media type (image, video, etc.)",
    "media.altText":                                      "Image alt text for accessibility",
    "media.caption":                                      "Image caption or credit",
    "media.width":                                        "Image width in pixels",
    "media.height":                                       "Image height in pixels",
    # publishedListing table
    "publishedListing.listingId":                         "Foreign key to the source listing",
    "publishedListing.distributorId":                     "Which distributor this published copy is scoped to",
    "publishedListing.publishedAt":                       "Timestamp when the record was published to this distributor",
    "publishedListing.status":                            "Publication status for this distributor",
    # service table (additional structured data per listing)
    "service.listingId":                                  "Foreign key to the parent listing",
    "service.type":                                       "Service type code (e.g. accommodation sub-type, tour style)",
    "service.pricing":                                    "Pricing information — structured but not in DAPI",
    "service.capacity":                                   "Capacity / number of guests — not in DAPI",
    "service.bookingURL":                                 "Direct booking URL — not exposed via DAPI",
    "service.phone":                                      "Contact phone for this service — not in DAPI",
    "service.email":                                      "Contact email for this service — not in DAPI",
}

# ── 4. Build schema tree grouped by table ──────────────────────
from collections import defaultdict
col_map = defaultdict(list)
for r in raw_cols:
    tname, cname, ordinal, dtype, maxlen, nullable, default, comment = r
    curated_key = f"{tname}.{cname}"
    desc = CURATED.get(curated_key, "") or comment or ""
    col_map[tname].append({
        "name":     cname,
        "type":     dtype + (f"({maxlen})" if maxlen else ""),
        "nullable": nullable == "YES",
        "default":  default,
        "desc":     desc,
        "in_dapi":  cname in DAPI_FIELDS.get(tname, set()),
    })

schema = []
for tname, ttype in tables:
    cols = col_map.get(tname, [])
    dapi_count = sum(1 for c in cols if c["in_dapi"])
    schema.append({
        "table":      tname,
        "type":       ttype,
        "col_count":  len(cols),
        "dapi_count": dapi_count,
        "columns":    cols,
    })

# ── 5. Summary stats ───────────────────────────────────────────
total_cols  = sum(t["col_count"] for t in schema)
dapi_cols   = sum(t["dapi_count"] for t in schema)
print(f"\nSummary:")
print(f"  Tables:        {len(schema)}")
print(f"  Total columns: {total_cols}")
print(f"  In DAPI:       {dapi_cols}")
print(f"  Not in DAPI:   {total_cols - dapi_cols}")

for t in sorted(schema, key=lambda x: -x["col_count"]):
    flag = " <-- has DAPI fields" if t["dapi_count"] else ""
    print(f"  {t['table']:<45} {t['col_count']:>4} cols  {t['dapi_count']:>3} in DAPI{flag}")

# ── 6. Write output ────────────────────────────────────────────
out = {
    "total_tables": len(schema),
    "total_columns": total_cols,
    "dapi_columns": dapi_cols,
    "tables": schema,
}
os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(out, f, indent=2, ensure_ascii=False)

print(f"\nWritten: {OUT}")
conn.close()
