# AWS Migration Simulation: SMB Invoice Tracker

A complete, self-contained walkthrough: the business problem, the AWS
solution, the architecture, and then the hands-on simulation itself,
from a bare Rocky Linux 10 VM through to a live, highly-available
deployment on AWS, and back down again. Everything here uses the AWS
Management Console, no CDK, no infrastructure as code, step by step.

## The Business Problem

A small business runs its invoice and customer tracker the way a lot
of small businesses actually run internal line-of-business software:
one server, set up by hand, and never touched again because it works.
This is a non-critical, low-risk workload, exactly the kind of
application worth using as a first pilot for a move to AWS, to
evaluate what AWS's auto-scaling capabilities can actually offer
before committing anything more critical to the cloud.

The application itself is a Flask web app for tracking customers and
invoices, with file attachments (receipts, scanned documents) per
invoice. Today it runs on a single Rocky Linux virtual machine,
on-premises, with:

- **A SQLite database**, a single file on that server's local disk.
- **Filesystem-backed sessions**, a user's login state stored in files
  next to the running process.
- **Local file uploads**, invoice attachments saved directly to a
  folder on that same disk.

None of this is a defect in how the application was written. It is
realistic of how a lot of small businesses actually operate, and it
creates four concrete risks:

1. **No backups.** The database is a single file. A disk failure
   erases every invoice and customer record, with nothing to restore
   from.
2. **One person holds the knowledge.** Whoever set up the server is
   the only one who knows how it is configured. No runbook exists.
3. **No redundancy.** One instance means one outage takes the whole
   system down, with no way to patch or reboot without downtime.
4. **State is tied to the instance.** Sessions and uploads live on
   local disk alongside the database. Adding a second server would not
   help on its own: a login only works on the instance that created
   it, and an uploaded file only exists on the instance that received
   it.

That fourth point is the real blocker, and it rules out the simplest
possible fix (moving the exact same server, unchanged, onto an AWS
EC2 instance). It is why this simulation evaluates the migration
strategy carefully rather than just lifting the box as-is.

## The AWS Solution

Two ways to move an application to AWS are commonly considered:

- **Rehost** ("lift and shift"): move the application as-is onto AWS
  compute. Same code, same architecture, just a different data center.
- **Replatform**: change specific pieces to use managed cloud
  services, without a full rewrite.

Rehosting alone does not fix any of the four risks above, because
those risks are all about *where state lives*, not about which data
center the server sits in. Put a second rehosted instance behind a
load balancer and a user's login only works on the instance that
created it, an uploaded file only exists on the instance that received
it, and two instances still cannot safely share one SQLite file.

The solution adopted here is to **replatform** exactly the three
stateful pieces, without rewriting the application's business logic:

- Sessions move to **Amazon DynamoDB**, so any instance can read any
  user's session.
- Uploads move to **Amazon S3**, so any instance can serve a file any
  other instance received.
- The database moves to **Amazon RDS**, gaining managed automated
  backups and a database built to be accessed by multiple application
  servers over the network at once.

The application then runs behind a load balancer, in an Auto Scaling
group spanning two Availability Zones, with none of its state tied to
any specific instance. This is the smallest change that actually
solves the real problem: state tied to a single instance. A full
rewrite was not necessary either, since the business logic (customers,
invoices, attachments) has nothing to do with where sessions or files
happen to be stored.

**Why not AWS's own migration tooling?** AWS Application Migration
Service (MGN) replicates a source server's disks and produces an EC2
instance that is a copy of the source, a rehost tool by design, with
no mechanism to decouple session, upload, and database state during
replication. It cannot produce the target's stateless, multi-instance
shape no matter how it is configured. AWS Database Migration Service
(DMS) does not support SQLite as a source engine at all, and this
database is small enough (a handful of customers and invoices) that a
one-time export and import is more appropriate than continuous
replication tooling built for large, actively written production
databases.

## How AWS Services Address the Business Problem

