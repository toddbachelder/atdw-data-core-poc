# -*- coding: utf-8 -*-
"""Build the Redlands->Fremantle accessible EV itinerary as a Word document.

Content is sourced from ATDW listing/profile records retrieved via the
atdw-pilot MCP server on 2026-09-07. Appendix A records the MCP steps.
"""
import docx
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from docx.opc.constants import RELATIONSHIP_TYPE as RT

doc = Document()

# ---------- base styles ----------
st = doc.styles['Normal']
st.font.name = 'Calibri'
st.font.size = Pt(10.5)
st.paragraph_format.space_after = Pt(6)
st.paragraph_format.line_spacing = 1.08

for name, size, color, bold in [
    ('Heading 1', 18, '1F3864', True),
    ('Heading 2', 14, '2E5496', True),
    ('Heading 3', 11.5, '2E5496', True),
]:
    s = doc.styles[name]
    s.font.name = 'Calibri'
    s.font.size = Pt(size)
    s.font.bold = bold
    s.font.color.rgb = RGBColor.from_string(color)
    s.paragraph_format.space_before = Pt(14)
    s.paragraph_format.space_after = Pt(5)


def add_hyperlink(paragraph, url, text):
    part = paragraph.part
    r_id = part.relate_to(url, RT.HYPERLINK, is_external=True)
    h = OxmlElement('w:hyperlink')
    h.set(qn('r:id'), r_id)
    r = OxmlElement('w:r')
    rPr = OxmlElement('w:rPr')
    c = OxmlElement('w:color')
    c.set(qn('w:val'), '0563C1')
    rPr.append(c)
    u = OxmlElement('w:u')
    u.set(qn('w:val'), 'single')
    rPr.append(u)
    sz = OxmlElement('w:sz')
    sz.set(qn('w:val'), '19')
    rPr.append(sz)
    r.append(rPr)
    t = OxmlElement('w:t')
    t.text = text
    t.set(qn('xml:space'), 'preserve')
    r.append(t)
    h.append(r)
    paragraph._p.append(h)


def para(text='', style=None, bold=False, italic=False, size=None,
         space_after=None, indent=None):
    p = doc.add_paragraph(style=style)
    if text:
        r = p.add_run(text)
        r.bold = bold
        r.italic = italic
        if size:
            r.font.size = Pt(size)
    if space_after is not None:
        p.paragraph_format.space_after = Pt(space_after)
    if indent is not None:
        p.paragraph_format.left_indent = Inches(indent)
    return p


def rich(segments, style=None, indent=None, space_after=None):
    """segments: list of (text, {bold, italic, link, size, color})"""
    p = doc.add_paragraph(style=style)
    for text, opt in segments:
        if opt.get('link'):
            add_hyperlink(p, opt['link'], text)
        else:
            r = p.add_run(text)
            r.bold = opt.get('bold', False)
            r.italic = opt.get('italic', False)
            if opt.get('size'):
                r.font.size = Pt(opt['size'])
            if opt.get('color'):
                r.font.color.rgb = RGBColor.from_string(opt['color'])
    if indent is not None:
        p.paragraph_format.left_indent = Inches(indent)
    if space_after is not None:
        p.paragraph_format.space_after = Pt(space_after)
    return p


def shade(cell, hexcolor):
    tcPr = cell._tc.get_or_add_tcPr()
    sh = OxmlElement('w:shd')
    sh.set(qn('w:val'), 'clear')
    sh.set(qn('w:fill'), hexcolor)
    tcPr.append(sh)


def table(headers, rows, widths=None, header_fill='1F3864'):
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = 'Table Grid'
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    hdr = t.rows[0].cells
    for i, h in enumerate(headers):
        hdr[i].text = ''
        p = hdr[i].paragraphs[0]
        p.paragraph_format.space_after = Pt(2)
        r = p.add_run(h)
        r.bold = True
        r.font.size = Pt(9.5)
        r.font.color.rgb = RGBColor.from_string('FFFFFF')
        shade(hdr[i], header_fill)
    for row in rows:
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = ''
            p = cells[i].paragraphs[0]
            p.paragraph_format.space_after = Pt(2)
            r = p.add_run(str(v))
            r.font.size = Pt(9.5)
    if widths:
        for i, w in enumerate(widths):
            for row in t.rows:
                row.cells[i].width = Inches(w)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return t


