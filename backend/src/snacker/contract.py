"""The output contract: every static JSON file the build writes, its path and its shape.

This is the interface between the build and the frontend. Each file document and each
row it holds is defined here once; the rest of the backend fills them in. See PRD.md §7
for the rules on which files exist.
"""

from pathlib import PurePosixPath
from typing import Literal, TypedDict, get_args
from urllib.parse import quote

# --- Rows shared between files ---


class DailyCount(TypedDict):
    date: str
    """A date in the office time zone, e.g. "2026-10-16"."""
    count: int


class HourlyCount(TypedDict):
    hour: int
    """0-23, in the office time zone."""
    count: int


class ScanRow(TypedDict):
    code: str
    name: str | None
    """The product's name; null for an unknown product."""
    brands: str | None
    known: bool
    """Whether OpenFoodFacts has the product; it may have it without a name."""
    location: str
    scanned_at: str
    """UTC, e.g. "2026-09-23T06:26:00Z"."""
    office_time: str
    """The same moment in the office time zone, e.g. "2026-09-23T13:26:00+07:00"."""
    office_time_zone: str
    """IANA name, e.g. "Asia/Bangkok"."""


class TopScan(TypedDict):
    code: str
    name: str | None
    brands: str | None
    known: bool
    """Whether OpenFoodFacts has the product; unknown products are flagged in the UI."""
    count: int
    share: float
    """This code's fraction of all scans in the period, e.g. 0.25."""


# Period IDs contain hyphens, so this TypedDict uses the functional form.
TopScansByPeriod = TypedDict("TopScansByPeriod", {
    "today": list[TopScan],
    "this-work-week": list[TopScan],
    "last-7-days": list[TopScan],
    "this-month": list[TopScan],
    "last-30-days": list[TopScan],
    "this-year": list[TopScan],
    "last-365-days": list[TopScan],
    "all-time": list[TopScan],
})
"""Top scans for every period, keyed by period ID."""

Period = Literal[
    "today",
    "this-work-week",
    "last-7-days",
    "this-month",
    "last-30-days",
    "this-year",
    "last-365-days",
    "all-time",
]
"""A period top scans are ranked over (see GLOSSARY.md, Period)."""

PERIODS: tuple[Period, ...] = get_args(Period)
"""Every period, in display order; the keys of TopScansByPeriod, in the same order."""


class Product(TypedDict):
    """What a code page shows about a product (PRD R5)."""

    name: str | None
    brands: str | None
    quantity: str | None
    categories: list[str]
    image_url: str | None
    """OpenFoodFacts's front image (docs/adr/0001)."""
    off_url: str
    """The product's page on OpenFoodFacts."""


class LastScan(TypedDict):
    scanned_at: str
    """UTC, e.g. "2026-10-16T10:33:45Z"."""
    code: str
    product_name: str | None
    """Null for an unknown product."""
    known: bool
    """Whether OpenFoodFacts has the product."""


class ScannerStatus(TypedDict):
    name: str
    """The scanner's name, e.g. "rpi-pico-w-01"."""
    location: str
    """Where its latest heartbeat said it was."""
    app_version: str
    """From its latest heartbeat."""
    last_seen: str
    """UTC time of its latest heartbeat, e.g. "2026-10-19T09:45:47Z"."""
    last_scan: LastScan | None
    """The latest scan sent with its API key (docs/adr/0002); null if it has sent none."""


class SelectableLocation(TypedDict):
    id: str
    """`all`, or a location path such as "thailand:bangkok"."""


# --- Files ---

ContractVersion = Literal[2]
CONTRACT_VERSION: ContractVersion = 2
"""The version of this contract, written to meta.json so the frontend can tell when the data
it was built for and the data it is served are out of step.

Bump it (here and in ContractVersion) on any change that could break a reader of the old
contract: a field removed, renamed, retyped or newly nullable, a file moved, or a rule in
PRD.md §7 tightened or relaxed. Adding a whole new file is not breaking. Adding a field is,
because the schema rejects fields it doesn't list. Then regenerate the schema and the
frontend's types, and deploy both together.
"""



class MetaFile(TypedDict):
    generated_at: str
    """UTC time the data was built; every top-scans period ends then."""
    contract_version: ContractVersion
    """The version of this contract the data was built to (CONTRACT_VERSION)."""


class LocationsFile(TypedDict):
    locations: list[SelectableLocation]
    """`all`, then every prefix of every scanned location, in path order."""


class IndexFile(TypedDict):
    """The index page for one selectable location."""

    location: str
    top_scans: TopScansByPeriod
    top_unknown_scans: TopScansByPeriod
    """Top scans of unknown products only; shares are still of all scans in the period."""
    daily: list[DailyCount]
    """Scans per office date, oldest first; days without scans are left out."""
    recent: list[ScanRow]
    """The most recent scans, newest first."""


class ScannersFile(TypedDict):
    """Every scanner within one selectable location, ordered by name."""

    location: str
    scanners: list[ScannerStatus]


class ProductFile(TypedDict):
    """A code's product; written for every scanned code, whatever the location."""

    code: str
    product: Product | None
    """Null for an unknown product."""


class CodeScansFile(TypedDict):
    """One code's scans within one selectable location; written only where it was scanned."""

    code: str
    location: str
    daily: list[DailyCount]
    """Scans per office date, oldest first; days without scans are left out."""
    hourly: list[HourlyCount]
    """Scans per office hour of the day: always 24 entries, 0 to 23."""
    recent: list[ScanRow]
    """The most recent scans, newest first."""


ContractFile = MetaFile | LocationsFile | IndexFile | ScannersFile | ProductFile | CodeScansFile
"""Any file the build writes."""


# --- Paths, relative to the output's data directory ---


def meta_path() -> PurePosixPath:
    return PurePosixPath("meta.json")


def locations_path() -> PurePosixPath:
    return PurePosixPath("locations.json")


def index_path(location: str) -> PurePosixPath:
    return PurePosixPath("index", "by-location", f"{path_segment(location)}.json")


def scanners_path(location: str) -> PurePosixPath:
    return PurePosixPath("scanners", "by-location", f"{path_segment(location)}.json")


def product_path(code: str) -> PurePosixPath:
    return PurePosixPath("codes", path_segment(code), "product.json")


def code_scans_path(code: str, location: str) -> PurePosixPath:
    return PurePosixPath("codes", path_segment(code), "by-location", f"{path_segment(location)}.json")


def path_segment(value: str) -> str:
    """A location or code as a file name: percent-encoded like JavaScript's
    encodeURIComponent, except that `:` stays readable (`thailand:bangkok`)."""
    return quote(value, safe="!*'():")