| Business problem | AWS service | How it addresses the problem |
|---|---|---|
| No backups; a disk failure loses everything | Amazon RDS | Automated backups (7-day retention) and a manual snapshot before any teardown, neither of which a SQLite file on local disk ever had |
| Sessions tied to one instance, breaks horizontal scaling | Amazon DynamoDB | Any instance can read and write any user's session, so a load balancer can route to either instance freely |
| Uploaded files tied to one instance | Amazon S3 | Any instance can serve a file any other instance received; downloads go through short-lived presigned URLs rather than through the app |
| Single point of failure (one instance, one AZ) | Application Load Balancer + Auto Scaling group across 2 AZs | Traffic is distributed across healthy instances in two Availability Zones; a failed instance is detected and replaced automatically |
| No supervision, no health checks | ALB health checks + Auto Scaling group | Unhealthy instances are removed from rotation and replaced without anyone noticing an outage |
| Flat network, no segmentation | A VPC with public, app, and database subnet tiers | Security groups scoped tier to tier only; the database is never directly reachable from the internet, the same principle as VLAN segmentation on-premises |
| SSH key sprawl, open administrative ports | An IAM instance role + AWS Systems Manager Session Manager | No SSH keys and no open port 22 anywhere; administrative access is brokered through IAM instead |
| No visibility into system health | Amazon CloudWatch (dashboard + alarms) | CPU, storage, and request metrics visualized in one place, with alarms on high CPU and low RDS storage |
| Overly broad access instead of least privilege | A scoped custom IAM policy | Access is limited to exactly the services this workload actually uses, not full administrator access |
| Tribal knowledge, no documentation | This simulation itself | A written, repeatable procedure rather than one person's memory of how the server was configured |

## The AWS Architecture

The modernized architecture is a three-tier design in a single VPC
spanning two Availability Zones in `ap-southeast-1`:

- **Public tier**: an Application Load Balancer only, spanning both
  Availability Zones. This is the only entry point from the internet.
- **App tier**: an Auto Scaling group (minimum 1, maximum 2 instances)
  in private subnets, with no public IP addresses and no SSH access.
  Administrative access, when needed, goes through SSM Session
  Manager.
- **Data tier**: Amazon RDS for MySQL in private, internet-isolated
  subnets, alongside DynamoDB (sessions) and S3 (uploads), neither of
  which is tied to any specific application instance.

Security groups are scoped tier to tier only: the load balancer
accepts traffic from the internet, the app tier accepts traffic only
from the load balancer, and the database tier accepts traffic only
from the app tier. Nothing is open more broadly than that.

![Modernized architecture: a VPC in ap-southeast-1 spanning two availability zones, with an internet gateway feeding an Application Load Balancer in the public subnet, two app instances in private app subnets talking to DynamoDB and S3, and RDS for MySQL in the private DB subnets, alongside IAM, CloudWatch, Secrets Manager, and a NAT Gateway](diagrams/modernized-architecture.png)

---

# Simulation Guide: Rocky Linux 10 to AWS, via the Console

Everything below is one continuous walkthrough: a bare Rocky Linux 10
machine, with nothing on it, through to a live, verified, migrated
deployment on AWS, and a full teardown. All resource names use the
`smb-migration-demo-*` prefix; tag everything you create with
`Project=smb-migration-demo` as you go, it makes teardown and cost
tracking (Cost Explorer, Resource Groups) much easier later.

## Part 1: Getting Started from Scratch

Starting from a completely bare Rocky Linux 10 machine: no git, no
code, nothing installed.

**What you need:** Rocky Linux 10 (minimal install is fine), a regular
sudo-capable user, a GitHub account with access to this private repo,
and network/internet access from this machine.

Install git and the GitHub CLI:

```bash
sudo dnf install -y git 'dnf-command(config-manager)'
sudo dnf config-manager --add-repo https://cli.github.com/packages/rpm/gh-cli.repo
sudo dnf install -y gh
```

Authenticate and clone the repository:

```bash
gh auth login
```

Pick **GitHub.com** -> **HTTPS** -> **Login with a web browser**. It
gives you a one-time code and opens a browser tab, approve it there.

```bash
gh repo clone suiseiroha/smb-migration-aws
cd smb-migration-aws
```

**No `gh`, or you would rather use plain git?** Generate a Personal
Access Token at `github.com/settings/tokens` (classic, `repo` scope is
enough), then:

```bash
git clone https://github.com/suiseiroha/smb-migration-aws.git
cd smb-migration-aws
```

When prompted, the username is your GitHub username, the password is
the token, not your actual GitHub password, GitHub no longer accepts
that for git operations.

## Part 2: Installing legacy-app from Scratch

This is the "before" state: a real on-premises box, stateful by
design, running the invoice/customer tracker exactly the way a small
business actually would.

