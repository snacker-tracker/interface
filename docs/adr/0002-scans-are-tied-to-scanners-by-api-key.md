# Scans are tied to scanners by API key

A scan event carries only a code and a location; it doesn't say which scanner sent it. Heartbeats do name their scanner, and both kinds of event carry the API key the scanner authenticated with. We tie a scan to the scanner whose heartbeats use the same API key. This is how the scanners page finds each scanner's last scan.

This only works if **every scanner has its own API key**. Nothing in the code enforces that: it is a setup rule for whoever provisions a new scanner. If two scanners share a key, each shows the other's scans as its own. Backfill scans have no API key and are never tied to a scanner.

## Considered options

- **By location:** take the latest scan at the scanner's location. This was rejected because two scanners in one pantry would share a last scan, and backfill scans at broader locations (`thailand:bangkok`) would never match.
- **Scanner name in the scan payload:** have the firmware send its name with each scan. This is the most accurate option and the better long-term fix, but it needs a firmware change outside this repo. If it happens, prefer the name and fall back to the API key for older scans.
