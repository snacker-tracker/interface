"""Checking a built output against the contract (PRD.md §7).

Three layers, each reported as violations by file:
- shape: every file matches its document's schema
- layout: the files that must exist do, and no others
- invariants: rules across fields and files that a schema can't express
"""

import json
import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path, PurePosixPath
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from snacker.config import RECENT_SCANS_LIMIT, TOP_SCANS_LIMIT
from snacker.contract import (
    code_scans_path,
    index_path,
    locations_path,
    meta_path,
    product_path,
    scanners_path,
)
from snacker.schema import schema_errors

UTC_TIMESTAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
SHARE_ROUNDING = 0.00005
"""Shares are rounded to 4 places, so a list's shares can sum to just over 1."""


@dataclass(frozen=True)
class Violation:
    path: PurePosixPath
    """The file, relative to the data directory."""
    problem: str

    def __str__(self) -> str:
        return f"{self.path}: {self.problem}"


def document_of(path: PurePosixPath) -> str | None:
    """Which contract document a file under the data directory is, by its path; None if none."""
    match path.parts:
        case ("meta.json",):
            return "MetaFile"
        case ("locations.json",):
            return "LocationsFile"
        case ("index", "by-location", name) if name.endswith(".json"):
            return "IndexFile"
        case ("scanners", "by-location", name) if name.endswith(".json"):
            return "ScannersFile"
        case ("codes", _, "product.json"):
            return "ProductFile"
        case ("codes", _, "by-location", name) if name.endswith(".json"):
            return "CodeScansFile"
    return None


def contract_violations(
    data_dir: Path, *, recent_limit: int = RECENT_SCANS_LIMIT, top_limit: int = TOP_SCANS_LIMIT
) -> list[Violation]:
    """Every way the files under `data_dir` break the contract."""
    files, violations = _read_files(data_dir)
    output = _Output(files, recent_limit=recent_limit, top_limit=top_limit)
    return violations + list(output.layout_violations()) + list(output.invariant_violations())


def _read_files(data_dir: Path) -> tuple[dict[PurePosixPath, tuple[str, Any]], list[Violation]]:
    """Each file that parses and matches its document's schema, as (document, content) by path,
    plus a violation for every file that doesn't. Later checks only look at the good files."""
    files = {}
    violations = []
    for file in sorted(path for path in data_dir.rglob("*") if path.is_file()):
        path = PurePosixPath(file.relative_to(data_dir).as_posix())
        document = document_of(path)
        if document is None:
            violations.append(Violation(path, "not a file the contract describes"))
            continue
        try:
            content = json.loads(file.read_text())
        except json.JSONDecodeError as error:
            violations.append(Violation(path, f"not valid JSON: {error}"))
            continue
        errors = schema_errors(document, content)
        violations += [Violation(path, error) for error in errors]
        if not errors:
            files[path] = (document, content)
    return files, violations


