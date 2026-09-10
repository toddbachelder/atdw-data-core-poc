# Findings Log

Anything harder than it looked, anything that forced a decision, anything surprising.

---

## API & Connection

**API returns XML, not JSON**
The DAPI endpoint (`/api/atlas/products`) returns UTF-16LE encoded XML. Not documented anywhere obvious. Means standard JSON tooling doesn't work out of the box; `xml.etree.ElementTree` handles it fine from raw bytes but will fail if you try to pass it a decoded string (BOM issue).

**58,135 records in scope for this API key**
Unclear from the API response whether this is filtered by state/distributor or is truly national. Worth confirming — it affects how representative any sample is.

**Base URL returns 404 with an unusual error shape**
`GET /api/atlas?key=...` returns a 404 with body: `"Shared class 'atlas' has no method handling GET /?"`. Suggests a reflection-based routing system underneath. The right call is `/api/atlas/products`.

---

## Data Shape

**`addresses` has multiple `<area>` elements per address block**
The Adelaide "Rundle Mall pigs" record has two `<area>` elements under one `<address>`. A naive `findtext('area')` silently drops one. Decision: collect all `<area>` elements into a list.

**`boundary` is a single `"lat,lng"` string, not two separate fields**
Split on comma and cast to float. No issues yet, but worth watching for records where this is empty or malformed.

**`next_occurrence` is always empty on non-event product types**
Present in the schema for all records but meaningless outside of EVENTs. Not a problem but clutters the shape.

**`product_image` URL encodes distributor context as base64 JSON in the `?q=` param**
The image CDN URL contains `&q=eyJ...` which decodes to `{"type":"listing","listingId":"...","distributorId":"...","apikeyId":"..."}`. The image URL is therefore specific to this API key, not a clean asset path. If we ever need to re-serve images or cache them, this is a problem.

---

## Taxonomy & Filtering

**`productType` filter is silently ignored by the search endpoint**
Querying with `productType=TOUR`, `productType=ACCOMM`, etc. all return the same 58,151 total results and the same first 50 records. After loading 5 × 50 records, only 50 unique records landed in the DB (confirmed by upsert conflict behaviour). The category breakdown in those 50 records (ACCOMM=24, ATTRACTION=12, EVENT=11, GENSERVICE=1, HIRE=1, TOUR=1) reflects the natural mix of the top-ranked results, not 50 of each type.

The correct approach is to paginate through the full result set and filter by `product_category_id` on our side, not rely on the API to pre-filter.

**`FOOD` is not a valid `product_category_id` — the correct code is `RESTAURANT`**
After paginating through 126+ pages with FOOD=0 the entire time, a full category count revealed `RESTAURANT` with 1,555 records — the single largest category in the dataset. The brief's shortlist of TOUR / ATTRACTION / ACCOMM / FOOD / EVENT used an informal name that doesn't match the actual data taxonomy.

**The unfiltered dataset is dominated by non-listing record types**
After 126 pages (~6,300 records scanned), 3,078 were stored. Category breakdown:

| Category   | Count | Notes |
|------------|-------|-------|
| RESTAURANT | 1,555 | Food/dining — dominant category |
| DESTINFO   | 367   | Destination information — fragment? |
| GENSERVICE | 361   | General services — fragment? |
| HIRE       | 294   | Hire products — fragment? |
| JOURNEY    | 157   | Journey/itinerary records — fragment? |
| INFO       | 94    | Information records — fragment? |
| TRANSPORT  | 90    | Transport — fragment? |
| EVENT      | 40    | Target category |
| ATTRACTION | 40    | Target category |
| TOUR       | 40    | Target category |
| ACCOMM     | 40    | Target category |

DESTINFO, GENSERVICE, HIRE, JOURNEY, INFO, TRANSPORT are almost certainly the "fragments" the brief warned about. They appear to be support/meta record types rather than bookable listings. The ratio is significant: for every core listing, there are roughly 3–4 non-listing records in the stream.

