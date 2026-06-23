"""
Full-dataset analytical probe — runs against the complete 58,388-record national dataset.
Outputs structured findings for docs/findings.md and the website.
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from db import get_conn

conn = get_conn()
cur  = conn.cursor()

def q(sql, *args):
    cur.execute(sql, args)
    return cur.fetchall()

def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)

# ── 1. TOTALS ─────────────────────────────────────────────────
section("1. TOTALS & CATEGORY BREAKDOWN")
rows = q("""
    SELECT category,
           COUNT(*) AS total,
           SUM(CASE WHEN latitude IS NOT NULL THEN 1 ELSE 0 END) AS has_geo,
           SUM(CASE WHEN image_url IS NOT NULL THEN 1 ELSE 0 END) AS has_img,
           ROUND(AVG(LENGTH(description))) AS avg_desc,
           MIN(LENGTH(description)) AS min_desc,
           MAX(LENGTH(description)) AS max_desc,
           SUM(CASE WHEN LENGTH(description) < 50 THEN 1 ELSE 0 END) AS short_desc
    FROM listings GROUP BY category ORDER BY total DESC
""")
for r in rows:
    print(f"  {r[0]:<12} total={r[1]:>6,}  geo={r[2]:>6,} ({100*r[2]//r[1]:>3}%)  img={r[3]:>6,}  desc_avg={r[4]}  desc_min={r[5]}  short(<50)={r[7]}")

# ── 2. RECORDS WITH NO DESCRIPTION ───────────────────────────
section("2. EMPTY / VERY SHORT DESCRIPTIONS")
rows = q("""
    SELECT category, COUNT(*) FROM listings
    WHERE description IS NULL OR LENGTH(description) < 20
    GROUP BY category ORDER BY COUNT(*) DESC
""")
for r in rows: print(f"  {r[0]}: {r[1]}")

# ── 3. NAME ANOMALIES ─────────────────────────────────────────
section("3. NAME ANOMALIES")
rows = q("SELECT COUNT(*) FROM listings WHERE name ~ '^[A-Z0-9 ]{4,}$'")
print(f"  ALL-CAPS names: {rows[0][0]:,}")

rows = q("SELECT COUNT(*) FROM listings WHERE name ~ '[^\\x20-\\x7E]'")
print(f"  Non-ASCII names: {rows[0][0]:,}")

rows = q("SELECT COUNT(*) FROM listings WHERE LENGTH(name) < 5")
print(f"  Very short names (< 5 chars): {rows[0][0]:,}")

rows = q("SELECT COUNT(*) FROM listings WHERE name ~ '^[^a-zA-Z0-9]'")
print(f"  Names starting with non-alphanumeric: {rows[0][0]:,}")

rows = q("""
    SELECT name, category FROM listings
    WHERE name ~ '^[^a-zA-Z0-9]' LIMIT 10
""")
for r in rows: print(f"    '{r[0]}' [{r[1]}]")

# ── 4. GEO OUTLIERS (outside Australia bounding box) ─────────
section("4. GEO OUTLIERS — outside Australia")
rows = q("""
    SELECT COUNT(*), category FROM listings
    WHERE latitude IS NOT NULL
      AND (latitude < -44 OR latitude > -10
        OR longitude < 113 OR longitude > 154)
    GROUP BY category ORDER BY COUNT(*) DESC
""")
total_outliers = sum(r[0] for r in rows)
print(f"  Total geo outliers: {total_outliers:,}")
for r in rows: print(f"  {r[1]}: {r[0]:,}")

rows = q("""
    SELECT name, category, latitude, longitude,
           address->0->>'city' AS city,
           address->0->>'state' AS state
    FROM listings
    WHERE latitude IS NOT NULL
      AND (latitude < -44 OR latitude > -10
        OR longitude < 113 OR longitude > 154)
    ORDER BY category LIMIT 15