def callout(text, fill='FFF2CC'):
    t = doc.add_table(rows=1, cols=1)
    t.style = 'Table Grid'
    c = t.rows[0].cells[0]
    shade(c, fill)
    c.text = ''
    p = c.paragraphs[0]
    r = p.add_run(text)
    r.font.size = Pt(9.5)
    r.italic = True
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


# =========================================================
# TITLE
# =========================================================
h = doc.add_heading('Redlands, QLD to Fremantle, WA', level=0)
for r in h.runs:
    r.font.color.rgb = RGBColor.from_string('1F3864')
para('Accessible EV Road Trip Itinerary', size=13, italic=True, space_after=2)
para('Approximately 4,400 km  |  9 nights driving  |  Charging staged at 400 km or less',
     size=10, space_after=2)
para('Compiled 7 September 2026 from ATDW listing data via the ATDW pilot MCP server. '
     'Total compilation runtime: 44 minutes (see Appendix A.7).',
     size=9, italic=True)

# =========================================================
# 1. THE REQUEST
# =========================================================
doc.add_heading('1. The Request', level=1)
para('The itinerary below was produced in response to the following request, quoted verbatim:',
     size=10, space_after=8)

t = doc.add_table(rows=1, cols=1)
t.style = 'Table Grid'
c = t.rows[0].cells[0]
shade(c, 'EDF2F9')
c.text = ''
p = c.paragraphs[0]
r = p.add_run('"please create me an itinerary to trval from redlands/qld to freemantle, wa. '
              'Include hotels which can accomidate a wheelchair for overnight stays and have '
              'prices between 300-400 a night. Include restaurants which have hamburgers and '
              'gluten free options on the menu, but no fastfood, I want proper burgers. I also '
              'need to stop every 400km to charge my EV car. provide me a list of things to do '
              'along the trip which are ecofriendly. Include direct booking options for hotels '
              'and restaurents."')
r.italic = True
r.font.size = Pt(10)
doc.add_paragraph().paragraph_format.space_after = Pt(2)

para('Decomposed into hard requirements:', bold=True, size=10)
for b in [
    'Road-trip itinerary from Redlands QLD to Fremantle WA.',
    'Hotels: wheelchair accessible AND $300-400 per night, for overnight stays.',
    'Restaurants: hamburgers AND gluten-free options on the same menu; no fast food.',
    'EV charging: a stop at least every 400 km.',
    'Things to do: eco-friendly, along the route.',
    'Direct booking options for both hotels and restaurants.',
]:
    para(b, style='List Bullet', size=10, space_after=2)

# =========================================================
# 2. AT A GLANCE
# =========================================================
doc.add_heading('2. Summary at a Glance', level=1)
table(
    ['Day', 'Leg', 'km', 'Overnight (all wheelchair accessible)', 'Indicative rate',
     'In $300-400?'],
    [
        ['1', 'Redlands to Goondiwindi QLD', '440', '40 on Marshall Boutique Hotel',
         '$180-240', 'No - below'],
        ['2', 'Goondiwindi to Dubbo NSW', '570', 'Quest Dubbo', '$189-649', 'Yes'],
        ['3', 'Dubbo to Mildura VIC', '750', 'Quality Hotel Mildura Grand', '$100-375',
         'Yes, at top'],
        ['4', 'Mildura to Adelaide SA', '400', 'Crowne Plaza Adelaide', '$275-580', 'Yes'],
        ['5', 'Adelaide to Ceduna SA', '770', 'Ceduna Foreshore Hotel Motel', '$135-195',
         'No - below'],
        ['6', 'Ceduna to Border Village / Eucla', '490',
         'Nullarbor roadhouse - not verifiable', 'Not recorded', 'Unable to confirm'],
        ['7', 'Eucla to Caiguna', '270', 'Nullarbor roadhouse - not verifiable',
         'Not recorded', 'Unable to confirm'],
        ['8', 'Caiguna to Kalgoorlie WA', '560', 'Quality Inn Railway Motel', '$219-325',
         'Yes, at top'],
        ['9', 'Kalgoorlie to Fremantle WA', '600', 'Esplanade Hotel Fremantle by Rydges',
         '$190-390', 'Yes'],
    ],
    widths=[0.4, 1.85, 0.42, 2.05, 0.95, 0.95]
)
para('Rates are indicative published rates recorded against each listing, not guaranteed '
     'current prices. Confirm at the point of booking.', size=8.5, italic=True)