**The search-side `productType` taxonomy and the record-level `product_category_id` taxonomy may not be the same thing**
Even if the filter were working, it's unclear that `productType=TOUR` would return only records with `product_category_id=TOUR`. They may be separate classification systems.

---

## Mapping Decisions

| Decision | What we chose | Why |
|---|---|---|
| Multiple `<area>` elements | Collect into array | Lossless; the alternative drops data |
| `boundary` → lat/lng | Split string, cast to float | No separate fields available |
| Empty strings vs nulls | Normalise to `None`/`null` | Cleaner to query against |

---

## Record Type Taxonomy — What's a "Core Listing" and What Isn't

After sampling one record per category, a clear line emerges between core tourism product records and everything else.

**Core listing types** — bookable or visitable tourism products with a consistent canonical shape:

| Category   | What it is | Notes |
|------------|------------|-------|
| RESTAURANT | Food & dining venues | Fully populated: name, description, address, geo, org |
| ACCOMM     | Accommodation | Fully populated |
| TOUR       | Tours & experiences | May have no lat/lng — operator address only, not tour departure point |
| ATTRACTION | Tourist attractions | Fully populated |
| EVENT      | Events | Only category with `next_occurrence` consistently populated |

**Non-listing types** — these look like listings but aren't tourism products in the bookable sense:

| Category  | What it is | Key difference |
|-----------|------------|----------------|
| DESTINFO  | Destination information (e.g. "Abrolhos Islands") | No street address; owned by visitor centres; content, not product |
| INFO      | Visitor information centres | About the centre itself, not a tourism product |
| JOURNEY   | Walking/cycling trails | Structured data (distance, difficulty) buried in description field — different content model entirely |
| GENSERVICE | General services | Extremely broad: includes B2B service providers (e.g. "Airqua — water-from-air machines for hotels") with no clear tourism relevance |
| HIRE      | Equipment/venue hire | Tourism-adjacent (e.g. wedding styling) but not a product a visitor would discover |
| TRANSPORT | Transport services | Tourism-adjacent (e.g. minibus hire) |

**The JOURNEY problem**: Trail and walk records carry structured data (distance, difficulty rating) embedded as plain text inside the `description` field, not in dedicated fields. If you ever want to surface walking tracks differently from restaurants, you'd need to parse the description to extract that structure. That's a content-modelling decision someone made — or didn't make.

**The GENSERVICE problem**: "Airqua — Water from Air machines to hotels and resorts" is in the same dataset as a Barossa Valley guest cottage. The category is too broad to be useful as a filter. Quality and relevance vary wildly.

**Structural finding**: All 11 category types return identically-shaped records from the API. There is no schema differentiation by record type at the API level. The categories are the only signal that a record is a destination guide vs a bookable tour vs a B2B service supplier.

---

## Geo Coverage

**TOUR: 62% of records have no lat/lng**
The address field is the operator's office, not the tour departure point or the geographic area the tour covers. A tour based in Adelaide CBD might operate in the Barossa — the coordinates say Adelaide. For any map-based use, TOUR geo data is misleading rather than just missing.

**JOURNEY: 82% of records have no lat/lng**
Makes sense for itineraries covering hundreds of kilometres, but not for short walking tracks. The category is internally inconsistent (see below).

**GENSERVICE: 28% missing image**
Service providers don't reliably have a photo. The highest null rate for `image_url` of any category — and GENSERVICE is the category with the most questionable tourism relevance.

---

## The JOURNEY Category Is Two Different Things

JOURNEY contains at least two structurally different record types that have been given the same category code:

1. **Walking/cycling tracks** — have Distance and Difficulty embedded in the description as plain text (e.g. "Distance: 1.5 kilometres", "Difficult: Easy"). No dedicated fields. Recoverable by regex but brittle.

2. **Multi-day itineraries** — e.g. "2 Day Accessible Quilpie Shire", "15 Day Outback Legends", "3 Day Hot Springs Trail". No distance or difficulty. These are suggested travel programs, not physical trails.