""")
for r in rows:
    print(f"    [{r[1]}] {r[0]!r:40s}  {r[2]}, {r[3]}  ({r[4]}, {r[5]})")

# ── 5. RECORDS WITH lat=0 or lng=0 ───────────────────────────
section("5. NULL-ISLAND / ZERO COORDINATES")
rows = q("""
    SELECT COUNT(*), category FROM listings
    WHERE latitude = 0 OR longitude = 0
    GROUP BY category ORDER BY COUNT(*) DESC
""")
for r in rows: print(f"  {r[1]}: {r[0]:,}")

# ── 6. ORGANISATION CONCENTRATION ────────────────────────────
section("6. ORGANISATION CONCENTRATION — top custodians by category")
for cat in ['ACCOMM','ATTRACTION','RESTAURANT','EVENT','TOUR','GENSERVICE','JOURNEY']:
    rows = q("""
        SELECT organisation_name, COUNT(*) AS n
        FROM listings WHERE category = %s
        GROUP BY organisation_name ORDER BY n DESC LIMIT 5
    """, cat)
    total_cat = q("SELECT COUNT(*) FROM listings WHERE category = %s", cat)[0][0]
    top5 = sum(r[1] for r in rows)
    print(f"\n  {cat} (total={total_cat:,})  top-5 concentration={100*top5//total_cat}%:")
    for r in rows:
        print(f"    {r[1]:>5,} ({100*r[1]//total_cat:>2}%)  {r[0]}")

# ── 7. CROSS-STATE CUSTODIANS ─────────────────────────────────
section("7. CROSS-STATE CUSTODIANS — orgs managing records in 3+ states")
rows = q("""
    SELECT organisation_name,
           COUNT(DISTINCT address->0->>'state') AS n_states,
           COUNT(*) AS n_records,
           STRING_AGG(DISTINCT address->0->>'state', ', ' ORDER BY address->0->>'state') AS states
    FROM listings
    WHERE organisation_name IS NOT NULL
    GROUP BY organisation_name
    HAVING COUNT(DISTINCT address->0->>'state') >= 3
    ORDER BY n_records DESC LIMIT 20
""")
for r in rows:
    print(f"  {r[2]:>5,} records  {r[1]} states  {r[0]!r:45s}  [{r[3]}]")

# ── 8. MULTI-AREA RECORDS ────────────────────────────────────
section("8. MULTI-AREA RECORDS")
rows = q("""
    SELECT category,
           SUM(CASE WHEN jsonb_array_length(address->0->'areas') > 1 THEN 1 ELSE 0 END) AS multi,
           COUNT(*) AS total
    FROM listings
    WHERE address IS NOT NULL AND jsonb_array_length(address) > 0
    GROUP BY category ORDER BY multi DESC
""")
for r in rows:
    pct = 100*r[1]//r[2] if r[2] else 0
    print(f"  {r[0]:<12} multi-area={r[1]:>5,}/{r[2]:>6,} ({pct}%)")

rows = q("""
    SELECT MAX(jsonb_array_length(address->0->'areas')) FROM listings
""")
print(f"\n  Max areas on a single record: {rows[0][0]}")

rows = q("""
    SELECT name, category, jsonb_array_length(address->0->'areas') AS n_areas,
           address->0->'areas' AS areas
    FROM listings
    WHERE jsonb_array_length(address->0->'areas') >= 5
    ORDER BY n_areas DESC LIMIT 5
""")
for r in rows:
    print(f"  [{r[1]}] {r[0]!r:45s}  {r[2]} areas: {r[3]}")

# ── 9. EXPIRY ANALYSIS ───────────────────────────────────────
section("9. EXPIRY ANALYSIS")
rows = q("""
    SELECT TO_CHAR(DATE_TRUNC('month', expires_at::date), 'YYYY-MM') AS month,
           COUNT(*) AS n
    FROM listings
    WHERE expires_at IS NOT NULL
    GROUP BY month ORDER BY month
    LIMIT 36
