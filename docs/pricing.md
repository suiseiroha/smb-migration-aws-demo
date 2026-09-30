# Pricing for this approach

What this project actually costs to run, split into the two pieces it's
built from: the modernized workload itself (Parts 1-13 of either
simulation guide), and the optional multi-account landing zone
(`docs/landing-zone.md`). All figures are `ap-southeast-1` (Singapore)
On-Demand pricing, approximate, and will drift over time — treat this
as a planning estimate, not a quote. Run anything real through the
[AWS Pricing Calculator](https://calculator.aws) before committing a
client to a number.

## The workload

This is what's actually built by following the simulation guide, and
what Part 13's teardown removes.

| Resource | Rate | ~Monthly (730 hrs), running continuously |
|---|---|---|
| NAT Gateway | ~$0.059/hr + ~$0.045/GB processed | ~$43 + data, **the single biggest line item** |
| Application Load Balancer | ~$0.025/hr + a small per-LCU charge | ~$18-25 |
| RDS (`db.t3.micro`, Single-AZ) | ~$0.02-0.027/hr | ~$15-20 |
| EC2 (`t3.micro`, per instance) | ~$0.0104-0.014/hr | ~$8-10 per instance |
| Secrets Manager | $0.40/secret/month | ~$0.80 (2 secrets: Flask key, DB password) |
| DynamoDB, S3, CloudWatch | pay-per-request / negligible at this scale | ~$0-2 |
| On-premises Rocky Linux 10 VM | $0 AWS cost | whatever your own hypervisor/hosting bills |

**Rough total, one app instance, running 24/7: ~$95-105/month.** Part
12's scale-out to a second instance adds another ~$8-10/month while
it's up.

That total is dominated by three things that bill by the hour whether
anyone is using the app or not: the NAT Gateway, the ALB, and RDS. None
of them have a meaningful free tier at this point, and none of them are
worth leaving up between demo sessions — this is exactly why Part 13
(teardown) exists, and why NAT/RDS are the two resources this project
has already had to pause mid-build to control spend.

## The landing zone (optional, not yet built)

Governance costs money differently than the workload does: mostly flat
and usage-driven rather than hourly-idle. See `docs/landing-zone.md`
for what each of these actually is.

| Service | Pricing model | ~Monthly at this project's scale |
|---|---|---|
| AWS Organizations | Free | $0 |
| IAM Identity Center | Free (AWS charges nothing for the service itself) | $0 |
| CloudTrail (organization trail) | First copy of management events is free; S3 storage for the trail is billed separately | ~$0-1, storage only, negligible at low log volume |
| AWS Config (optional aggregator, Phase 4) | ~$0.003 per configuration item recorded (continuous) | ~$2-5 across 4 small accounts |
| GuardDuty (Phase 5) | ~$4.00 per million CloudTrail management events analyzed, plus separate per-GB/per-query pricing if VPC Flow Logs, S3, or DNS protection are also enabled | ~$1-3 with just the foundational (CloudTrail-based) protection; meaningfully more if the optional protections are turned on |
| Security Hub (optional, Phase 5) | ~$3.75 per resource unit/month (roughly: 1 EC2 instance, 12 Lambda functions, or 125 IAM users/roles = 1 unit) | ~$4-15, the most expensive *optional* piece — skip it initially if the client doesn't need a consolidated findings dashboard yet |

**Rough total: ~$5-15/month** with just Config + foundational GuardDuty
enabled (the minimum that makes Phases 4-5 meaningful), climbing to
**~$15-30/month** if Security Hub is turned on across every account.
At this project's scale, none of this needs urgent teardown between
sessions the way NAT Gateway or RDS does — see `docs/landing-zone.md`'s
"Cost and reversibility" section for why it also isn't nearly as easy
to *undo* as the workload resources are.

## Combined picture

| Scenario | ~Monthly |
|---|---|
| Workload only, running continuously | ~$95-105 |
| Workload + landing zone (Config + foundational GuardDuty) | ~$100-120 |
| Workload + landing zone + Security Hub | ~$110-140 |

The practical takeaway for how this project is actually meant to be
run: the workload is the expensive-while-idle part and should be torn
down (Part 13) between sessions; the landing zone is the cheap-but-
semi-permanent part and, once stood up, is meant to stay up.