Both are labelled JOURNEY. There is no sub-category to distinguish them at the API level. This is a canonical modelling decision that was never made: trails and itineraries share a schema that fits neither well.

---

## Who Owns the Data

The `organisation_name` field reveals that records are not all entered by the operators themselves — there's a significant proxy layer:

**RESTAURANT**: Top owner is "Destination NSW" with 51 records, followed by regional visitor information centres (Camden, Ballina). A state tourism body and local government proxies are managing restaurant listings on behalf of operators — or without them. Data freshness and accuracy depends entirely on whether those proxies are actively maintaining records.

**ACCOMM**: Top owner is "Hipcamp Australia Pty Ltd" with 15 records — a third-party aggregator bulk-listing its inventory into ATDW. "Ray White Normanville" (a real estate agency) also appears. ACCOMM ownership is a mix of direct operators, aggregators, and property managers — not a clean "operator owns their listing" model.

**ATTRACTION**: Dominated by visitor information centres and government departments (Dept of Planning and Environment, Rundle Mall Management Authority). These organisations are entering records for attractions they manage or promote, not the attraction operating them.

**TOUR**: Mostly tour operators (AAT Kings, SA Eco Tours), but visitor information centres also own some TOUR records. The ownership model is inconsistent even within the same category.

**Implication**: The data custodian is often not the entity being described. There is no reliable way to contact "the operator" via the data — `organisation_name` is whoever entered the record, which may be a state body, a council, an aggregator, or the actual business.

---

## Description Quality and Richness

| Category   | Avg length | Observation |
|------------|-----------|-------------|
| DESTINFO   | 1,177 chars | Richest descriptions — content records written for visitors |
| ACCOMM     | 975 chars  | Operators write their own copy, it shows |
| JOURNEY    | 926 chars  | Mixed: trail records and itineraries, both verbose |
| TOUR       | 846 chars  | Operator copy, decent quality |
| RESTAURANT | 662 chars  | Shorter — possibly proxy-entered or lightly maintained |
| GENSERVICE | 491 chars  | Shortest — B2B services don't need tourist copy |

GENSERVICE having the shortest descriptions is consistent with it being the noisiest category: service providers writing for procurement, not visitors.

---

## State Distribution

NSW dominates every core listing category in this dataset. For RESTAURANT: NSW has 737, SA 220, QLD 181, VIC 159. The API key scope is unclear — this could reflect:
- The national dataset genuinely skewed toward NSW
- This distributor key having stronger NSW reach
- Sort order surfacing NSW-heavy records first in our paginated sample

Worth confirming whether this reflects the true national split or is an artefact of how data is allocated to this key.

**ACT has 66 RESTAURANT records but 0 ACCOMM, 0 TOUR in the sample** — likely a small sample size issue for those categories, but also consistent with Canberra being a food/dining market with less tourist accommodation listed in ATDW.

---

## Data Freshness and Expiry

Every record has an `expires_at` date — records expire on a rolling annual basis. In our dataset, 30 records expire **this month** (June 2026). The distribution clusters between now and mid-2027, suggesting most records have a 12-month renewal cycle.

**Implication for a canonical store**: Any persistent copy of this data goes stale on a known schedule. An owner of canonical data would need to either re-sync from ATDW on that schedule, or manage the expiry dates actively. The data is not a one-time export — it has a built-in TTL.

The API appears to only return `ACTIVE` records (all 3,078 records in our DB have `status = ACTIVE`). There is no signal in the API response for records that have recently expired or been deactivated — they simply disappear from the search results. A canonical store that relies on polling would have no tombstone signal when a record goes away.

---

## The Address Array Is Always Length 1

Despite our schema storing `address` as a JSONB array (because the XML `<addresses>` block can technically hold multiple `<address>` elements), zero records in the dataset have more than one address. Every record has exactly one address block. The array wrapping is technically correct but in practice unnecessary — and it means all downstream queries need `address->0->>'field'` rather than `address->>'field'`.