# =========================================================
# 3. FOUR THINGS UP FRONT
# =========================================================
doc.add_heading('3. Four Things to Know Up Front', level=1)
para('These change how the plan should be used, so they are stated before the plan itself.',
     size=10, italic=True, space_after=8)

items = [
    ('Accessibility is verified at property level, not room level.',
     'Every hotel listed is confirmed wheelchair accessible in its ATDW listing. That attribute '
     'is recorded against the property, not against individual rooms, so "accessible property" '
     'is verified while "accessible room at this price" is not. Confirm the room type when '
     'booking. Only one property on the route - Quality Inn Railway Motel, Kalgoorlie - names a '
     '"Disabled Access" room type in its own rate notes.'),
    ('The $300-400 band is not achievable across the middle of the route.',
     'It works at Dubbo, Mildura, Adelaide, Kalgoorlie and Fremantle. It does not exist at '
     'Goondiwindi, Ceduna, or anywhere on the Nullarbor - those towns do not have accessible '
     'stock at that price. Port Augusta has zero wheelchair-accessible accommodation listed at '
     'all, and Norseman has exactly one accommodation listing, which records no wheelchair '
     'attribute. Rather than drop those stops silently, the best available accessible option is '
     'given instead, and marked as out of band.'),
    ('EV charging is not held in ATDW at all.',
     'Every charge point below is a construction based on town and roadhouse spacing, not '
     'verified data. ATDW records no EV charging concept; the only charging-related entry in its '
     'vocabulary refers to a wheelchair or scooter charging point. Confirm actual chargers in '
     'PlugShare or Chargefox before departure - above all for the Nullarbor.'),
    ('There is no eco-certification field in ATDW.',
     'The activities below are verified as national parks, reserves and natural attractions, and '
     'several are Aboriginal-owned. That is a strong nature-based proxy and genuinely '
     'low-impact, but it is not a certified sustainability credential. A sustainability score '
     'field does exist on listings, but it was empty on every listing checked.'),
]
for i, (title, body) in enumerate(items, 1):
    rich([('%d.  ' % i, {'bold': True}), (title, {'bold': True})], space_after=2)
    para(body, size=10, indent=0.28, space_after=9)

# =========================================================
# 4. DAY BY DAY
# =========================================================
doc.add_heading('4. Day-by-Day Itinerary', level=1)


def day(title, charge, blocks, warnings=None):
    doc.add_heading(title, level=2)
    rich([('Charging: ', {'bold': True, 'size': 10}), (charge, {'size': 10})], space_after=8)
    for label, name, lines, link, linktext in blocks:
        rich([(label + ' - ', {'bold': True, 'size': 10}),
              (name, {'bold': True, 'size': 10})], space_after=2)
        for ln in lines:
            para(ln, size=10, indent=0.28, space_after=2)
        if link:
            p = rich([(linktext + ': ', {'size': 10})], indent=0.28, space_after=9)
            add_hyperlink(p, link, link)
        else:
            doc.add_paragraph().paragraph_format.space_after = Pt(4)
    if warnings:
        for w in warnings:
            callout(w)


day('Day 1  |  Redlands to Goondiwindi QLD  -  440 km',
    'Toowoomba at 160 km, then Goondiwindi at 280 km.',
    [
        ('Lunch', 'The Rock, Toowoomba',
         ['Hamburgers and gluten-free options both confirmed on the menu.'],
         'https://www.therockpub.com.au/book-a-table', 'Book a table'),
        ('Stay', '40 on Marshall Boutique Hotel, Goondiwindi',
         ['Wheelchair accessible: confirmed.',
          'Indicative rate $180-240 - below the requested band. It is the best accessible '
          'option in town.'],
         'https://40onmarshall.bookus.direct/', 'Book direct'),
        ('Nature', 'Macintyre River Walk, Goondiwindi',
         ['A 3 km tree-lined riverwalk with prolific birdlife and interpretive environmental '
          'signage. No booking required.'],
         None, None),
    ],
    ['Goondiwindi has no listing combining hamburgers and gluten-free options, and nothing '
     'within 200 km except the Toowoomba and Dalby options. Eat on the way in.'])