Install system packages. Rocky Linux 10 ships Python 3.12 by default
(`python3 --version` to confirm), well above Flask's minimum of 3.8:

```bash
sudo dnf install -y python3 python3-pip firewalld policycoreutils-python-utils
sudo systemctl enable --now firewalld
```

Set up the application, from inside the cloned repository:

```bash
cd legacy-app
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python seed.py
```

`seed.py` creates the SQLite database, an admin user, and sample
customers and invoices. Safe to re-run, it only inserts if the
database is empty.

Run it as a systemd service, so it survives disconnecting and restarts
itself if it crashes:

```bash
sudo tee /etc/systemd/system/legacy-app.service > /dev/null << UNIT
[Unit]
Description=SMB legacy invoice tracker (unmanaged, single instance)
After=network.target

[Service]
Type=simple
User=$(whoami)
WorkingDirectory=/home/$(whoami)/smb-migration-aws/legacy-app
Environment=FLASK_DEBUG=0
ExecStart=/home/$(whoami)/smb-migration-aws/legacy-app/.venv/bin/python /home/$(whoami)/smb-migration-aws/legacy-app/app.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
UNIT

sudo systemctl daemon-reload
```

The heredoc delimiter above is deliberately unquoted (`<< UNIT`, not
`<< 'UNIT'`), so `$(whoami)` expands into the file automatically
instead of you having to find-and-replace a placeholder by hand.
Setting `FLASK_DEBUG=0` is deliberate too: the Flask development
server's debugger is a remote-code-execution risk on anything actually
reachable over a network.

Rocky Linux 10 runs SELinux enforcing by default, and its policy
generally blocks system services from executing anything under a home
directory at all, regardless of file permissions, since that's exactly
the kind of thing it's designed to stop. Starting the service right
now would fail with `status=203/EXEC`. Give the virtual environment an
executable type SELinux actually allows system services to run,
before starting it:

```bash
sudo semanage fcontext -a -t bin_t "/home/$(whoami)/smb-migration-aws/legacy-app/.venv(/.*)?"
sudo restorecon -Rv /home/$(whoami)/smb-migration-aws/legacy-app/.venv
```

`restorecon` alone (without the `semanage fcontext` rule first) won't
fix this: the directory's existing label is already the "correct"
default for a home directory, which is exactly what's blocked. The
`semanage` command records a persistent rule saying everything under
`.venv/` should carry the standard executable-content type instead, so
`restorecon` has something different to apply, and the rule survives
future relabels and reboots.

Now start it:

```bash
sudo systemctl enable --now legacy-app
sudo firewall-cmd --permanent --add-port=5000/tcp
sudo firewall-cmd --reload
```

**Verify:** browse to `http://<vm-ip>:5000`, log in with `admin` /
`changeme123`. Create a customer, an invoice, and attach a file, so
there is something real to migrate later.

## Part 3: Prerequisites for the AWS Side

Even a Console-driven build needs the AWS CLI for a handful of things
the Console cannot do at all: SSM Run Command (no SSH onto the app
instances, by design), and driving the actual data migration.

You will need a second machine for this part and onward (your own
workstation, which can also be this same Rocky Linux 10 machine if you
prefer), with this repository cloned onto it, and:

```bash
sudo dnf install -y unzip
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install
aws --version
```

**IAM user**, the one step you cannot skip since you need credentials
before the CLI can do anything: follow
[`infrastructure/iam/README.md`](../infrastructure/iam/README.md) to
create the scoped `smb-migration-demo-cli` user (not
`AdministratorAccess`) and run `aws configure` yourself, region
`ap-southeast-1`. Verify:

```bash
aws sts get-caller-identity
```

## Part 4: Network

**Console: VPC -> Your VPCs -> Create VPC**
- Resources to create: **VPC only**
- Name tag: `smb-migration-demo-vpc`
- IPv4 CIDR: `10.0.0.0/16`
- IPv6 CIDR block: No IPv6 CIDR block
- Tenancy: Default

**Console: VPC -> Internet Gateways -> Create internet gateway**
- Name tag: `smb-migration-demo-igw`
- Create, then **Actions -> Attach to VPC** -> `smb-migration-demo-vpc`

**Console: VPC -> Subnets -> Create subnet**, VPC = `smb-migration-demo-vpc`,
add all 6 in one flow (**Add new subnet** repeated):

