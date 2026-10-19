# 12: Gather the output contract into one backend module

**What to build:** A pure prefactor. Everything the build promises the frontend gets a single typed definition in one backend module: the six file documents (meta, locations, index, scanners, product, code scans), the rows they share (scan row, daily count, hourly count, top scan, product, scanner status, last scan), and the rule that turns a code or location into a file name. Today the rows are TypedDicts scattered across the summary, products and heartbeats modules, and the file-level documents are untyped dicts inside the build. After this, the build writes typed documents, so mypy checks the whole output shape. The JSON written is byte-for-byte unchanged. Requested 2026-10-19.

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

- [ ] One module defines every file document and every row type that appears in the static JSON, with the docstrings that explain each field (UTC vs office time, null meaning unknown product, 0-23 hours, share as a fraction).
- [ ] The file-name encoding rule (percent-encoded like `encodeURIComponent`, `:` kept literal) and the path of each file type live in the same module.
- [ ] The build constructs each file as its typed document; no file content is built as an untyped dict.
- [ ] A fixture build writes exactly the same files and contents as before (existing build tests pass unchanged).
- [ ] mypy strict passes.