The multiple `<area>` elements we found earlier are within a single `<address>` block, not multiple `<address>` blocks. The schema is fine, but the complexity is in the wrong place.

---

## TOUR Geo Problem Is Worse Than It Looks

The 10 TOUR records without lat/lng aren't missing data — they have an address, just the wrong one. Every address is the operator's office:
- "Level 2, Eagle Chamber, 5 Pirie St, Adelaide" — for a wine tour that goes to the Barossa
- "AAT Kings, 48 Priest St, Alice Springs" — for Red Centre day tours
- "AAT Kings, 82-86 Bourke Rd, Alexandria NSW" — for NSW tours from a suburban Sydney depot

Placing a TOUR record on a map using its `boundary` coordinate would put it at the operator's office, not where the tour goes. For map-based discovery, TOUR coordinates are actively misleading — a user looking for tours in the Barossa would not find "A Taste of South Australia" because it maps to an Adelaide CBD address.

**Corollary**: AAT Kings has at least 5 separate records in the dataset (one per state entity: SA, NSW, NT×3, QLD, WA). A single operator appearing as 5–7 separate records with different business addresses is a deduplication problem that has no clean solution from the data alone.

---

## Aggregator Data Can Be Higher Quality Than Direct Submissions

Hipcamp Australia owns 15 of 40 ACCOMM records in the sample (37.5%). Their records are actually the richest in the ACCOMM category:
- 100% have geo coordinates (lat/lng)
- Description lengths 810–1,205 chars — longer than average
- Rural/farm stay locations with specific geographic coordinates

The instinct that "aggregator data = lower quality" doesn't hold here. Hipcamp's records are more complete than many direct operator submissions. This matters for any quality scoring or preferencing logic — the data custodian is not a reliable proxy for data quality.

---

## Area Field Has Overlapping and Hierarchical Values

Records with multiple `<area>` elements reveal inconsistent region taxonomy:

- `['Adelaide', 'City of Adelaide']` — two granularity levels for the same location (tourism region + local government area)
- `['Launceston and North', 'North West', 'North - Northeast']` — three adjacent Tasmanian regions assigned to a single business, implying the business is relevant to all three but sits in none cleanly
- `['South', 'Hobart and South']` — another hierarchical pair

The `areas` field is not a clean taxonomy. It mixes tourism marketing regions with LGA names, uses hierarchical terms at different levels, and assigns multiple values to the same record without a clear rule. Any filter built on `areas` would behave unpredictably.

---

## EVENT Records

**The API only surfaces future events** — all 40 EVENT records have `next_occurrence` in the future and none are in the past. The API appears to filter out past events at query time rather than returning them with a past date. This means:
- A canonical store populated from the API will never see a "tombstone" for an event that passed — it just stops appearing
- There's no way to know if an event was cancelled vs completed vs quietly removed
- A sync strategy based on polling needs to actively detect which records disappeared, not just which changed

**`next_occurrence` is not the event start date — it's the next upcoming occurrence**
Recurring events like "10 Toes Trivia Night" and "2 Bent Rods - All Age Fishing Lessons" show a near-future `next_occurrence` but `expires_at` months later. For one-off events, `next_occurrence` == `expires_at`. There is no field for the event's original or series start date.

**"2 Bent Rods" fishing lessons appears 8 times** — one per location (Wellington, Maroubra, Currumbin, etc.). Same operator, same event type, separate records per venue. In any listing UI this appears as 8 near-identical results. This is the same deduplication problem as AAT Kings in TOUR, but more acute for recurring events across multiple sites.

**Record names are not sanitised**: `$afety Deposit Box` appears as an event name (dollar sign prefix). Sorts before alphabetical characters. No normalisation at the data layer.

**`organisation_name` casing is inconsistent with `name`**: The RESTAURANT record for "A Table of 10" has `organisation_name = "a table of 10"` (lowercase) vs `name = "A Table of 10"` (title case). These fields are entered separately and there's no enforcement of consistent casing.

---

