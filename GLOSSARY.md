# Snacker Tracker

Tracking which snacks are taken from office pantries, as recorded by barcode scanners, so purchasing can follow what people actually eat.

## Language

### Scans

**Scan**:
One reading of a code by a scanner, meaning one item was taken from a pantry.
_Avoid_: event, read, take

**Code**:
The value a scanner read: usually a product barcode, but sometimes a QR-code URL or a short internal code.
_Avoid_: UPC, EAN, barcode (when the value isn't necessarily one)

**Product**:
What a code identifies, as described by OpenFoodFacts or the Snacker archive. Where both describe it, OpenFoodFacts is preferred and the archive fills what it lacks.
_Avoid_: item, snack (for the catalogue entry)

**Snacker archive**:
Product records kept by the previous Snacker Tracker, pulled from shop websites or entered by hand. Frozen: nothing is added or corrected. A second, less trusted source of product details than OpenFoodFacts.
_Avoid_: legacy data, historical data, old codes

**Scanned product**:
A scanned code together with what the scan lists show of its product: its name and where the name came from, its brands, whether OpenFoodFacts has it, and its Nutri-Score. An unknown product is a scanned product too, just with little or nothing known.
_Avoid_: listed product, product summary

**Unknown product**:
A code OpenFoodFacts doesn't have, whether or not the Snacker archive does; worth adding to OpenFoodFacts. Its scans still count.

**Grade**:
A product's rating on one of OpenFoodFacts's scales: its Nutri-Score, NOVA group or Green-Score. Only OpenFoodFacts grades products; a product without a grade on a scale simply has none there.
_Avoid_: score (for the letter or group shown), rating

**Nutri-Score**:
Nutritional quality, graded A (best) to E (worst).

**NOVA group**:
How processed a food is, from 1 (unprocessed or minimally processed) to 4 (ultra-processed).

**Green-Score**:
Environmental impact, graded A+ (lowest) to F (highest). OpenFoodFacts's former Eco-Score.
_Avoid_: Eco-Score, environmental score

**Scan summary**:
What a set of scans amounts to: how many fell on each day and in each hour of the day in their office time zone, and which were the most recent.
_Avoid_: stats, aggregates, report

**Top scans**:
The codes scanned most often within a period, most first, unknown products included. It ranks codes, not individual scans.
_Avoid_: most scanned, popular, top items, best sellers, favourites

**Healthiest and least healthy products**:
The products with a Nutri-Score scanned within a period, split into two lists that never share a product: the healthiest are best grade first, and the least healthy are worst grade first. Within a grade, the most scanned come first.
_Avoid_: healthiest snacks, health ranking

**Nutri-Score distribution**:
How many scans within a period were of products of each Nutri-Score grade, A to E. Each scan counts, so a product scanned ten times adds ten to its grade. Scans of products without a Nutri-Score aren't in it.
_Avoid_: histogram (for the counts rather than the chart), Nutri-Score breakdown, health mix

**Period**:
A span of time ending when the data was built: calendar-aligned in each scan's office time zone (today, this work week from Monday, this month, this year), rolling (the last 7, 30 or 365 days), or all time.
_Avoid_: range, window, time-line (for this concept)

### Places and time

**Location**:
A colon-separated path naming where a scan happened, from broad to narrow (e.g. `thailand:bangkok:main-kitchen`). A location includes every location beneath it.
_Avoid_: site, office (when the path is meant), pantry (when the path is meant)

**Selectable location**:
A location someone can filter by: `all`, or any prefix of a location some scan came from.

**Office time zone**:
The time zone of the office a location belongs to; days and hours for its scans are counted in it.
_Avoid_: local timezone (ambiguous with the viewer's browser)

**Office time**:
When a scan happened, as a clock in its office time zone would show it.
_Avoid_: local time

### Hardware

**Scanner**:
An internet-connected barcode scanner placed at a location. A scanner is known once it has sent a heartbeat. Its scans are the ones sent with the same API key as its heartbeats, so each scanner has its own key.
_Avoid_: device, reader

**Offline**:
A scanner whose latest heartbeat is more than an hour old. Scans don't count: a working scanner can go a weekend without one.
_Avoid_: down, dead, inactive

**Heartbeat**:
A periodic sign of life from a scanner, carrying its app version.
_Avoid_: ping, health check

### Site usage

**Interaction**:
One recorded thing a visitor did on the site, such as viewing a page or choosing a period. Not a scan: the two are never mixed.
_Avoid_: event, hit, tracked event

**Page view**:
An interaction recording that a visitor opened a page: the index, a code's page or the scanners page. Choosing a location or period on the page they're already on isn't a page view.
_Avoid_: screen, screen view

**Visitor**:
A browser the site recognises across visits by a random identifier it was given. One person on two browsers is two visitors; it says nothing about who they are.
_Avoid_: user, person, customer

**Visit**:
A visitor's run of interactions with no gap longer than 30 minutes; a longer gap starts a new visit, even in the same tab.
_Avoid_: session
