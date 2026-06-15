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

- Is 58,151 records national or distributor-scoped? The NSW dominance in RESTAURANT (737/1,555) suggests either scope limitation or genuine state imbalance.
- Is there a single-product detail endpoint returning richer fields than the search response? (Pricing, opening hours, booking URLs, multimedia beyond one image?)
- What does `score` represent when there is no search query — all our records returned `score=1`?
- Is there a category list endpoint, or is the taxonomy only discoverable by sampling?
- What does the INACTIVE/EXPIRED flow look like? The API appears to silently drop records rather than serving them with a different status.
- What is the full set of category codes? We found 11 in ~3,000 records but there may be more.
- Are DESTINFO records the intended mechanism for destination guides, or is this an unofficial use of the product record schema?