## Open Questions

- ~~Is 58,151 records national or distributor-scoped?~~ **Answered (June 2026)**: 58,388 records via DAPI for this distributor key. The ATDW PlatformDB contains 190,280 listings — the DAPI is a filtered distributor projection, not a full platform mirror. NSW dominance (43% of records) is real, not sampling bias.
- Is there a single-product detail endpoint returning richer fields than the search response? (Pricing, opening hours, booking URLs, multimedia beyond one image?)
- What does `score` represent when there is no search query — all our records returned `score=1`?
- Is there a category list endpoint, or is the taxonomy only discoverable by sampling? **Partial answer**: 11 categories confirmed in the full 58,388-record national dataset.
- ~~What does the INACTIVE/EXPIRED flow look like?~~ **Answered**: The API silently drops records — all 58,388 records are ACTIVE. No inactive or expired state is ever visible.
- ~~What is the full set of category codes?~~ **Answered**: 11 codes: ACCOMM, ATTRACTION, EVENT, RESTAURANT, TOUR, DESTINFO, GENSERVICE, HIRE, JOURNEY, INFO, TRANSPORT.
- Are DESTINFO records the intended mechanism for destination guides, or is this an unofficial use of the product record schema?

---

## Full National Dataset — Confirmed Findings at Scale (June 2026)

The full national ingest completed June 2026: **58,388 records** ingested from 19,511 pages at 3 records/page. Runtime: 5h 26m. All findings below supersede the probe-sample numbers above.

### Category Breakdown

| Category   | Count  | % of total | Geo coverage | Image coverage |
|------------|--------|-----------|-------------|----------------|
| ACCOMM     | 16,247 | 27.8%     | 100%        | 100%           |
| ATTRACTION | 14,833 | 25.4%     | 100%        | 99%            |
| EVENT      | 8,954  | 15.3%     | 100%        | 99%            |
| RESTAURANT | 8,282  | 14.2%     | 100%        | 100%           |
| TOUR       | 3,465  | 5.9%      | 45% (**54.6% missing**) | —   |
| DESTINFO   | 1,955  | 3.3%      | 100%        | —              |
| GENSERVICE | 1,803  | 3.1%      | 100%        | 71%            |
| HIRE       | 1,224  | 2.1%      | —           | —              |
| JOURNEY    | 734    | 1.3%      | 16% (**83.6% missing**) | —  |
| INFO       | 498    | 0.9%      | —           | —              |
| TRANSPORT  | 393    | 0.7%      | —           | —              |

### State Distribution (confirmed national)

| State | Records | % |
|-------|---------|---|
| NSW   | 21,725  | 43% |
| QLD   | 8,532   | 16% |
| SA    | 6,767   | 13% |
| VIC   | 6,008   | 12% |
| WA    | 3,552   | 7%  |
| TAS   | 2,982   | 6%  |
| NT    | 1,133   | 2%  |
| ACT   | 1,082   | 2%  |

NSW dominance (43%) is confirmed as a genuine data skew, not a sampling artefact.

### Custodian / Operator Confirmed at Scale

**ACCOMM**: Hipcamp Australia owns 2,158 records — **13.3% of all accommodation** from a single third-party aggregator. Average quality is higher than direct submissions (100% geo, 100% image).

**ATTRACTION**: Department of Planning and Environment NSW owns 1,395 records — **9.4% of all attractions** from a single government agency.

**RESTAURANT**: Destination NSW owns 251 restaurant records (3% of all RESTAURANT) entered as proxy custodian.

### Deduplication at Scale

- **AAT Kings**: 10 records confirmed across 6 states (SA, NSW, NT, QLD, WA).
- **2 Bent Rods**: 9 records in QLD — same operator, separate records per venue.
- **Multi-area records**: 4,334 records carry more than one area tag.

### Geo Findings Confirmed

