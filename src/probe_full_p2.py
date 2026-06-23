"""Probe sections 11-20 — continuation after type-cast fix."""
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
               AND next_occurrence::date = expires_at::date THEN 1 ELSE 0 END) AS one_off,
      SUM(CASE WHEN next_occurrence IS NOT NULL AND expires_at IS NOT NULL
               AND next_occurrence::date <> expires_at::date THEN 1 ELSE 0 END) AS recurring,
      COUNT(*) AS total
    FROM listings WHERE category = 'EVENT'
""")
r = rows[0]
print(f"  One-off events (next_occurrence = expires_at): {r[0]:,} ({100*r[0]//r[2]}%)")
print(f"  Recurring events (next_occurrence != expires_at): {r[1]:,} ({100*r[1]//r[2]}%)")

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
      SUM(CASE WHEN organisation_name ILIKE '%hipcamp%' OR organisation_name ILIKE '%stayz%'
               OR organisation_name ILIKE '%airbnb%' OR organisation_name ILIKE '%booking%'
               OR organisation_name ILIKE '%expedia%' THEN 1 ELSE 0 END) AS aggregator,
      SUM(CASE WHEN organisation_name ILIKE '%council%' OR organisation_name ILIKE '%shire%'
               OR organisation_name ILIKE '%government%' OR organisation_name ILIKE '%department%'
               OR organisation_name ILIKE '%dept%' THEN 1 ELSE 0 END) AS govt,
      COUNT(*) AS total
    FROM listings WHERE category = 'ACCOMM'
""")
r = rows[0]
print(f"  Aggregator-owned (Hipcamp/Stayz/etc): {r[0]:,} ({100*r[0]//r[2]}%)")
print(f"  Govt/council-owned:                   {r[1]:,} ({100*r[1]//r[2]}%)")
print(f"  Other (likely direct):                {r[2]-r[0]-r[1]:,} ({100*(r[2]-r[0]-r[1])//r[2]}%)")

# ── 13. DESCRIPTION QUALITY DEEP-DIVE ────────────────────────
section("13. DESCRIPTION QUALITY — percentiles")
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

# ── 14. STATE x CATEGORY GAPS ────────────────────────────────
section("14. STATE x CATEGORY GAPS (core 5 categories)")
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
section("15. ORGANISATION NAME CASING ANOMALIES")
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
           STRING_AGG(DISTINCT address->0->>'state', ',' ORDER BY address->0->>'state') AS states
    FROM listings
    GROUP BY name
    HAVING COUNT(*) >= 5
    ORDER BY n DESC LIMIT 20
""")
print("  Names appearing 5+ times:")
for r in rows:
    print(f"  {r[1]:>4}x  {r[3]:<25}  {r[0]!r}")

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

# ── 17. IMAGE URL STABILITY ───────────────────────────────────
section("17. IMAGE URL ANALYSIS")
rows = q("""
    SELECT COUNT(*) FROM listings WHERE image_url IS NOT NULL
      AND image_url LIKE '%?q=%'
""")
print(f"  Image URLs with distributor ?q= payload: {rows[0][0]:,}")

rows = q("""
    SELECT COUNT(DISTINCT SPLIT_PART(image_url, '?', 1)) AS unique_base,
           COUNT(DISTINCT image_url) AS unique_full,
           COUNT(*) AS total_with_img
    FROM listings WHERE image_url IS NOT NULL
""")
r = rows[0]
print(f"  Unique base paths (without ?q=): {r[0]:,}")
print(f"  Unique full URLs:                {r[1]:,}")
print(f"  Total records with image:        {r[2]:,}")

# ── 18. SHARED ADDRESS ────────────────────────────────────────
section("18. SHARED ADDRESS — multiple records at same street address")
rows = q("""
    SELECT address->0->>'streetAddress' AS addr, COUNT(*) AS n,
           COUNT(DISTINCT category) AS n_cats,
           STRING_AGG(DISTINCT category, ',' ORDER BY category) AS cats
    FROM listings
    WHERE address IS NOT NULL AND jsonb_array_length(address) > 0
      AND LENGTH(COALESCE(address->0->>'streetAddress','')) > 5
    GROUP BY addr HAVING COUNT(*) >= 10
    ORDER BY n DESC LIMIT 15