class _Output:
    def __init__(self, files: dict[PurePosixPath, tuple[str, Any]], *, recent_limit: int, top_limit: int) -> None:
        self.files = files
        self.recent_limit = recent_limit
        self.top_limit = top_limit
        locations = files.get(locations_path())
        self.selectable = [entry["id"] for entry in locations[1]["locations"]] if locations else []

    def of(self, document: str) -> Iterator[tuple[PurePosixPath, Any]]:
        return ((path, content) for path, (kind, content) in self.files.items() if kind == document)

    # --- Layout ---

    def layout_violations(self) -> Iterator[Violation]:
        for path in (meta_path(), locations_path()):
            if path not in self.files:
                yield Violation(path, "missing")
        if self.files.get(locations_path()) and "all" not in self.selectable:
            yield Violation(locations_path(), "`all` isn't a selectable location")
        for location in self.selectable:
            for path in (index_path(location), scanners_path(location)):
                if path not in self.files:
                    yield Violation(path, f"missing: every selectable location has one ({location!r})")

        # Each file sits at the path its own content names, which pins the encoding.
        expected_paths: dict[str, Callable[[Any], PurePosixPath]] = {
            "IndexFile": lambda content: index_path(content["location"]),
            "ScannersFile": lambda content: scanners_path(content["location"]),
            "ProductFile": lambda content: product_path(content["code"]),
            "CodeScansFile": lambda content: code_scans_path(content["code"], content["location"]),
        }
        for path, (document, content) in self.files.items():
            if document in expected_paths and (expected := expected_paths[document](content)) != path:
                yield Violation(path, f"its content belongs at {expected}")
            if document in ("IndexFile", "ScannersFile", "CodeScansFile") and content["location"] not in self.selectable:
                yield Violation(path, f"location {content['location']!r} isn't selectable")

        # Every scanned code has a product file and a scans file for `all`.
        for path, content in self.of("CodeScansFile"):
            for required in (product_path(content["code"]), code_scans_path(content["code"], "all")):
                if required not in self.files:
                    yield Violation(path, f"{required} is missing")
        for path, content in self.of("ProductFile"):
            if code_scans_path(content["code"], "all") not in self.files:
                yield Violation(path, "a product file for a code that has no scans file for `all`")
        for path, code in self._codes_mentioned():
            if product_path(code) not in self.files:
                yield Violation(path, f"code {code!r} has no product file")

    def _codes_mentioned(self) -> Iterator[tuple[PurePosixPath, str]]:
        for path, content in self.of("IndexFile"):
            for row in content["recent"]:
                yield path, row["code"]
            for lists in (content["top_scans"], content["top_unknown_scans"]):
                for rows in lists.values():
                    for row in rows:
                        yield path, row["code"]
        for path, content in self.of("ScannersFile"):
            for scanner in content["scanners"]:
                if scanner["last_scan"]:
                    yield path, scanner["last_scan"]["code"]

    # --- Invariants ---

    def invariant_violations(self) -> Iterator[Violation]:
        for path, content in self.of("MetaFile"):
            yield from _utc(path, "generated_at", content["generated_at"])
        for path, content in self.of("IndexFile"):
            yield from self._daily(path, content["daily"])
            yield from self._recent(path, content["location"], content["recent"])
            yield from self._recent_length(path, content["daily"], content["recent"])
            yield from self._top_scans(path, "top_scans", content["top_scans"], unknown_only=False)
            yield from self._top_scans(path, "top_unknown_scans", content["top_unknown_scans"], unknown_only=True)
        for path, content in self.of("CodeScansFile"):
            yield from self._daily(path, content["daily"])
            yield from self._hourly(path, content["hourly"])
            yield from self._recent(path, content["location"], content["recent"])
            yield from self._recent_length(path, content["daily"], content["recent"])
            total = sum(day["count"] for day in content["daily"])
            if sum(hour["count"] for hour in content["hourly"]) != total:
                yield Violation(path, "hourly and daily counts add up to different totals")
            if total == 0:
                yield Violation(path, "written for a location where the code wasn't scanned")
            if any(row["code"] != content["code"] for row in content["recent"]):
                yield Violation(path, "recent lists scans of another code")
        for path, content in self.of("ScannersFile"):
            names = [scanner["name"] for scanner in content["scanners"]]
            if names != sorted(names) or len(set(names)) != len(names):
                yield Violation(path, "scanners aren't unique and ordered by name")
            for scanner in content["scanners"]:
                if not _within(scanner["location"], content["location"]):
                    yield Violation(path, f"scanner {scanner['name']!r} is at {scanner['location']!r}, outside this location")
                yield from _utc(path, f"{scanner['name']} last_seen", scanner["last_seen"])
                if last_scan := scanner["last_scan"]:
                    where = f"{scanner['name']} last_scan"
                    yield from _utc(path, where, last_scan["scanned_at"])
                    yield from _name_source(path, where, last_scan["product_name"], last_scan)

    def _daily(self, path: PurePosixPath, daily: list[Any]) -> Iterator[Violation]:
        try:
            dates = [date.fromisoformat(day["date"]) for day in daily]
        except ValueError as error:
            yield Violation(path, f"daily: {error}")
            return
        if any(later <= earlier for earlier, later in zip(dates, dates[1:])):
            yield Violation(path, "daily: dates aren't unique and oldest first")
        if any(day["count"] <= 0 for day in daily):
            yield Violation(path, "daily: lists a day without scans")

    def _hourly(self, path: PurePosixPath, hourly: list[Any]) -> Iterator[Violation]:
        if [hour["hour"] for hour in hourly] != list(range(24)):
            yield Violation(path, "hourly: isn't exactly hours 0 to 23 in order")
        if any(hour["count"] < 0 for hour in hourly):
            yield Violation(path, "hourly: a negative count")

    def _recent(self, path: PurePosixPath, location: str, recent: list[Any]) -> Iterator[Violation]:
        for index, row in enumerate(recent):
            where = f"recent/{index}"
            yield from _utc(path, f"{where}/scanned_at", row["scanned_at"])
            yield from _office_time(path, where, row)
            yield from _name_source(path, where, row["name"], row)
            if not _within(row["location"], location):
                yield Violation(path, f"{where}: scanned at {row['location']!r}, outside this location")
            if row["location"] not in self.selectable:
                yield Violation(path, f"{where}: location {row['location']!r} isn't selectable")
        moments = [row["scanned_at"] for row in recent]  # UTC with Z sorts as text
        if moments != sorted(moments, reverse=True):
            yield Violation(path, "recent: isn't newest first")

    def _recent_length(self, path: PurePosixPath, daily: list[Any], recent: list[Any]) -> Iterator[Violation]:
        total = sum(day["count"] for day in daily)
        if len(recent) != min(total, self.recent_limit):
            yield Violation(path, f"recent: lists {len(recent)} of {total} scans, limit {self.recent_limit}")

    def _top_scans(
        self, path: PurePosixPath, field: str, by_period: dict[str, list[Any]], *, unknown_only: bool
    ) -> Iterator[Violation]:
        for period, rows in by_period.items():
            where = f"{field}/{period}"
            counts = [row["count"] for row in rows]
            if len(rows) > self.top_limit:
                yield Violation(path, f"{where}: {len(rows)} codes, more than {self.top_limit}")
            if counts != sorted(counts, reverse=True) or any(count <= 0 for count in counts):
                yield Violation(path, f"{where}: counts aren't positive and most first")
            if len({row["code"] for row in rows}) != len(rows):
                yield Violation(path, f"{where}: a code is listed twice")
            if any(not 0 < row["share"] <= 1 for row in rows):
                yield Violation(path, f"{where}: a share outside (0, 1]")
            if sum(row["share"] for row in rows) > 1 + SHARE_ROUNDING * len(rows):
                yield Violation(path, f"{where}: shares add up to more than 1")
            if unknown_only and any(row["known"] for row in rows):
                yield Violation(path, f"{where}: lists a known product")
            for index, row in enumerate(rows):
                yield from _name_source(path, f"{where}/{index}", row["name"], row)