day('Day 2  |  Goondiwindi to Dubbo NSW  -  570 km',
    'Moree at 120 km, Narrabri at 220 km, Coonabarabran at 370 km, then Dubbo.',
    [
        ('Dinner', "Devil's Hollow Brewery, Dubbo",
         ['Hamburgers and gluten-free options both confirmed on the menu.'],
         'https://devilshollow.com.au/pages/book-a-table', 'Book a table'),
        ('Stay', 'Quest Dubbo',
         ['Wheelchair accessible: confirmed.',
          'Indicative rate $189-649 - the requested band is available here.'],
         'https://www.questapartments.com.au/properties/nsw/dubbo/quest-dubbo', 'Book direct'),
        ('Nature', 'Beni State Conservation Area and Terramungamine Rock Grooves',
         ['Beni State Conservation Area: birdwatching, bushwalking and cycling, 10 km from '
          'the CBD.',
          'Terramungamine Rock Grooves: approximately 150 grinding grooves carved by the '
          'Tubbagah people of the Wiradjuri nation.'],
         None, None),
    ])

day('Day 3  |  Dubbo to Mildura VIC  -  750 km  (long day)',
    'Parkes at 110 km, Griffith at 380 km, Balranald at 600 km, then Mildura.',
    [
        ('Dinner', 'Kokomo at Trentham Waters, Trentham Cliffs',
         ['Hamburgers and gluten-free options both confirmed on the menu. 10 km from Mildura.'],
         'https://trenthamwatersmildura.com.au/restaurant/#booking-form', 'Book a table'),
        ('Stay', 'Quality Hotel Mildura Grand',
         ['Wheelchair accessible: confirmed.',
          'Indicative rate $100-375 - the top of the range meets the requested band.'],
         'https://www.thebookingbutton.com.au/properties/QUALITYMILDURADIRECT', 'Book direct'),
        ('Nature', 'Bottle Bend Reserve and Trail of Lights',
         ['Bottle Bend Reserve, Monak NSW: Murray River walking tracks, birdwatching and '
          'canoeing, 18 km out.',
          'Trail of Lights: an immersive Murray River night walk.'],
         'https://tickets.mildura.com/BookingProduct/ProductList/?Category=WEBSITE', 'Tickets'),
    ],
    ['This is the longest driving day in the plan, roughly 8.5 hours. There is no verified '
     'accessible, in-band accommodation at Griffith or Hay with which to split it, so it is '
     'either one push or an unverified stopover.'])

day('Day 4  |  Mildura to Adelaide SA  -  400 km',
    'Renmark at 130 km, then Adelaide.',
    [
        ('Lunch', 'Hotel Renmark',
         ['Hamburgers and gluten-free options both confirmed on the menu. Doubles as the '
          'charge stop.'],
         'https://bookings.nowbookit.com/?venueid=5366', 'Book a table'),
        ('Stay', 'Crowne Plaza Adelaide',
         ['Wheelchair accessible: confirmed.',
          'Indicative rate $275-580 - the requested band sits inside this range.'],
         'https://adelaide.crowneplaza.com/offers/sunny-escapes-family-package', 'Book direct'),
        ('Alternative stay', 'Hotel Alba Adelaide',
         ['Wheelchair accessible: confirmed. Indicative rate $209-369 - a tighter fit to '
          'the band.'],
         'https://www.hotelalba.com.au/rates/', 'Book direct'),
        ('Low-impact activity', "Captain Jolley's Paddle Boats, Torrens River",
         ['Pedal-powered, no motor. Pelicans are common on this stretch of the river.'],
         'https://www.captainjolleys.com.au/bookings', 'Book'),
    ])

day('Day 5  |  Adelaide to Ceduna SA  -  770 km',
    'Port Augusta at 305 km, Kimba at 460 km, Wudinna at 570 km, then Ceduna.',
    [
        ('Lunch', 'Bluebush Cafe, Australian Arid Lands Botanic Garden, Port Augusta West',
         ['Hamburgers and gluten-free options both confirmed on the menu.',
          'The best stop of the day: a cafe inside an arid-zone botanic garden, so it serves as '
          'both the meal and the nature stop. No online booking recorded - walk in or phone.'],
         None, None),
        ('Stay', 'Ceduna Foreshore Hotel Motel',
         ['Wheelchair accessible: confirmed.',
          'Indicative rate $135-195 - below the requested band. It is the only accessible '
          'property in Ceduna.'],
         'https://www.thebookingbutton.com.au/properties/CEDUNAFORSHOREDIRECT', 'Book direct'),
    ],
    ['Port Augusta has zero wheelchair-accessible accommodation listed. Do not plan to '
     'overnight there.',
     'Ceduna has no hamburger listing at all, at any radius up to 400 km. The nearest is Drift '
     'Streaky Bay, 90 km back east - hamburgers confirmed, gluten-free unable to confirm.'])