""")
for r in rows:
    print(f"  {r[1]:>4,} records ({r[2]} cats: {r[3]})  {r[0]!r}")

# ── 19. MISSING ORGANISATION ─────────────────────────────────
section("19. MISSING ORGANISATION NAME")
rows = q("""
    SELECT category,
           SUM(CASE WHEN organisation_name IS NULL OR organisation_name = '' THEN 1 ELSE 0 END) AS missing,
           COUNT(*) AS total
    FROM listings GROUP BY category ORDER BY missing DESC
""")
for r in rows:
    pct = 100*r[1]//r[2] if r[2] else 0
    if r[1] > 0:
        print(f"  {r[0]:<12} missing={r[1]:>5,}/{r[2]:>6,} ({pct}%)")

# ── 20. HIPCAMP VS REST — ACCOMM quality ─────────────────────
section("20. HIPCAMP vs NON-HIPCAMP ACCOMM quality")
rows = q("""
    SELECT
      CASE WHEN organisation_name = 'Hipcamp Australia Pty Ltd.' THEN 'Hipcamp' ELSE 'Other' END AS grp,
      COUNT(*) AS n,
      ROUND(AVG(LENGTH(description))) AS avg_desc,
      ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY LENGTH(description))) AS med_desc,
      SUM(CASE WHEN latitude IS NOT NULL THEN 1 ELSE 0 END) AS has_geo,
      SUM(CASE WHEN image_url IS NOT NULL THEN 1 ELSE 0 END) AS has_img
    FROM listings WHERE category = 'ACCOMM'
    GROUP BY grp ORDER BY grp
""")
for r in rows:
    print(f"  {r[0]:<10} n={r[1]:>6,}  desc_avg={r[2]:>5}  desc_med={r[3]:>5}  geo={r[4]:>6,} ({100*r[4]//r[1]}%)  img={r[5]:>6,} ({100*r[5]//r[1]}%)")

# ── 21. BONUS: NULL-ISLAND RECORDS ───────────────────────────
section("21. NULL-ISLAND records (lat=0, lng=0)")
rows = q("""
    SELECT name, category,
           address->0->>'city' AS city,
           address->0->>'state' AS state
    FROM listings
    WHERE latitude = 0 OR longitude = 0
    ORDER BY category, name LIMIT 20
""")
for r in rows:
    print(f"  [{r[1]}] {r[0]!r:45s}  ({r[2]}, {r[3]})")

# ── 22. TERRITORIES IN THE DATASET ───────────────────────────
section("22. EXTERNAL TERRITORIES")
rows = q("""
    SELECT name, category, latitude, longitude,
           address->0->>'city' AS city,
           address->0->>'state' AS state
    FROM listings
    WHERE (latitude BETWEEN -32 AND -29 AND longitude BETWEEN 158 AND 161)  -- Lord Howe
       OR (latitude BETWEEN -11 AND -9  AND longitude BETWEEN 104 AND 108)  -- Christmas Is
       OR (latitude BETWEEN -13 AND -11 AND longitude BETWEEN 95 AND 98)    -- Cocos
       OR (latitude BETWEEN -29.5 AND -28.5 AND longitude BETWEEN 167 AND 169) -- Norfolk
    ORDER BY state, city LIMIT 25
""")
print(f"  External territory records: {len(rows)}")
for r in rows:
    print(f"  [{r[1]}] {r[0]!r:45s}  {r[2]}, {r[3]}")

conn.close()
print("\n\n=== PROBE PART 2 COMPLETE ===")
