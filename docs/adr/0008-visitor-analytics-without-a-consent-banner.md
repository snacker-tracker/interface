# Visitor analytics run without a consent banner, designed toward the CNIL audience-measurement exemption

**Status: partly in place.** Opt-out and the privacy note are deferred. Until both exist, the site doesn't meet the exemption. They must be built before the site has any EU presence.

The site records interactions so we can tell whether it's used, how individual features are used, and whether it's healthy. A consent banner would get in visitors' way, and its refusals would skew the counts. There are no EU offices yet, but the user wants to be ready for one. So the analytics are built to the CNIL's audience-measurement exemption, which allows measurement without consent:
- first-party only
- used only for aggregate statistics, never joined to other data
- visitor IDs expire after 13 months
- raw data is deleted after 25 months
- no full user agent is recorded

## Considered options

- **A consent banner.** Rejected: it adds friction and loses the visits of people who refuse, while the purpose only needs audience measurement.
- **Honouring Global Privacy Control and Do Not Track now.** Deferred together with the opt-out toggle, to keep the first version small.

## Consequences

- The exemption needs two things the site doesn't have yet: a privacy note telling visitors what is recorded, and a way to object. Until both arrive, every prod visitor is recorded. The planned opt-out honours GPC and DNT, adds a footer link to the privacy note with a toggle, and deletes the IDs when someone opts out.
- Anything that would join interactions to other data, or use them for more than aggregate statistics, breaks the exemption and brings the banner back.