""")
for r in rows:
    bar = '#' * (r[1] // 200)
    print(f"  {r[0]}  {r[1]:>5,}  {bar}")

rows = q("""
    SELECT COUNT(*) FROM listings
    WHERE expires_at IS NOT NULL AND expires_at::date < CURRENT_DATE
""")
print(f"\n  Already past expiry (stale): {rows[0][0]:,}")

# ── 10. JOURNEY SUB-TYPE DETECTION ───────────────────────────
section("10. JOURNEY — trail vs itinerary detection")
rows = q("""
    SELECT
      SUM(CASE WHEN description ~* 'distance:|difficulty:|grade:' THEN 1 ELSE 0 END) AS trails,
      SUM(CASE WHEN description ~* '\\d+[ -]?day' THEN 1 ELSE 0 END) AS itineraries,
      SUM(CASE WHEN description ~* 'distance:|difficulty:|grade:'
               AND description ~* '\\d+[ -]?day' THEN 1 ELSE 0 END) AS both,
      COUNT(*) AS total
    FROM listings WHERE category = 'JOURNEY'
""")
r = rows[0]
print(f"  Trails (Distance/Difficulty/Grade in desc): {r[0]:,} / {r[3]:,} ({100*r[0]//r[3]}%)")
print(f"  Itineraries (N-day in desc):                {r[1]:,} / {r[3]:,} ({100*r[1]//r[3]}%)")
print(f"  Both signals (ambiguous):                   {r[2]:,}")
print(f"  Neither (uncategorisable):                  {r[3]-r[0]-r[1]+r[2]:,}")

# ── 11. EVENT PATTERNS ───────────────────────────────────────
section("11. EVENT PATTERNS")
rows = q("""
    SELECT COUNT(*) FROM listings
    WHERE category = 'EVENT' AND next_occurrence IS NOT NULL
      AND next_occurrence::date < CURRENT_DATE
""")
print(f"  Past-dated next_occurrence: {rows[0][0]:,}")

rows = q("""
    SELECT
      SUM(CASE WHEN next_occurrence IS NOT NULL AND expires_at IS NOT NULL
               AND next_occurrence = expires_at THEN 1 ELSE 0 END) AS one_off,
      SUM(CASE WHEN next_occurrence IS NOT NULL AND expires_at IS NOT NULL
               AND next_occurrence <> expires_at THEN 1 ELSE 0 END) AS recurring,
      COUNT(*) AS total
    FROM listings WHERE category = 'EVENT'
""")
r = rows[0]
print(f"  One-off events (next_occurrence = expires_at): {r[0]:,} ({100*r[0]//r[2]}%)")
print(f"  Recurring events (next_occurrence ≠ expires_at): {r[1]:,} ({100*r[1]//r[2]}%)")

rows = q("""
    SELECT organisation_name, COUNT(*) AS n
    FROM listings WHERE category = 'EVENT'
    GROUP BY organisation_name ORDER BY n DESC LIMIT 10
""")
print("\n  Top EVENT custodians:")
for r in rows: print(f"    {r[1]:>4,}  {r[0]}")

# ── 12. ACCOMM PATTERNS ───────────────────────────────────────
section("12. ACCOMM — aggregator vs direct")
rows = q("""
    SELECT
      SUM(CASE WHEN organisation_name ~* 'hipcamp|airbnb|stayz|booking|expedia|vrbo' THEN 1 ELSE 0 END) AS aggregator,
      SUM(CASE WHEN organisation_name ~* 'council|shire|govt|government|department|dept' THEN 1 ELSE 0 END) AS govt,
      COUNT(*) AS total
    FROM listings WHERE category = 'ACCOMM'
