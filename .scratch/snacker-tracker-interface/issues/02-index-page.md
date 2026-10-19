# 02: Index page

**What to build:** An office-goer opens the interface at `/` and sees a bar chart of scans per day across all history, and can brush a range on it to zoom in. Below it is a list of the 25 most recent scans. Both read the static index file for `all` produced by ticket 01. This ticket sets up the frontend.

**Blocked by:** 01 (Build pipeline skeleton).

**Status:** ready-for-agent

- [ ] The frontend uses Vite, React, TypeScript and React Router, with Node 22 LTS pinned.
- [ ] In development, Vite serves the build output folder as static files, so the page loads real built data.
- [ ] The `/` route fetches the `all` index file and shows a Vega-Lite (via react-vega) daily bar chart across all history with brush-to-zoom.
- [ ] The page lists the 25 most recent scans, newest first, with the time and location of each scan and its raw code.
- [ ] Loading and fetch-error states are handled without crashing the page.
- [ ] The README or AGENTS.md documents how to build the data and run the frontend locally.