- **TOUR**: 1,891 of 3,465 records missing geo (54.6%) — confirmed finding. The 38% with coordinates point to operator offices.
- **JOURNEY**: 614 of 734 records missing geo (83.6%) — confirmed finding.
- ACCOMM, ATTRACTION, EVENT, RESTAURANT: all effectively 100% geo.

### Expiry at Scale

1,688 records expire **June 2026** (this month). The 12-month renewal cycle creates a rolling refresh obligation — this is material, not a footnote.

### DAPI Coverage Gap (New Finding)

The ATDW DAPI returned 58,388 records for this distributor key. The authoritative ATDW PlatformDB (queried directly via CData Connect Cloud) contains **190,280 listings**. The DAPI is a filtered distributor projection exposing roughly **30.7% of platform data**. Any canonical store built from DAPI alone is structurally incomplete relative to the full platform.

---

## Full Dataset Probe — New Findings (June 2026)

The following findings emerged from running analytical queries across the complete 58,388-record national dataset. These are new patterns not visible in the 3,078-record probe sample.

### External Territories — 112 records outside the mainland bounding box

112 records have coordinates that fall outside the standard Australian mainland bounding box (lat −10°S to −44°S, lng 113°E to 154°E). These are not errors — they are legitimate Australian territories:

| Territory | ~Records | Coordinates | State |
|-----------|---------|-------------|-------|
| Lord Howe Island | ~20 | −31.5°, 159.1° | NSW |
| Cocos (Keeling) Islands | ~6 | −12.2°, 96.8° | WA |
| Christmas Island | ~2 | −10.4°, 105.7° | WA |
| Norfolk Island | ~1 | −29.0°, 168.0° | NSW |

Any geo filter, map viewport, or bounding-box query that clips to mainland Australia will silently exclude these records. This is a deliberate architecture decision, not a data error — but it needs to be made deliberately.

### Null-Island Geocoding — 28 records at lat=0, lng=0

28 records have non-null latitude and longitude, both set to exactly 0.0 — the null-island coordinate in the Gulf of Guinea. These are real Australian places with broken geocoding: SEA LIFE Sydney, Queensland Parliament House, Dashville (Lower Belford NSW), Francvillers Station (Cunnamulla QLD). These records pass a `latitude IS NOT NULL` filter and would be plotted in West Africa on a map. A `latitude != 0 AND longitude != 0` validation step is required.

### Event Timing Drift — 457 events with past next_occurrence

457 EVENT records have `next_occurrence` in the past. The DAPI filters future events at query time, but a canonical store ingest freezes the state at ingest time. Events that occurred after the ingest are not automatically removed. Without regular re-sync the canonical store accumulates stale EVENT records silently. Note also: of 8,954 total EVENTs, **50% are one-off** (next_occurrence == expires_at) and **49% are recurring** (next_occurrence ≠ expires_at).

### GENSERVICE Is a Regional Tourism Body Dumping Ground

GENSERVICE top-5 concentration is 34% — far higher than any other category. Destination Southern Tasmania alone owns 351 GENSERVICE records (19% of the category). East Coast Tasmania Tourism owns 130. Regional tourism bodies appear to be using GENSERVICE as a catch-all for content that doesn't fit tourism product categories — destination guides, regional info, facilities. This compresses the already-low utility of GENSERVICE as a filter.

### Organisation Name Normalisation — 4,135 ALL-CAPS entries

4,135 records have ALL-CAPS organisation names (e.g., ADELAIDE FESTIVAL CENTRE, WAITOC, KEG TOURING). 167 records have all-lowercase org names. One org name is a phone number: `0410405278`. The data has no normalisation at the custodian-entry level — organisation names will sort, display, and match inconsistently without a standardisation step.

### Hipcamp Data Quality NOT Exceptional at Scale

At the 15-record probe sample, Hipcamp records appeared higher quality. At 2,158 records the difference is negligible: Hipcamp ACCOMM avg description 900 chars vs 917 chars for all others; geo 100% vs 100%; image 100% vs 100%. The "aggregator data = higher quality" hypothesis from the probe sample does not hold at national scale. Hipcamp records are equivalent, not superior.