""")
r = rows[0]
print(f"  Aggregator-owned (Hipcamp/Stayz/etc): {r[0]:,} ({100*r[0]//r[2]}%)")
print(f"  Govt/council-owned:                   {r[1]:,} ({100*r[1]//r[2]}%)")
print(f"  Other (likely direct):                {r[2]-r[0]-r[1]:,} ({100*(r[2]-r[0]-r[1])//r[2]}%)")

# ── 13. DESCRIPTION QUALITY DEEP-DIVE ────────────────────────
section("13. DESCRIPTION QUALITY")
rows = q("""
    SELECT category,
           PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY LENGTH(description)) AS p25,
           PERCENTILE_CONT(0.5)  WITHIN GROUP (ORDER BY LENGTH(description)) AS p50,
           PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY LENGTH(description)) AS p75
    FROM listings WHERE description IS NOT NULL
    GROUP BY category ORDER BY p50 DESC
""")
print(f"  {'Category':<12}  {'P25':>6}  {'P50':>6}  {'P75':>6}")
for r in rows:
    print(f"  {r[0]:<12}  {int(r[1]):>6,}  {int(r[2]):>6,}  {int(r[3]):>6,}")

# ── 14. STATE × CATEGORY GAPS ────────────────────────────────
section("14. STATE × CATEGORY GAPS")
rows = q("""
    SELECT address->0->>'state' AS state, category, COUNT(*) AS n
    FROM listings
    WHERE address IS NOT NULL AND jsonb_array_length(address) > 0
      AND address->0->>'state' IN ('NSW','VIC','QLD','SA','WA','TAS','NT','ACT')
      AND category IN ('ACCOMM','RESTAURANT','ATTRACTION','TOUR','EVENT')
    GROUP BY state, category ORDER BY state, category
""")
from collections import defaultdict
grid = defaultdict(dict)
for r in rows:
    grid[r[0]][r[1]] = r[2]
cats = ['ACCOMM','RESTAURANT','ATTRACTION','TOUR','EVENT']
print(f"  {'STATE':<6}  " + "  ".join(f"{c:>10}" for c in cats))
for state in sorted(grid):
    vals = "  ".join(f"{grid[state].get(c,0):>10,}" for c in cats)
    print(f"  {state:<6}  {vals}")

# ── 15. ORGANISATION NAME CASING ─────────────────────────────
section("15. ORGANISATION NAME CASING — mismatches with business name")
rows = q("""
    SELECT COUNT(*) FROM listings
    WHERE organisation_name IS NOT NULL
      AND organisation_name = LOWER(organisation_name)
      AND LENGTH(organisation_name) > 3
""")
print(f"  All-lowercase org names: {rows[0][0]:,}")

rows = q("""
    SELECT COUNT(*) FROM listings
    WHERE organisation_name IS NOT NULL
      AND organisation_name = UPPER(organisation_name)
      AND LENGTH(organisation_name) > 3
""")
print(f"  ALL-CAPS org names: {rows[0][0]:,}")

rows = q("""
    SELECT organisation_name, COUNT(*) AS n
    FROM listings
    WHERE organisation_name = LOWER(organisation_name)
      AND LENGTH(organisation_name) > 3
    GROUP BY organisation_name ORDER BY n DESC LIMIT 8
""")
print("  Top all-lowercase org names:")
for r in rows: print(f"    {r[1]:>4,}  {r[0]!r}")

# ── 16. DUPLICATE DETECTION ───────────────────────────────────
section("16. DUPLICATE / NEAR-DUPLICATE DETECTION")
rows = q("""
    SELECT name, COUNT(*) AS n,
           COUNT(DISTINCT address->0->>'state') AS n_states,
           STRING_AGG(DISTINCT address->0->>'state', ',') AS states
    FROM listings
    GROUP BY name
    HAVING COUNT(*) >= 5
    ORDER BY n DESC LIMIT 20
