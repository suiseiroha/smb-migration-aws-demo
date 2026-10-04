# Pricing: migration and landing zone together

One place to see what this actually costs to run, both the modernized
app architecture (`docs/simulation-guide-rocky-linux-10.md` /
`docs/simulation-guide-windows.md`) and the governance layer on top of
it (`docs/landing-zone.md`), since the two get built at different times
but should be budgeted for together.

## The modernized app architecture

Everything here bills hourly while running, nothing bills for being
"deployed," only for being on:

| Resource | Rate | Notes |
|---|---|---|
| RDS (`db.t3.micro`, Single-AZ) | ~$0.02 to $0.027/hr | Runs the whole time the stack exists |
| Application Load Balancer | ~$0.025/hr + small per-request charge | Bills even with zero traffic |
| NAT Gateway | ~$0.059/hr + per-GB data processing | The one to watch, keeps billing even completely idle |
| EC2 (`t3.micro`, 1-2 instances) | ~$0.01 to $0.014/hr each | Scales with the Auto Scaling group |
| DynamoDB, S3, CloudWatch | effectively $0 at this scale | Pay-per-use, this project's traffic doesn't register |

Left running continuously, that's roughly **$2 to $3.50 a day**, call it
**$60 to $100 a month** if it were never torn down. In practice this
project tears it down between sessions (`cdk destroy --all`), so the
real cost is closer to a few dollars total across the whole build,
demo, and teardown cycle. The on-prem equivalent isn't really
comparable the same way: a physical or VMware host bills the same
whether it's busy or idle, which is exactly the "pay for capacity
whether you use it or not" problem this migration is meant to get away
from.

## The landing zone

AWS Organizations itself has no charge. Once it's actually standing up
the accounts this project uses it for, two things start billing, both
usage-based rather than hourly:

| Service | Pricing model | Expected cost at this scale |
|---|---|---|
| AWS Config (org-wide aggregator) | Per configuration item recorded | A few dollars a month, scales with how many resources exist across all accounts |
| GuardDuty (org-wide) | Per event analyzed (CloudTrail/VPC Flow/DNS logs) | Low single digits a month for one small workload account |
| CloudTrail (organization trail) | Free for management events; data events cost extra if enabled | $0 unless data events are turned on, which this design doesn't call for |

Realistically, **$3 to $8 a month** total for the landing zone itself,
regardless of whether the workload underneath it is running or torn
down, since Config and GuardDuty keep watching the account structure
even when nothing is deployed inside it.

## What doesn't follow the usual "tear it down" advice

Everything else in this repo gets torn down between sessions on
purpose, cost discipline is part of the point. The landing zone is the
exception, and it's worth being direct about why: closing an AWS member
account takes a mandatory 90-day wait, and an AWS Organization isn't
something to spin up and dismantle for a demo. Once this gets built for
real, the few dollars a month it costs is the ongoing price of having
it, not a teardown candidate the way NAT Gateway or RDS are. Budget it
as a fixed monthly line item, not a per-demo-session cost like
everything else here.

## Put together

| Scenario | Monthly cost |
|---|---|
| App only, torn down between sessions (current practice) | A few dollars total per build/demo/teardown cycle |
| App only, left running continuously | ~$60 to $100/month |
| Landing zone only, always on (this is the normal state once built) | ~$3 to $8/month |
| Landing zone + one workload account, left running continuously | ~$65 to $110/month |

None of this is free-tier-guaranteed long term, and none of it accounts
for a second or third workload account once the client actually adds
one, each additional workload adds its own compute/data costs on top of
this, the landing zone's own cost barely moves since Config/GuardDuty
pricing is per-event, not per-account.