### Image URL Finding Confirmed at 100%

The earlier probe noted that image URLs carry a `?q=` distributor payload. At full dataset the URL structure reveals the parameter is actually `&q=` (after rect, w, h, rot params), not the leading query param. All **57,874** image URLs contain a `&q=` base64 JSON payload encoding distributorId and apikeyId. Every image URL in the canonical store is distributor-scoped and will break if the key rotates.

### JOURNEY Sub-Type Detection: 90% Unclassifiable

Only 5% of JOURNEY records have trail signals (Distance/Difficulty/Grade) in descriptions; 3% have N-day itinerary signals. The remaining 90% have neither. Deriving JOURNEY sub-type from description parsing is not a viable approach for the majority of records — additional metadata or human curation would be needed.

### Cross-State Operators — Name Deduplication Scale

793 distinct names appear on 2+ records. There are 930 excess records (records beyond the first instance of each name). Notable national operators appearing 7x across all states: Australian Geographic Travel, Auswalk Walking Holidays, Australian Air Safaris. "Rugby World Cup (Australia)" holds 60 EVENT records across 5 states — likely stale from a past tournament.

## Platform Re-Architecture Probe — DAPI Component (June 2026)

Hit the live DAPI directly with the existing key (not the translated `listings` table) to see what the raw API surface actually exposes, ahead of the web-portal/DAPI re-architecture work. Script: `src/probe_dapi_api.py`, raw samples in `docs/dapi_raw/`.

### The /products list endpoint is a thin slice of what DAPI actually has

`/products` (the endpoint `ingest.py` has always used) returns only **16 top-level fields** per record — name, description, category, organisation, image, address, status, expiry, next_occurrence, etc. This is the entire universe the canonical schema and the standards-mapping tab have been built against so far.

### /product (single-record detail) exposes ~3x more, and it is structurally different

Calling `/product?productId=<id>` for one real TOUR record returned **194 distinct tags** (including nested service data), with ~46 of them new top-level fields never seen via `/products` or captured anywhere in the canonical schema: `australian_business_number`, `check_in_time`/`check_out_time`, `disabled_access_flag`/`_text`, `pets_allowed_flag`/`_text`, `children_catered_for_flag`/`_text`, `rate_from`/`rate_to`, `attribute_id_currency`, `number_of_rooms`, `total_capacity`, `stra_property_id_number`, `international_ready_flag`, `nearest_gateway`/`_distance`, `validity_date_from`/`_to`, `brochure_available_flag`, `deal_flag`, `job_flag`. None of this is reachable through the list endpoint at all — it only exists if you fetch every product individually by ID.

### /productservice requires BOTH productId and serviceId — and is richer again

`/productservice` 400s with "Product Id and Service Id are mandatory" unless given both. The `service_id` has to be harvested from the nested `<service_id>` block embedded inside a `/product` detail response — it isn't surfaced by `/products` at all. Once called correctly, a single service record returned **123 distinct tags**: pricing ranges (`range_1_from_rate`/`_to_rate`), booking config (`service_booking`, `service_booking_with_tracking`, `service_configuration`), capacity (`minimum_capacity`/`maximum_capacity`), departure data (`service_departure_date`, `departure_time`, `journey_route`, `end_location_text`), and multimedia with `photographer`/`copyright` credit fields.

### Implication for the re-architecture work

A future-state DAPI (or its replacement) can't be scoped from the list endpoint alone — the bulk of the platform's actual product/service data (pricing, accessibility, capacity, booking config) is only visible one record at a time via two extra round-trips per product. Any redesign that wants this data at scale needs either a bulk detail endpoint that doesn't exist today, or N+1 API calls per product — itself a re-architecture-worthy finding for the DAPI component.

## Canonical Store Outage and Recovery — Supabase (September 2026)

