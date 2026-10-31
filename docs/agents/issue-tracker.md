# Issue tracker: GitHub

Issues and specs for this repo live as GitHub issues. Use the `gh` CLI for all operations.

## Conventions

- **Create an issue**: `gh issue create --title "..." --body "..."`. Use a heredoc for multi-line bodies.
- **Read an issue**: `gh issue view <number> --json number,title,body,labels,comments`.
- **List issues**: `gh issue list --state open --json number,title,body,labels,comments --jq '[.[] | {number, title, body, labels: [.labels[].name], comments: [.comments[].body]}]'` with appropriate `--label` and `--state` filters.
- **Make an issue a sub-issue of a parent**: `gh issue create --parent <parent> ...`, or `gh issue edit <parent> --add-sub-issue <child>` afterwards (`gh` 2.94+). Older `gh`: `gh api --method POST repos/<owner>/<repo>/issues/<parent>/sub_issues -F sub_issue_id=<child-db-id>` (database id, as in **Blocking** below). Without sub-issues, put `Part of #<parent>` at the top of the child body.
- **Comment on an issue**: `gh issue comment <number> --body "..."`
- **Apply / remove labels**: `gh issue edit <number> --add-label "..."` / `--remove-label "..."`
- **Close**: `gh issue close <number> --comment "..."`

Infer the repo from `git remote -v` (`snacker-tracker/interface`); `gh` does this automatically when run inside a clone. If `gh` isn't signed in, use the token in the root `.env` (git-ignored): `export GH_TOKEN="$(grep -E '^GITHUB_TOKEN=' .env | cut -d= -f2-)"`. Never print it.

## This repo's conventions

- **Features:** each feature's issues carry a `feature:<slug>` label, such as `feature:aws-deployment`. A feature's spec is an issue labelled `spec` as well.
- **Titles:** `[<slug> NN] <title>` for a ticket and `[<slug>] Spec: <title>` for a spec. `NN` numbers the tickets within a feature, from `01`.
- **Status:** an issue's open or closed state, plus the triage labels in `triage-labels.md`. There is no `Status:` line in the body. A superseded ticket is closed as not planned, with a comment naming the issue that replaced it.
- **Comments:** progress notes and results go in issue comments, not in edits to the body.

## Pull requests as a triage surface

**PRs as a request surface: no.** _(Set to `yes` if this repo treats external PRs as feature requests; `/triage` reads this flag.)_

When set to `yes`, PRs run through the same labels and states as issues, using the `gh pr` equivalents:

- **Read a PR**: `gh pr view <number> --comments` and `gh pr diff <number>` for the diff.
- **List external PRs for triage**: `gh api --paginate 'repos/{owner}/{repo}/pulls?state=open' --jq '.[] | select(.author_association | IN("OWNER","MEMBER","COLLABORATOR") | not) | {number, title, author: .user.login, author_association, labels: [.labels[].name]}'`.
- **Comment / label / close**: `gh pr comment`, `gh pr edit --add-label`/`--remove-label`, `gh pr close`.

GitHub shares one number space across issues and PRs, so a bare `#42` may be either: resolve with `gh pr view 42` and fall back to `gh issue view 42`.

## When a skill says "publish to the issue tracker"

Create a GitHub issue.

## When a skill says "fetch the relevant ticket"

Read it as in **Read an issue** above.

## Wayfinding operations

Used by `/wayfinder`. The **map** is a single issue with **child** issues as tickets.

- **Map**: a single issue labelled `wayfinder:map`, holding the Notes / Decisions-so-far / Fog body. `gh issue create --label wayfinder:map`.
- **Child ticket**: an issue linked to the map as a GitHub sub-issue (see **Make an issue a sub-issue of a parent**). Where sub-issues aren't enabled, add the child to a task list in the map body and put `Part of #<map>` at the top of the child body. Labels: `wayfinder:<type>` (`research`/`prototype`/`grilling`/`task`). Once claimed, the ticket is assigned to the driving dev.
- **Blocking**: GitHub's **native issue dependencies**, the canonical, UI-visible representation. Add an edge with `gh api --method POST repos/<owner>/<repo>/issues/<child>/dependencies/blocked_by -F issue_id=<blocker-db-id>`, where `<blocker-db-id>` is the blocker's numeric **database id** (`gh api repos/<owner>/<repo>/issues/<n> --jq .id`, _not_ the `#number` or `node_id`). GitHub reports `issue_dependencies_summary.blocked_by` (open blockers only, the live gate). Where dependencies aren't available, fall back to a `Blocked by: #<n>, #<n>` line at the top of the child body. A ticket is unblocked when every blocker is closed.
- **Frontier query**: list the map's open children (`gh issue list --state open`, scoped to the map's sub-issues / task list), drop any with an open blocker (`issue_dependencies_summary.blocked_by > 0`, or an open issue in the `Blocked by` line) or an assignee; first in map order wins.
- **Claim**: `gh issue edit <n> --add-assignee @me`, the session's first write.
- **Resolve**: `gh issue comment <n> --body "<answer>"`, then `gh issue close <n>`, then append a context pointer (gist + link) to the map's Decisions-so-far.

