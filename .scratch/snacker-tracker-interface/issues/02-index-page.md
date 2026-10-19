# 02: Index page

**What to build:** An office-goer opens the interface at `/` and sees a bar chart of scans per day across all history, and can brush a range on it to zoom in. Below it is a list of the 25 most recent scans. Both read the static index file for `all` produced by ticket 01. This ticket sets up the frontend.

**Blocked by:** 01 (Build pipeline skeleton).

**Status:** resolved

- [x] The frontend uses Vite, React, TypeScript and React Router, with Node 22 LTS pinned.
- [x] In development, Vite serves the build output folder as static files, so the page loads real built data.
- [x] The `/` route fetches the `all` index file and shows a Vega-Lite (via react-vega) daily bar chart across all history with brush-to-zoom.
- [x] The page lists the 25 most recent scans, newest first, with the time and location of each scan and its raw code.
- [x] Loading and fetch-error states are handled without crashing the page.
- [x] The README or AGENTS.md documents how to build the data and run the frontend locally.

## Comments

- 2026-10-19: Implemented. The page is Vite 8, React 19, TypeScript, React Router 8 and react-vega 8, with Node 22 pinned in `.nvmrc` and `engines`. Vite serves `public-data/` as its public directory. The chart is a detail view over an overview view; brushing the overview filters the detail view and rescales its y-axis. It has light and dark colour steps, and a table view of the daily counts sits under the chart. Rounded bar ends were dropped because Vega-Lite's per-bar corner clipping broke the brush zoom. There's no browser on the dev machine, so the real spec was rendered to PNG in Node (full range, zoomed, dark, 340px wide). The DOM page wasn't screenshotted: double-click-to-reset and the container width still need one check in a real browser. The scan list shows UTC until ticket 04.
