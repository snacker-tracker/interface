# CloudFront access logs go to CloudWatch Logs and S3, with client IPs

Each distribution sends its access logs through standard logging (v2) to two destinations at once:
- a CloudWatch log group, kept for 30 days, for quick queries with Logs Insights
- a private S3 bucket, kept for 90 days, as the archive. Its keys are Hive-compatible and partitioned by hour, so a query engine can be pointed at it later.

The logs keep each request's client IP, for security and operations: tracing a scraper, a burst of errors or a spike to one source. They leave out the user agent, X-Forwarded-For, cookies and the referrer. Location comes from the coarser country and ASN fields.

## Considered options

- **Legacy standard logging.** Rejected: it only writes to S3, needs ACLs on the bucket, and can't choose fields. For S3, v2 costs nothing extra either.
- **S3 only, queried with Athena when needed.** Rejected for now: Logs Insights makes rough questions ("what were the 5xx in the last hour?") quick, and at this traffic the CloudWatch delivery costs cents.
- **Routing CloudWatch Logs on to S3.** Rejected: one delivery source can feed both destinations directly, with no subscription filter, Firehose or extra role.
- **Leaving out the client IP, or truncating it with a CloudFront Function.** Deferred: there's no abuse to trace yet. Revisit this if the IP stops paying for itself.

## Consequences

- Client IPs are personal data. Keeping them is a different purpose from the audience measurement in ADR 0008, and these logs must never be joined to interaction records. Joining them would break that ADR's exemption. Revisit keeping IPs along with ADR 0008's deferred opt-out and privacy note, before any EU presence; the privacy note has to mention them.
- Under ADR 0005, CI can't write resource policies, so the admin configuration writes them ahead of time: the bucket's policy for log delivery, and an account-level CloudWatch Logs policy over `/aws/vendedlogs/cloudfront/snacker-tracker-<env>-*` in us-east-1. Delivery finds those policies and never needs to add its own.
- CI does get `cloudfront:AllowVendedLogDeliveryForResource` on its own tagged distributions. IAM files that action under permissions management, but it only lets log delivery read the distribution's logs. Where they land is still decided by the admin's policies.
- CloudFront's log delivery is set up in us-east-1, so the delivery source, destinations and log group live there. The bucket stays in ap-southeast-1.