# ---- Nullarbor ----
doc.add_heading('Days 6 to 8  |  The Nullarbor: Ceduna to Kalgoorlie  -  1,320 km', level=2)
para('This is the weakest-covered segment of the route and needs the most planning outside this '
     'itinerary. Suggested staging, roadhouse to roadhouse, with every leg under 400 km:',
     size=10, space_after=8)
table(['Day', 'Leg', 'km'],
      [['6', 'Ceduna to Nullarbor Roadhouse to Border Village / Eucla', '490'],
       ['7', 'Eucla to Madura to Caiguna', '270'],
       ['8', 'Caiguna to Balladonia to Norseman to Kalgoorlie', '560']],
      widths=[0.5, 4.7, 0.7])

para('What cannot be supplied here', bold=True, size=10)
for b in [
    'No wheelchair-accessible, in-band accommodation is listed anywhere between Ceduna and '
    'Kalgoorlie. Norseman has exactly one accommodation listing - Acclaim Gateway Tourist Park - '
    'and it records no wheelchair attribute. Nullarbor roadhouse rooms will need to be booked '
    'direct by phone, asking about access specifically.',
    'Charging across the Nullarbor must be verified before committing. The roadhouse spacing '
    'works geographically; whether each has a working, usable charger is precisely what ATDW '
    'cannot say.',
]:
    para(b, style='List Bullet', size=10, space_after=4)

para('Nature stops - the strongest on the trip', bold=True, size=10)
rich([('Mamungari Conservation Park', {'bold': True, 'size': 10}),
      (' - a UNESCO World Biosphere Reserve; red sand dunes and salt lakes, traditionally owned '
       'by and culturally significant to the Maralinga Tjarutja peoples.', {'size': 10})],
     style='List Bullet', space_after=3)
p = rich([('YALATA - Camping and Fishing', {'bold': True, 'size': 10}),
          (' - Aboriginal-owned coastal wilderness on the Great Australian Bight. ',
           {'size': 10})],
         style='List Bullet', space_after=3)
add_hyperlink(p, 'https://yalata.com.au/camping-fishing/', 'yalata.com.au/camping-fishing')
rich([('Wittelbee Conservation Park', {'bold': True, 'size': 10}),
      (' - samphire flats, hooded plovers and oyster catchers.', {'size': 10})],
     style='List Bullet', space_after=8)

rich([('Stay - ', {'bold': True, 'size': 10}),
      ('Quality Inn Railway Motel, Kalgoorlie', {'bold': True, 'size': 10})], space_after=2)
para('Wheelchair accessible: confirmed.', size=10, indent=0.28, space_after=2)
para('Indicative rate $219-325 - meets the requested band. Its own rate notes name a "Disabled '
     'Access" room type, the only listing on the route that does.',
     size=10, indent=0.28, space_after=2)
para('No online booking recorded. Phone 08 9088 0000 or email welcome@railwaymotel.com.au',
     size=10, indent=0.28, space_after=9)

rich([('Goldfields nature: ', {'bold': True, 'size': 10}),
      ('Burra Rock Conservation Park (granite outcrop and historic catchment dam); Red Hill '
       'Lookout, Kambalda East (summit walk over the Lake Lefroy salt lake); Cave Hill Nature '
       'Reserve, Coolgardie (bushland walking trails and cave formations).', {'size': 10})],
     space_after=8)

callout('Kalgoorlie has no listing combining hamburgers and gluten-free options, in town or '
        'within 200 km. Plan to eat at the hotel.')