def _within(location: str, selected: str) -> bool:
    """Whether `location` is `selected` or beneath it, on whole segments."""
    return selected == "all" or location == selected or location.startswith(selected + ":")


def _name_source(path: PurePosixPath, where: str, name: str | None, row: dict[str, Any]) -> Iterator[Violation]:
    """A name has a source exactly when there is a name, and only a known product has an OpenFoodFacts name."""
    if name is None and row["name_source"] is not None:
        yield Violation(path, f"{where}: name_source is set but there's no name")
    if name is not None and row["name_source"] is None:
        yield Violation(path, f"{where}: name_source is null but the name isn't")
    if row["name_source"] == "openfoodfacts" and not row["known"]:
        yield Violation(path, f"{where}: an OpenFoodFacts name for a product OpenFoodFacts doesn't have")


def _utc(path: PurePosixPath, field: str, value: str) -> Iterator[Violation]:
    if not UTC_TIMESTAMP.fullmatch(value):
        yield Violation(path, f"{field}: {value!r} isn't a UTC time like 2026-10-19T12:00:00Z")
        return
    try:
        datetime.fromisoformat(value)
    except ValueError:
        yield Violation(path, f"{field}: {value!r} isn't a real time")


def _office_time(path: PurePosixPath, where: str, row: dict[str, Any]) -> Iterator[Violation]:
    """A scan row's office time is its UTC time, written with its office time zone's offset."""
    try:
        zone = ZoneInfo(row["office_time_zone"])
    except (ZoneInfoNotFoundError, ValueError):
        yield Violation(path, f"{where}: {row['office_time_zone']!r} isn't an IANA time zone")
        return
    try:
        scanned_at = datetime.fromisoformat(row["scanned_at"])
        office_time = datetime.fromisoformat(row["office_time"])
    except ValueError:
        yield Violation(path, f"{where}: office_time {row['office_time']!r} isn't an ISO 8601 time")
        return
    if office_time.tzinfo is None or office_time != scanned_at:
        yield Violation(path, f"{where}: office_time {row['office_time']!r} isn't the moment {row['scanned_at']}")
    elif office_time.utcoffset() != scanned_at.astimezone(zone).utcoffset():
        yield Violation(path, f"{where}: office_time {row['office_time']!r} isn't in {row['office_time_zone']}")