## Local issues, imported later

Issues lived as markdown under `.scratch/<feature>/` twice, and were imported as they stood each time. That's why some commits, ADRs and issue bodies say "ticket 06".

- **Until 2026-10-21.** Their imported issues are in the first table below.
- **From 2026-10-30 to 2026-10-31**, for the stepdag experiment (#82 to #125). Each feature's `decisions.md` became a comment on its spec, and the tickets' dated comments became issue comments. Their imported issues are in the second table below.

Until 2026-10-21:

| Feature | Local | GitHub |
| --- | --- | --- |
| `snacker-tracker-interface` | spec | #2 |
| `snacker-tracker-interface` | 01 | #3 |
| `snacker-tracker-interface` | 02 | #4 |
| `snacker-tracker-interface` | 02a | #5 |
| `snacker-tracker-interface` | 03 | #6 |
| `snacker-tracker-interface` | 04 | #7 |
| `snacker-tracker-interface` | 05 | #8 |
| `snacker-tracker-interface` | 06 | #9 |
| `snacker-tracker-interface` | 07 | #10 |
| `snacker-tracker-interface` | 08 | #11 |
| `snacker-tracker-interface` | 09 | #12 |
| `snacker-tracker-interface` | 10 | #13 |
| `snacker-tracker-interface` | 11 | #14 |
| `snacker-tracker-interface` | 12 | #15 |
| `snacker-tracker-interface` | 13 | #16 |
| `snacker-tracker-interface` | 14 | #17 |
| `snacker-tracker-interface` | 15 | #18 |
| `snacker-tracker-interface` | 16 | #19 |
| `snacker-tracker-interface` | 17 | #20 |
| `snacker-tracker-interface` | 18 | #21 |
| `snacker-tracker-interface` | 19 | #22 |
| `snacker-tracker-interface` | 20 | #23 |
| `snacker-tracker-interface` | 21 | #24 |
| `snacker-tracker-interface` | 22 | #25 |
| `snacker-tracker-interface` | 23 | #26 |
| `snacker-tracker-interface` | 24 | #27 |
| `snacker-tracker-interface` | 25 | #28 |
| `snacker-tracker-interface` | 26 | #29 |
| `snacker-tracker-interface` | 27 | #30 |
| `aws-deployment` | 01 | #31 |
| `aws-deployment` | 02 | #32 |
| `aws-deployment` | 03 | #33 |
| `aws-deployment` | 04 | #34 |
| `aws-deployment` | 05 | #35 |
| `aws-deployment` | 06 | #36 |
| `aws-deployment` | 07 | #37 |
| `aws-deployment` | 08 | #38 |

From 2026-10-30 to 2026-10-31:

| Feature | Local | GitHub |
| --- | --- | --- |
| `stepdag` | spec | #82 |
| `stepdag` | 01 | #83 |
| `stepdag` | 02 | #84 |
| `stepdag` | 03 | #85 |
| `stepdag` | 04 | #86 |
| `stepdag` | 05 | #87 |
| `stepdag` | 06 | #88 |
| `stepdag` | 07 | #89 |
| `stepdag` | 08 | #90 |
| `stepdag-scans` | spec | #91 |
| `stepdag-scans` | 01 | #92 |
| `stepdag-scans` | 02 | #93 |
| `stepdag-scans` | 03 | #94 |
| `stepdag-scans` | 04 | #95 |
| `stepdag-scans` | 05 | #96 |
| `stepdag-scans` | 06 | #97 |
| `stepdag-scans-products` | spec | #98 |
| `stepdag-scans-products` | 01 | #99 |
| `stepdag-scans-products` | 02 | #100 |
| `stepdag-scans-products` | 03 | #101 |
| `stepdag-scans-products` | 04 | #102 |
| `stepdag-scans-products` | 05 | #103 |
| `stepdag-scans-products` | 06 | #104 |
| `stepdag-snacker-parity` | spec | #105 |
| `stepdag-snacker-parity` | 01 | #106 |
| `stepdag-snacker-parity` | 02 | #107 |
| `stepdag-snacker-parity` | 03 | #108 |
| `stepdag-snacker-parity` | 04 | #109 |
| `stepdag-snacker-parity` | 05 | #110 |
| `stepdag-snacker-parity` | 06 | #111 |
| `stepdag-snacker-parity` | 07 | #112 |
| `stepdag-snacker-parity` | 08 | #113 |
| `stepdag-snacker-parity` | 09 | #114 |
| `stepdag-snacker-parity` | 10 | #115 |
| `stepdag-scans-triggered` | idea | #116 |
| `snacker-on-stepdag` | spec | #117 |
| `snacker-on-stepdag` | 01 | #118 |
| `snacker-on-stepdag` | 02 | #119 |
| `snacker-on-stepdag` | 03 | #120 |
| `snacker-on-stepdag` | 04 | #121 |
| `snacker-on-stepdag` | 05 | #122 |
| `snacker-on-stepdag` | 06 | #123 |
| `snacker-on-stepdag` | 07 | #124 |
| `snacker-on-stepdag` | 08 | #125 |
