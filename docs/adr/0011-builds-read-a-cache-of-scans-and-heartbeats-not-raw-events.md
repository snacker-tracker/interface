# Builds read a cache of scans and heartbeats, not every raw event

Every build used to download every raw event: about 12,600 small objects every 15 minutes, almost all of them heartbeats. That cost around $0.50 a day in S3 GETs, and the cost grew with each new heartbeat.

The build now keeps a cache of two Parquet files in the working bucket:
- **Scans:** every normalised scan, each row with the raw key it came from.
- **Heartbeats:** each scanner's latest heartbeat. This is all the scanners pages use, since a scanner is at the location its latest heartbeat names.

Each cache holds a watermark: the newest `LastModified` of any raw file it has loaded. Each build reads scans and heartbeats the same way:
1. List from the day folder before the watermark.
2. Download only files modified after the watermark minus 15 minutes.

On a typical build that is a handful of heartbeats and perhaps a couple of scans.

The margin exists because Firehose names each file after its buffer's start time but writes it when the buffer closes. A file can therefore land after a later-named one, so an exact key cursor could skip it for good. Re-reading the overlap does no harm:
- **Heartbeats:** only the latest heartbeat per scanner is kept.
- **Scans:** rows from a raw key the cache already holds are replaced, not added, so no scan is counted twice.

A watermark never sees a deleted raw file. A deleted scan file's scans stay in the cache until the next rebuild. A deleted heartbeat file matters only if it held a scanner's latest heartbeat. To remove scans, delete the raw file and then the cache.

The cache records the code version that wrote it: the image digest in Lambda, or the git commit for the CLI, where a dirty tree never matches. A build from any other version rebuilds the cache from raw, which costs one full read per deploy. That way a change to the normalisers can't leave stale rows, and nobody has to remember to bump a version. The cache is always derivable from raw, so overlapping builds need no locking: whichever write lands last is correct, or the next build corrects it. Only the build writes the cache. The extract function reads it, and brings it up to date in memory when it is missing or stale.

## Considered options

- **Delta Lake:** rejected. Each append adds a data file and a log entry, which brings back the many-small-objects problem and needs compaction. It also needs S3 write locking and a large extra dependency, and it protects transactions on data that can always be rebuilt. Rewriting a file of a few hundred rows costs one PUT.
- **Appending to the Parquet files:** not possible. Parquet ends in a footer and S3 objects are immutable, so each build rewrites both files whole.
