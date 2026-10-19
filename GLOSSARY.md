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
What a code identifies, when the product catalogue knows it.
_Avoid_: item, snack (for the catalogue entry)

**Unknown product**:
A code with no matching product; its scans still count.

**Scan summary**:
What a set of scans amounts to: how many fell on each day in their office time zone, and which were the most recent.
_Avoid_: stats, aggregates, report

### Places and time

**Location**:
A colon-separated path naming where a scan happened, from broad to narrow (e.g. `thailand:bangkok:main-kitchen`). A location includes every location beneath it.
_Avoid_: site, office (when the path is meant), pantry (when the path is meant)

**Selectable location**:
A location someone can filter by: `all`, or any prefix of a location some scan came from.

**Office time zone**:
The time zone of the office a location belongs to; days and hours for its scans are counted in it.
_Avoid_: local timezone (ambiguous with the viewer's browser)

### Hardware

**Scanner**:
An internet-connected barcode reader placed at a location.
_Avoid_: device, reader

**Heartbeat**:
A periodic sign of life from a scanner, carrying its app version.
_Avoid_: ping, health check