A routine status check found the canonical store unreachable: the pooler returned `FATAL XX000 — (ENOTFOUND) tenant/user postgres.eszrwktyqpkfblfhitbz not found`, and the project subdomain returned **NXDOMAIN** from both Google and Cloudflare DNS. Both the `aws-0-` and `aws-1-` regional poolers rejected the tenant identically. The project was subsequently recovered by ATDW and the store is fully intact — but the outage exposed several things worth recording.

### The data survived; 58,388 rows recovered intact

Post-recovery verification: **58,388 rows**, all 17 columns, all four indexes (`listings_pkey`, `listings_source_id_key`, `listings_category_idx`, `listings_status_idx`) present. `source_id` uniqueness holds at 58,388 distinct values, zero null names, and the ingest window is unchanged at 2026-06-15 → 2026-06-18. Decisively, `image_url` is populated on **57,874** rows — the exact figure recorded in the image-URL finding above, confirming byte-level continuity rather than a partial restore. Category split: ACCOMM 16,247 / ATTRACTION 14,833 / EVENT 8,954 / RESTAURANT 8,282 / TOUR 3,465 / DESTINFO 1,955 / GENSERVICE 1,803 / HIRE 1,224 / JOURNEY 734 / INFO 498 / TRANSPORT 393.

### Recovery moved the project ref twice, and credentials do not follow

The recovery first surfaced the data under a **new project ref** (`gcpsdqotpevjhdlffsas`), then it was moved back to the original ref (`eszrwktyqpkfblfhitbz`). Each ref is a separate project with separate credentials, so a password reset performed on the interim project did not apply to the final one — a full reset had to be repeated against the ref the data ultimately landed on. Any runbook for this has to treat *project ref* and *database password* as a matched pair; neither survives a move on its own.

### The error codes distinguish the failure modes precisely

Worth recording because the three are easily conflated, and each points somewhere different:
- `XX000 (ENOTFOUND) tenant not found` — Supavisor has no tenant registered. Project absent, or pooler registration not yet propagated.
- `28P01` with **no** `F`/`L`/`R` fields — pooler-synthesised auth rejection.
- `28P01` **with** `'F': 'auth.c', 'R': 'auth_failed'` — the real PostgreSQL backend rejected it, meaning the pooler forwarded successfully and only the credential is wrong.
Additionally, a bad database name returns `3D000`, not `28P01` — so `28P01` positively confirms host, tenant, and username format are all correct. During recovery the tenant registration was observed flipping from `ENOTFOUND` to `28P01` mid-poll, which is how pooler propagation presents.

### Direct Postgres connections are unavailable from the ATDW network

`db.<ref>.supabase.co` resolves **AAAA-only** (IPv6). The workstation used for this probe has no IPv6 egress — a raw socket to `2001:4860:4860::8888` fails with `WinError 10051, network unreachable`. Every direct connection attempt therefore fails regardless of credentials, and **the Supavisor pooler is the only viable Postgres path**. An IPv4-only lookup reports "no DNS record" and reads like a deleted project, which is actively misleading. Any future-state component that assumes direct Postgres reachability needs to account for this.

### National record count has drifted: 58,135 → 58,817

The DAPI list endpoint now reports **58,817** total results, up **682 (+1.2%)** from the 58,135 recorded earlier in this log, and 429 above the 58,388 rows in the store. Any total quoted from this probe needs a date attached.

### Implication for the re-architecture work

Nothing else in the pipeline degraded — DAPI returned HTTP 200 in 0.56s and the translation layer parsed 50/50 records with zero errors throughout. **The hosted store was the single point of failure.** The recovery was successful, but it depended on the vendor's own restore process, took multiple ref moves, and invalidated credentials twice along the way. The reconstruction path that actually de-risked this was ATDW-controlled: the source (DAPI) is ATDW-owned and the translation layer is in version control, so the store was rebuildable regardless of the vendor's outcome. That is the property any future-state architecture has to preserve — the canonical store must be reconstructible from ATDW-controlled inputs, not merely backed up by whoever is hosting it. This is a small-scale rehearsal of the exit-risk and data-portability concerns driving the Magpie partnership analysis.