""")
print(f"  Names appearing 5+ times:")
for r in rows:
    print(f"  {r[1]:>4}x  {r[3]:<20}  {r[0]!r}")

rows = q("""
    SELECT COUNT(*) FROM (
        SELECT name FROM listings
        GROUP BY name HAVING COUNT(*) > 1
    ) sub
""")
print(f"\n  Distinct names with 2+ records: {rows[0][0]:,}")

rows = q("""
    SELECT SUM(cnt - 1) FROM (
        SELECT COUNT(*) AS cnt FROM listings GROUP BY name HAVING COUNT(*) > 1
    ) sub
""")
print(f"  Excess records (above first instance): {rows[0][0]:,}")

# ── 17. IMAGE URL INSTABILITY ─────────────────────────────────
section("17. IMAGE URL ANALYSIS")
rows = q("""
    SELECT COUNT(*) FROM listings WHERE image_url IS NOT NULL
      AND image_url LIKE '%?q=%'
""")
print(f"  Image URLs with distributor ?q= payload: {rows[0][0]:,}")

rows = q("""
    SELECT COUNT(DISTINCT SPLIT_PART(image_url, '?', 1)) AS unique_base_paths,
           COUNT(DISTINCT image_url) AS unique_full_urls,
           COUNT(*) AS total_with_img
    FROM listings WHERE image_url IS NOT NULL
""")
r = rows[0]
print(f"  Unique base paths (without ?q=): {r[0]:,}")
print(f"  Unique full URLs: {r[1]:,}")
print(f"  Total records with image: {r[2]:,}")

# ── 18. RECORDS WITH SAME ADDRESS ────────────────────────────
section("18. SHARED ADDRESS — records sharing exact street address")
rows = q("""
    SELECT address->0->>'streetAddress' AS addr, COUNT(*) AS n, COUNT(DISTINCT category) AS cats
    FROM listings
    WHERE address IS NOT NULL AND jsonb_array_length(address) > 0
      AND address->0->>'streetAddress' IS NOT NULL
      AND LENGTH(address->0->>'streetAddress') > 5
    GROUP BY addr HAVING COUNT(*) >= 10
    ORDER BY n DESC LIMIT 15
""")
for r in rows:
    print(f"  {r[1]:>4,} records ({r[2]} cats)  {r[0]!r}")

# ── 19. RECORDS WITH MISSING ORGANISATION ────────────────────
section("19. MISSING ORGANISATION NAME")
rows = q("""
    SELECT category,
           SUM(CASE WHEN organisation_name IS NULL OR organisation_name = '' THEN 1 ELSE 0 END) AS missing,
           COUNT(*) AS total
    FROM listings GROUP BY category ORDER BY missing DESC
""")
for r in rows:
    pct = 100*r[1]//r[2] if r[2] else 0
    print(f"  {r[0]:<12} missing={r[1]:>5,}/{r[2]:>6,} ({pct}%)")

# ── 20. ACCOMM: HIPCAMP QUALITY VS OTHERS ────────────────────
section("20. HIPCAMP vs NON-HIPCAMP ACCOMM quality comparison")
rows = q("""
    SELECT
      CASE WHEN organisation_name = 'Hipcamp Australia Pty Ltd.' THEN 'Hipcamp' ELSE 'Other' END AS grp,
      COUNT(*) AS n,
      ROUND(AVG(LENGTH(description))) AS avg_desc,
      SUM(CASE WHEN latitude IS NOT NULL THEN 1 ELSE 0 END) AS has_geo,
      SUM(CASE WHEN image_url IS NOT NULL THEN 1 ELSE 0 END) AS has_img
    FROM listings WHERE category = 'ACCOMM'
    GROUP BY grp
""")
for r in rows:
    print(f"  {r[0]:<10}  n={r[1]:>6,}  desc_avg={r[2]}  geo={r[3]:>6,} ({100*r[3]//r[1]}%)  img={r[4]:>6,} ({100*r[4]//r[1]}%)")

conn.close()
print("\n\n=== PROBE COMPLETE ===")