| Name | Availability Zone | CIDR |
|---|---|---|
| `public-1a` | `ap-southeast-1a` | `10.0.0.0/24` |
| `public-1b` | `ap-southeast-1b` | `10.0.1.0/24` |
| `app-1a` | `ap-southeast-1a` | `10.0.2.0/24` |
| `app-1b` | `ap-southeast-1b` | `10.0.3.0/24` |
| `db-1a` | `ap-southeast-1a` | `10.0.4.0/24` |
| `db-1b` | `ap-southeast-1b` | `10.0.5.0/24` |

**Console: VPC -> NAT Gateways -> Create NAT gateway** (one, shared by
both app subnets, a deliberate cost decision rather than one per AZ)
- Name: `smb-migration-demo-nat`
- Subnet: `public-1a`
- Connectivity type: Public
- Elastic IP allocation ID: click **Allocate Elastic IP**
- Takes a few minutes to reach `Available`, the next step needs it
  ready

**Console: VPC -> Route Tables -> Create route table**, three total:

- `smb-migration-demo-public-rt`: **Edit routes**, add `0.0.0.0/0` ->
  Internet Gateway -> `smb-migration-demo-igw`. **Edit subnet
  associations** -> `public-1a`, `public-1b`.
- `smb-migration-demo-app-rt`: **Edit routes**, add `0.0.0.0/0` -> NAT
  Gateway -> `smb-migration-demo-nat`. **Edit subnet associations** ->
  `app-1a`, `app-1b`.
- `smb-migration-demo-db-rt`: leave routes as the default local-only
  route, no internet access at all for this tier. **Edit subnet
  associations** -> `db-1a`, `db-1b`.

**Console: VPC -> Security Groups -> Create security group**, three
total, VPC = `smb-migration-demo-vpc`:

- `smb-migration-demo-alb-sg`: Inbound -> HTTP (80) from `0.0.0.0/0`.
- `smb-migration-demo-app-sg`: Inbound -> Custom TCP, port `5000`,
  source = `smb-migration-demo-alb-sg` (the security group itself, not
  a CIDR).
- `smb-migration-demo-db-sg`: Inbound -> MYSQL/Aurora (3306), source =
  `smb-migration-demo-app-sg`.

Every rule points at another security group, never a raw CIDR for
internal traffic, tier to tier only.

## Part 5: Data Services

**Secrets Manager first**, both secrets get created here so nothing
downstream has to wait:

**Console: Secrets Manager -> Store a new secret**
- Secret type: Other type of secret
- Key/value pairs -> Plaintext, paste a value from
  `python3 -c "import secrets; print(secrets.token_hex(32))"`
- Secret name: `smb-migration-demo/flask-secret-key`

For the database password, generate one yourself first (a password
manager, or `python3 -c "import secrets; print(secrets.token_urlsafe(24))"`),
write it down temporarily, you will use the same value twice:

**Console: Secrets Manager -> Store a new secret**
- Secret type: Other type of secret
- Plaintext: the password you generated
- Secret name: `smb-migration-demo/db-password`

**Console: RDS -> Subnet groups -> Create DB subnet group**
- Name: `smb-migration-demo-db-subnet-group`
- VPC: `smb-migration-demo-vpc`
- Add subnets: `db-1a`, `db-1b`

**Console: RDS -> Databases -> Create database**
- Standard create
- Engine: MySQL, version 8.0 (closest available 8.0.x)
- Templates: Dev/Test
- DB instance identifier: `smb-migration-demo-db`
- Master username: `app_user`
- Master password: **Self managed**, the exact same password you just
  put in `smb-migration-demo/db-password` above (`modern-app` reads
  the password from that secret, not from RDS directly, so the two
  must match)
- Instance configuration: Burstable classes, `db.t3.micro`
- Storage: 20 GiB, gp3
- Connectivity: VPC = `smb-migration-demo-vpc`, DB subnet group =
  `smb-migration-demo-db-subnet-group`, Public access = **No**,
  existing VPC security group = `smb-migration-demo-db-sg` (remove the
  default one)
- **Additional configuration -> Initial database name:**
  `smb_migration_demo`, set this now, not after; skipping it here was
  a real bug hit during this project's own build
- Backup: enable automated backups, retention 7 days
- Encryption: enable
- Create database, takes roughly 10 minutes