day('Day 9  |  Kalgoorlie to Fremantle WA  -  600 km',
    'Southern Cross at 190 km, Merredin at 300 km, Northam at 475 km, then Fremantle.',
    [
        ('Dinner', 'Bathers Beach House, Fremantle',
         ['Hamburgers and gluten-free options both confirmed on the menu.'],
         'http://www.bathersbeachhouse.com.au/reservations', 'Book a table'),
        ('Stay', 'Esplanade Hotel Fremantle by Rydges',
         ['Wheelchair accessible: confirmed.',
          'Indicative rate $190-390 - meets the requested band.'],
         'https://www.rydges.com/rates/?hotelCode=RWFRES', 'Book direct'),
        ('Alternative stay', 'The Hougoumont Hotel, Fremantle',
         ['Wheelchair accessible: confirmed. Indicative rate $218-549. Phone 08 6160 6800.'],
         'http://www.hougoumonthotel.com/', 'Book direct'),
        ('Nature', 'Four options to finish on',
         ['Bathers Beach - immediately by the hotel.',
          'Point Walter and Blackwall Reach, Bicton - Swan River sand spit, an important '
          'waterbird feeding and resting site.',
          'Swan River Walk Trail - a 10 km loop, described in its listing as walkable or '
          'wheelable.',
          'Reabold Hill Scenic Lookout - a 200 m accessible Top Trail, the highest natural '
          'point on the Swan Coastal Plain.'],
         None, None),
    ])

# =========================================================
# 5. NO FAST FOOD
# =========================================================
doc.add_heading('5. On the "No Fast Food" Requirement', level=1)
para('There is no fast-food flag in ATDW to filter out. Food and Drink listings can only ever '
     'be bars, breweries and distilleries, restaurants and cafes, cooking schools, produce, or '
     'wineries - six categories, none of which is fast food. Every venue in this itinerary is a '
     'pub, brewery, cafe or restaurant. The requirement is therefore satisfied in substance, by '
     'venue type, rather than by an explicit exclusion.', size=10)

# =========================================================
# 6. BEFORE YOU GO
# =========================================================
doc.add_heading('6. Before You Go', level=1)
for b in [
    'Map the Nullarbor chargers in PlugShare or Chargefox. Nothing else in this plan is as '
    'load-bearing.',
    'Phone the Nullarbor roadhouses about wheelchair access. It is not recorded anywhere that '
    'can be checked.',
    'Confirm accessible-room rates, not property rates, at Mildura, Kalgoorlie and Fremantle. '
    'All three sit at the top of the band, so the accessible room may price above it.',
    'Carry food for the Ceduna to Kalgoorlie stretch. Both ends of it have no hamburger option '
    'at all.',
]:
    para(b, style='List Number', size=10, space_after=4)

doc.add_page_break()

# =========================================================
# APPENDIX A
# =========================================================
doc.add_heading('Appendix A. How This Was Built: Steps with the MCP Server', level=1)
para('All listing evidence in this itinerary came from the ATDW pilot MCP server. This appendix '
     'records the sequence of steps, what the data could and could not verify, the errors and '
     'workarounds encountered, and the runtime. It is included because the gaps are as '
     'informative as the results.', size=10, italic=True, space_after=10)

table(['Item', 'Value'],
      [['MCP server', 'atdw-pilot, version 0.9.0-dev.1 (schema 0.9.0)'],
       ['Tools used', 'get_atdw_capabilities, discover_atdw, get_product_details'],
       ['Taxonomy version', 'atdw-2026-09-04.1'],
       ['Domain schema', 'atdw-domain-2026-09-06.1'],
       ['Alias version', 'atdw-language-2026-09-07.1'],
       ['Provider', 'ATLAS adapter 0.5 (atlas-2026-09-04.1)'],
       ['Verification depth',
        'DISCOVERY_MATCH for searches; PROFILE_VERIFIED for detail lookups']],
      widths=[1.6, 4.3])

# A.1
doc.add_heading('A.1  Step one: capability discovery', level=2)
para('Before any searching, get_atdw_capabilities was used to establish what the vocabulary can '
     'actually express. It reports 11 Categories, 122 Classifications, 1,061 Attributes, 96 '
     'Accessibility concepts, 43 product tags, 72 service tags, 39 attribute types and 85 '
     'winery concepts.', size=10, space_after=8)
para('Each of the six requirements was then probed individually against that vocabulary, to '
     'determine which were filterable and which were not:', size=10, space_after=8)

