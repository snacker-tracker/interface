# Checks are blocking, and run on the value before it is stored

An asset's checks run in its own Lambda, on the value its function returned, before the IO manager stores it. A failed check fails the run. Nothing is stored, so a value that failed a check can never become an asset's latest materialization, and no later run can skip to it.

A rule that spans several assets is a check on an asset that depends on all of them. For a site whose files must agree with each other, that is an asset holding the whole tree, whose IO manager publishes it. So a tree that breaks the rule is never published.

## Considered options

- **Checks as their own steps,** which can load several assets after they are stored. Rejected: by then the values are already the latest materializations, so a later run could skip to a value that failed its check.
- **Non-blocking checks,** which only report. Left out until something needs them.