**Console: DynamoDB -> Tables -> Create table**
- Table name: `smb-migration-demo-sessions`
- Partition key: `session_id`, type String
- Table settings: Customize settings -> Read/write capacity mode:
  On-demand
- After creation, the table's **Additional settings** tab -> Time to
  Live -> Enable -> TTL attribute: `expires_at`

**Console: S3 -> Create bucket**
- Bucket name: `smb-migration-demo-uploads`
- Region: `ap-southeast-1`
- Block all public access: leave enabled (default)
- Bucket versioning: disabled
- Encryption: enable, SSE-S3 (Amazon S3 managed keys)

## Part 6: IAM Role for the App Instances

**Console: IAM -> Policies -> Create policy**
- JSON tab, paste the contents of
  [`infrastructure/iam/smb-migration-demo-app-role-policy.json`](../infrastructure/iam/smb-migration-demo-app-role-policy.json)
- Name: `smb-migration-demo-app-role-policy`

**Console: IAM -> Roles -> Create role**
- Trusted entity type: AWS service
- Use case: EC2
- Permissions: attach `smb-migration-demo-app-role-policy` (just
  created) and the AWS managed policy `AmazonSSMManagedInstanceCore`
  (this is what gives Session Manager access instead of SSH)
- Role name: `smb-migration-demo-app-role`

Creating a role for EC2 through the console automatically creates a
matching instance profile with the same name, there is no separate
instance-profile step.

## Part 7: Package and Upload modern-app's Code

The launch template's user data (next part) expects
`modern-app.tar.gz` to already exist in S3, so this happens first,
from your workstation:

```bash
tar -czf modern-app.tar.gz -C modern-app .
aws s3 cp modern-app.tar.gz s3://smb-migration-demo-uploads/deploy/modern-app.tar.gz --region ap-southeast-1
```

## Part 8: Launch Template

Get your RDS endpoint first: **Console: RDS -> Databases ->
`smb-migration-demo-db`**, copy the value under **Endpoint & port**.

Open
[`modern-app/deploy/ec2-user-data.sh`](../modern-app/deploy/ec2-user-data.sh)
locally and change the `DB_HOST=` line to *your* RDS endpoint (the one
already in that file is specific to this project's own earlier build,
not a generic placeholder). Everything else in the script looks up its
values (the two secret ARNs) by name at boot, so nothing else needs
editing.

**Console: EC2 -> Launch Templates -> Create launch template**
- Name: `smb-migration-demo-lt`
- AMI: Amazon Linux 2023 (search and select the latest)
- Instance type: `t3.micro`
- Key pair: **None** (no SSH keys, SSM Session Manager only)
- Network settings -> Security groups: `smb-migration-demo-app-sg`
- Advanced details -> IAM instance profile: `smb-migration-demo-app-role`
- Advanced details -> Metadata version: **V2 only (token required)** (IMDSv2 enforced)
- Advanced details -> User data: paste the edited script from above

## Part 9: Load Balancer and Auto Scaling Group

**Console: EC2 -> Target Groups -> Create target group**
- Target type: Instances
- Name: `smb-migration-demo-tg`
- Protocol/port: HTTP / 5000
- VPC: `smb-migration-demo-vpc`
- Health checks -> Advanced: path `/login`, healthy threshold 2,
  unhealthy threshold 2, interval 10 seconds, timeout 5 seconds
- Do not register any targets yet, the Auto Scaling group does that

**Console: EC2 -> Load Balancers -> Create load balancer -> Application
Load Balancer**
- Name: `smb-migration-demo-alb`
- Scheme: Internet-facing
- VPC: `smb-migration-demo-vpc`, mappings: `public-1a`, `public-1b`
- Security group: `smb-migration-demo-alb-sg` (remove the default one)
- Listener: HTTP : 80 -> forward to `smb-migration-demo-tg`

**Console: EC2 -> Auto Scaling Groups -> Create Auto Scaling group**
- Name: `smb-migration-demo-asg`
- Launch template: `smb-migration-demo-lt`
- VPC: `smb-migration-demo-vpc`, subnets: `app-1a`, `app-1b`
- Attach to an existing load balancer -> choose your existing target
  group -> `smb-migration-demo-tg`
- Health checks: turn on **ELB health checks**, health check grace
  period `300` seconds (the app needs time to boot before a failed
  check counts against it)
- Group size: Desired `1`, Minimum `1`, Maximum `2`