table(['Requirement', 'Resolvable?', 'What was found'],
      [['Wheelchair access', 'Yes',
        'Accessibility concept WHEELCHAIR, "Caters for people who use a wheelchair." Product '
        'scope. Operator-declared, not a universal guarantee.'],
       ['Hamburgers', 'Yes',
        'Cuisine concept HAMBURGERS. Product scope, Food and Drink only.'],
       ['Gluten free', 'Yes',
        'Cuisine concept GLUTEFREE, "Gluten Free Available." A structured cuisine option, not '
        'an allergen-safety certification.'],
       ['No fast food', 'No',
        'Food and Drink has exactly six Classifications: bars; breweries and distilleries; '
        'restaurants and cafes; cooking schools; produce; wineries. There is no fast-food value '
        'to exclude.'],
       ['EV charging', 'No',
        'Probing "charging station" returns only a wheelchair or scooter charging point. EV '
        'charging is absent from the taxonomy.'],
       ['Eco-friendly', 'No',
        'Concept probes for "eco-friendly", "sustainable" and "environment" each returned zero '
        'concepts. A sustainabilityScore field exists on listings but was empty on every one '
        'retrieved.'],
       ['Price band $300-400', 'Partially',
        'No price parameter exists in the discovery search. Price can only be read from a full '
        'profile, one listing at a time, after retrieval.'],
       ['Routing / distances', 'No',
        'Explicitly listed as unsupported. Radius search is straight-line from a point, not '
        'driving distance or route containment.']],
      widths=[1.25, 0.85, 3.8])

# A.2
doc.add_heading('A.2  Step two: accommodation, per stop', level=2)
para('For each candidate overnight town, discover_atdw was called with category Accommodation '
     'and wheelchair access as a hard requirement. Location was expressed three ways depending '
     'on what the server would resolve: by locality name, by postcode and state, or by '
     'coordinates with an explicit radius.', size=10, space_after=6)
para('Because price is not filterable, qualifying properties were then passed individually to '
     'get_product_details to read their indicative rates and booking links. This two-stage '
     'pattern - filter on what is filterable, then verify the rest per listing - was the shape '
     'of most of the work.', size=10, space_after=6)
para('Notable results: Adelaide returned 26 candidates, of which 13 qualified on wheelchair '
     'access. Port Augusta returned none. Norseman returned a single accommodation listing with '
     'no wheelchair attribute recorded.', size=10)

# A.3
doc.add_heading('A.3  Step three: restaurants, per stop', level=2)
para('discover_atdw was called with category Food and Drink and two hard requirements on the '
     'same listing - Hamburgers and Gluten Free Available. Where a town returned nothing, the '
     'search was re-run as a coordinate search with a widening radius, up to 400 km.',
     size=10, space_after=6)
para('Three towns returned nothing at any radius tried: Goondiwindi (nothing within 200 km on '
     'route), Ceduna (nothing within 400 km), and Kalgoorlie (nothing within 200 km). Those are '
     'genuine coverage gaps, not search failures, and they are reported as such in the '
     'itinerary rather than being filled with a weaker match.', size=10)

# A.4
doc.add_heading('A.4  Step four: eco-friendly activities, by proxy', level=2)
para('Since no eco or sustainability concept resolves, a substitute was constructed and is '
     'labelled as one throughout: category Attraction, with Classifications "National Parks and '
     'Reserves" or "Natural Attractions" (matching either), run as a coordinate-and-radius '
     'search at each overnight stop.', size=10, space_after=6)
para('Qualifying counts per stop: Goondiwindi 15, Dubbo 54, Mildura 29, Ceduna and the '
     'Nullarbor 42, the Goldfields 14, Fremantle 98, Adelaide 108. Results were then filtered '
     'by hand for genuine nature relevance - see A.6.', size=10)