The instance takes a couple of minutes to boot (installing
dependencies, starting the app), the target group will show
**unhealthy** until then, that is expected. Poll it instead of
guessing, from your workstation:

```bash
TG_ARN=$(aws elbv2 describe-target-groups --names smb-migration-demo-tg \
  --region ap-southeast-1 --query "TargetGroups[0].TargetGroupArn" --output text)
aws elbv2 wait target-in-service --target-group-arn "$TG_ARN" --region ap-southeast-1
echo "Target is healthy"

ALB_DNS=$(aws elbv2 describe-load-balancers --names smb-migration-demo-alb \
  --region ap-southeast-1 --query "LoadBalancers[0].DNSName" --output text)
echo "http://$ALB_DNS"
```

The database seeds itself at boot (schema plus a placeholder admin
user and sample rows, from `ec2-user-data.sh`), so the ALB URL should
already log in with `admin` / `changeme123` at this point, before your
actual migrated data exists.

## Part 10: Monitoring

**Console: CloudWatch -> Dashboards -> Create dashboard**
- Name: `smb-migration-demo-dashboard`
- Add widgets: ASG average CPU (`AWS/EC2`, `CPUUtilization`, dimension
  `AutoScalingGroupName` = `smb-migration-demo-asg`), RDS free storage
  space (`smb-migration-demo-db`'s `FreeStorageSpace` metric), ALB
  request count and target response time
  (`smb-migration-demo-alb` / `smb-migration-demo-tg` metrics)

**Console: CloudWatch -> Alarms -> Create alarm**, two:
- `smb-migration-demo-asg-high-cpu`: metric = the ASG CPU metric
  above, threshold > 70, for 2 consecutive 5-minute periods
- `smb-migration-demo-rds-low-storage`: metric = RDS
  `FreeStorageSpace`, threshold < 2 GiB, for 1 period

Alarm-only for now, not wired to an actual scaling policy.

## Part 11: Migrate the Legacy Data from the On-Premises VM

RDS is not publicly accessible by design, so nothing outside the VPC
can write to it directly, not even your own workstation. Every step
that touches RDS runs on the app instance itself, driven remotely via
SSM (no SSH). Your workstation's job is relaying the data through S3,
since S3, unlike RDS, is reachable from anywhere.

**1. Pull the data off the Rocky Linux 10 VM**, from your workstation:

```bash
scp your-user@<vm-ip>:smb-migration-aws/legacy-app/instance/app.db ./app.db
mkdir -p uploads
scp your-user@<vm-ip>:smb-migration-aws/legacy-app/uploads/* ./uploads/ 2>/dev/null || true
```

**2. Package the migration script with the data, push to S3** (the
same `deploy/` prefix, the app role already has read/write there):

```bash
mkdir -p migration-data/uploads
cp app.db migration-data/
cp uploads/* migration-data/uploads/ 2>/dev/null || true
tar -czf migration-support.tar.gz scripts/export_sqlite_to_rds.py migration-data/
aws s3 cp migration-support.tar.gz s3://smb-migration-demo-uploads/deploy/ --region ap-southeast-1
```

**3. Run it on the app instance via SSM.** `export_sqlite_to_rds.py`
imports `modern-app`'s own models and config, so it runs from inside
`modern-app`'s already-deployed virtual environment, reusing the same
environment variables the systemd unit already set:

```bash
INSTANCE_ID=$(aws autoscaling describe-auto-scaling-groups \
  --auto-scaling-group-names smb-migration-demo-asg --region ap-southeast-1 \
  --query "AutoScalingGroups[0].Instances[0].InstanceId" --output text)

CMD_ID=$(aws ssm send-command --instance-ids "$INSTANCE_ID" \
  --document-name "AWS-RunShellScript" \
  --parameters 'commands=[
    "aws s3 cp s3://smb-migration-demo-uploads/deploy/migration-support.tar.gz /tmp/migration-support.tar.gz --region ap-southeast-1",
    "mkdir -p /tmp/migration && tar -xzf /tmp/migration-support.tar.gz -C /tmp/migration",
    "cd /home/ec2-user/app-deploy/modern-app && grep Environment= /etc/systemd/system/modern-app.service > /tmp/envs.txt && while IFS= read -r line; do export \"${line#Environment=}\"; done < /tmp/envs.txt && ./.venv/bin/python /tmp/migration/export_sqlite_to_rds.py /tmp/migration/migration-data/app.db /tmp/migration/migration-data/uploads"
  ]' \
  --region ap-southeast-1 --query "Command.CommandId" --output text)

sleep 10
aws ssm get-command-invocation --command-id "$CMD_ID" --instance-id "$INSTANCE_ID" \
  --region ap-southeast-1 --query "{Status:Status,Output:StandardOutputContent,Error:StandardErrorContent}"
```

Expect output like:

```
Schema created/confirmed in RDS.
Migrated 3 customers.
Migrated 4 invoices.
Migrated 1 users.
Migrated 1 attachment records, 1 files uploaded to S3.

Validation (RDS row counts):
 customers: 3
 invoices: 4
 users: 1
 attachments: 1
```

Row counts matching the source exactly *is* the validation step, not a
separate one. Log back into the ALB URL, the dashboard should now show
your actual migrated data, and the migrated attachment should download
correctly through a presigned S3 URL.

## Part 12: Scale Up and Verify High Availability

**Console: EC2 -> Auto Scaling Groups -> `smb-migration-demo-asg` ->
Edit** -> Desired capacity: `2` -> Update, or from the CLI:

```bash
aws autoscaling set-desired-capacity \
  --auto-scaling-group-name smb-migration-demo-asg \
  --desired-capacity 2 --region ap-southeast-1

TG_ARN=$(aws elbv2 describe-target-groups --names smb-migration-demo-tg \
  --region ap-southeast-1 --query "TargetGroups[0].TargetGroupArn" --output text)
aws elbv2 wait target-in-service --target-group-arn "$TG_ARN" --region ap-southeast-1
```

```bash
python scripts/smoke_test_statelessness.py
```

This covers round-robin requests holding one session, and
deterministically forcing traffic through each instance individually,
to prove the same session and uploaded file work through either one
alone. Scale back to `1` afterward to save the cost of the second
`t3.micro`.

## Part 13: Tear Down via the Console

Manual builds do not clean up after themselves, so do this in
dependency order, newest resources first:

1. **RDS -> Databases -> `smb-migration-demo-db` -> Actions -> Take
   snapshot**, name it something identifiable, wait for it to
   complete.
2. **Auto Scaling Groups -> `smb-migration-demo-asg` -> Delete** (this
   terminates both instances).
3. **Load Balancers -> `smb-migration-demo-alb` -> Delete**, then
   **Target Groups -> `smb-migration-demo-tg` -> Delete**.
4. **Launch Templates -> `smb-migration-demo-lt` -> Delete**.
5. **RDS -> Databases -> `smb-migration-demo-db` -> Delete** (skip the
   final-snapshot prompt, one was already taken manually in step 1).
6. **DynamoDB -> Tables -> `smb-migration-demo-sessions` -> Delete.**
7. **S3 -> `smb-migration-demo-uploads`**, empty the bucket first
   (versioned or not, S3 will not delete a non-empty bucket), then
   delete the bucket.
8. **VPC -> NAT Gateways -> `smb-migration-demo-nat` -> Delete**, then
   release the Elastic IP it was using (**VPC -> Elastic IPs ->
   Release**).
9. **VPC -> Route Tables**, delete `smb-migration-demo-app-rt` and
   `smb-migration-demo-db-rt` (the main/default route table for the
   VPC is removed with the VPC itself).
10. **VPC -> Security Groups**, delete `smb-migration-demo-app-sg`,
    `smb-migration-demo-db-sg`, `smb-migration-demo-alb-sg`, in that
    order (a security group referenced by another cannot be deleted
    first).
11. **VPC -> Subnets**, delete all 6.
12. **VPC -> Internet Gateways -> `smb-migration-demo-igw` -> Actions
    -> Detach**, then delete it.
13. **VPC -> Your VPCs -> `smb-migration-demo-vpc` -> Delete.**
14. **IAM -> Roles -> `smb-migration-demo-app-role` -> Delete**, then
    **IAM -> Policies -> `smb-migration-demo-app-role-policy` ->
    Delete.**
15. **Secrets Manager**, delete `smb-migration-demo/db-password` and
    `smb-migration-demo/flask-secret-key` (these have a mandatory
    recovery window, they will not disappear immediately, that is
    normal).
16. **CloudWatch**, delete the `smb-migration-demo-dashboard`
    dashboard and both alarms.

The RDS snapshot from step 1 survives all of this deliberately, delete
it separately once you are sure you do not need it: **RDS ->
Snapshots -> (your snapshot) -> Delete.**

The on-premises Rocky Linux 10 VM is not AWS-billed, leave it running
or shut it down as you like, it is not part of this teardown.

## Troubleshooting

**On the Rocky Linux 10 VM:** `curl` works locally but the page will
not load from another machine, almost always the firewall, confirm
with `sudo firewall-cmd --list-ports`. A service that fails to start
with `status=203/EXEC` almost always means the SELinux relabel in
Part 2 was skipped, `sudo systemctl status legacy-app --no-pager`
shows that exit code directly. A service that fails to start some
other way (`journalctl -u legacy-app -n 50 --no-pager` shows a Python
traceback rather than an exit code) is usually a path typo in the unit
file, or the virtual environment was not created before enabling the
service. For any other unexpected SELinux denial, check
`sudo ausearch -m avc -ts recent` for the specifics before reaching
for `setenforce 0`, which disables the protection entirely rather than
fixing the actual cause.

**Target group stays unhealthy well past the usual couple of
minutes.** Check the app's own logs via SSM:

```bash
INSTANCE_ID=$(aws autoscaling describe-auto-scaling-groups \
  --auto-scaling-group-names smb-migration-demo-asg --region ap-southeast-1 \
  --query "AutoScalingGroups[0].Instances[0].InstanceId" --output text)

CMD_ID=$(aws ssm send-command --instance-ids "$INSTANCE_ID" \
  --document-name "AWS-RunShellScript" \
  --parameters 'commands=["systemctl status modern-app --no-pager", "journalctl -u modern-app -n 50 --no-pager"]' \
  --region ap-southeast-1 --query "Command.CommandId" --output text)

sleep 8
aws ssm get-command-invocation --command-id "$CMD_ID" --instance-id "$INSTANCE_ID" \
  --region ap-southeast-1 --query "{Status:Status,Output:StandardOutputContent,Error:StandardErrorContent}"
```

Common causes: the instance is still running its boot script (give it
another minute); the `DB_HOST` value in the user data does not match
the actual RDS endpoint (a typo from Part 8 is the most likely cause
on a fresh build); the two Secrets Manager secrets do not exist yet,
or exist under different names than `ec2-user-data.sh` looks up;
`smb-migration-demo/db-password`'s value does not match RDS's actual
master password.

**The app loads but every page is an Internal Server Error, with
`Table 'smb_migration_demo.user' doesn't exist` in the journal.** The
database seeds itself at boot, so this means that step did not run or
did not finish, most likely RDS was not reachable yet when `seed.py`
ran. Re-run it by hand:

```bash
CMD_ID=$(aws ssm send-command --instance-ids "$INSTANCE_ID" \
  --document-name "AWS-RunShellScript" \
  --parameters 'commands=["cd /home/ec2-user/app-deploy/modern-app && grep Environment= /etc/systemd/system/modern-app.service > /tmp/envs.txt && while IFS= read -r line; do export \"${line#Environment=}\"; done < /tmp/envs.txt && ./.venv/bin/python seed.py"]' \
  --region ap-southeast-1 --query "Command.CommandId" --output text)
sleep 8
aws ssm get-command-invocation --command-id "$CMD_ID" --instance-id "$INSTANCE_ID" \
  --region ap-southeast-1 --query "{Status:Status,Output:StandardOutputContent}"
```

**A security group cannot be deleted during teardown.** Something
still references it. Delete in the order listed in Part 13 (app-sg
before alb-sg, since app-sg's rule points at alb-sg), or check
`aws ec2 describe-network-interfaces` for anything still attached.

## Cost While Running

- **RDS** (`db.t3.micro`, Single-AZ): approximately $0.02 to $0.027
  per hour
- **Application Load Balancer**: approximately $0.025 per hour plus a
  small per-request charge
- **NAT Gateway**: approximately $0.059 per hour plus per-GB data
  processing, the one to watch if pausing for more than a few hours
- **EC2** (`t3.micro`, one or two instances): approximately $0.01 to
  $0.014 per hour each
- DynamoDB, S3, and CloudWatch: effectively $0 at this scale
- The on-premises Rocky Linux 10 VM: $0 AWS cost, whatever your own
  hypervisor or hosting costs are

None of this is free-tier-guaranteed long term. Tear down (Part 13)
when not actively demoing.