# A.5
doc.add_heading('A.5  Errors and workarounds', level=2)
table(['What happened', 'Resolution'],
      [['MCP error -32602, "Invalid input at location" - twice. radiusKm was being passed '
        'nested inside the location object.',
        'radiusKm is a top-level parameter, a sibling of location, not a member of it. The '
        'coordinate form of location accepts latitude and longitude only. Fixed by reading the '
        'actual input schema rather than guessing.'],
       ['get_atdw_capabilities rejected an unrecognised key, "topic".',
        'That parameter does not exist. The tool accepts only category, concept, limit and '
        'offset.'],
       ['UNSUPPORTED_CAPABILITY: unknown Classification "Botanical Gardens", and again for '
        '"Walking Trails". Retrieval state came back as not_attempted.',
        'One unrecognised Classification label aborts the whole search before any inventory is '
        'looked at - it does not degrade gracefully. Both labels were dropped; "National Parks '
        'and Reserves" and "Natural Attractions" resolve exactly.'],
       ['INTERNAL_ERROR, marked non-retryable, twice, for Norseman WA searched by locality '
        'name.',
        'Worked around by searching postcode 6443 with state WA instead. That returned partial '
        'retrieval with "search candidate limit of 1000 reached". This looks like a genuine '
        'geography-resolution defect and is worth logging in the findings log.'],
       ['Cloudflare 502 Bad Gateway from the origin, twice.',
        'Both retryable. Rather than idling, an unrelated query was run in the interim and the '
        'failed one retried afterwards, successfully.'],
       ['CLIENT_CAPACITY_EXCEEDED and timeouts when calls were issued in parallel.',
        'Batches were kept to three or fewer, and mostly run sequentially.'],
       ['get_product_details responses exceeded the tool output limit - between 94,000 and '
        '226,000 characters each - and were written to disk instead of returned.',
        'Rates, booking links and the sustainability field were extracted from the saved files '
        'with a short Python script.'],
       ['Passing limit: 1 to get_atdw_capabilities truncated the Classification list as well as '
        'the concept list, returning 1 of 14.',
        'Noted. Not pursued, as the two confirmed labels were sufficient.']],
      widths=[2.95, 2.95])

# A.6
doc.add_heading('A.6  Data-quality observations worth logging', level=2)
for b in [
    'No price parameter exists in the discovery search at all, so a price band can only be '
    'checked one listing at a time after retrieval. For a request like this one - a price '
    'constraint applied across nine towns - that is expensive, and it is the single biggest '
    'reason this took as many calls as it did.',
    'Adelaide\'s "Natural Attractions" results include a Pulteney Street street-art trail, and '
    'Fremantle\'s include the Round House, a colonial gaol. That Classification is being applied '
    'loosely by some contributors, which weakens it as a proxy for anything nature-based.',
    'sustainabilityScore is a real field on the listing schema but was empty on every one of the '
    'nine full profiles retrieved. If sustainability filtering is ever wanted, the field exists '
    'but is not populated.',
    'The wheelchair attribute sits at property level only. Room-level rate records were '
    'retrieved for one property (the Esplanade, six room services) and came back with no rates '
    'attached, so confirming an accessible room within a price band is not possible from this '
    'data.',
    'Locality-name resolution failed hard for at least one small town (Norseman) while postcode '
    'resolution succeeded, which suggests name resolution has gaps in remote areas - exactly '
    'where a route like this depends on it most.',
]:
    para(b, style='List Bullet', size=10, space_after=5)

# A.7
doc.add_heading('A.7  Runtime and call volume', level=2)
para('Measured from the session transcript, first to last timestamp.', size=10, space_after=8)
table(['Measure', 'Value'],
      [['Total runtime', '44 minutes'],
       ['Session window (UTC)', '2026-09-07 07:31:46 to 2026-09-07 08:15 (approx.)'],
       ['Total MCP calls', '58'],
       ['  discover_atdw', '35 - searches for accommodation, restaurants and attractions'],
       ['  get_atdw_capabilities', '13 - vocabulary and concept probes'],
       ['  get_product_details', '10 - full profiles, for rates and booking links'],
       ['Supporting local calls', '9 shell / Python (parsing oversized responses), 4 schema '
        'lookups'],
       ['Towns assessed', '13 - Redlands, Toowoomba, Dalby, Goondiwindi, Dubbo, Mildura, '
        'Renmark, Adelaide, Port Augusta, Ceduna, Norseman, Kalgoorlie, Fremantle'],
       ['Average', 'Roughly 1.3 MCP calls per minute, or about 4.5 calls per town assessed']],
      widths=[1.85, 4.05])
para('The call count is high relative to the output for one specific reason, given in A.6: '
     'price cannot be filtered in a search, so every candidate property had to be retrieved in '
     'full and read individually to test a single numeric condition.', size=10, italic=True)

doc.add_paragraph()
para('Provenance: all listing facts above were read from ATDW listing and profile records via '
     'the atdw-pilot MCP server on 7 September 2026. Recorded rates, opening hours and '
     'schedules are indicative and not live; none of them establish current availability.',
     size=8.5, italic=True)

out = (r'C:\Users\ToddBachelder\Documents\atdw-data-core-poc'
       r'\GP MCP Test - TB .docx')
doc.save(out)
print('SAVED:', out)
