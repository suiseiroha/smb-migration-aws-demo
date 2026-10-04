# infrastructure/landing-zone/

Policy files and a CDK app for the multi-account landing zone design in
`docs/landing-zone.md`. Nothing here is deployed, this is the actual
policy content referenced by that doc, kept as real files instead of
code blocks buried in prose, the same reasoning `infrastructure/iam/`
already follows for the IAM policies this project actually uses.

- `cdk/`: a separate CDK app (see `docs/landing-zone.md`, "Doing
  Phases 2, 3, and 6 as code instead of by hand") that creates the OUs,
  the Log Archive and Audit accounts, and the Workloads SCP as code.
  Deliberately not part of `infrastructure/cdk/`'s own `cdk deploy
  --all`, that app deploys the workload itself inside an account this
  one's job is to help create.

- `smb-migration-demo-scp-workloads.json`: the Service Control Policy
  for the `Workloads` OU (see `docs/landing-zone.md`, Phase 6). Locks
  workload accounts to `ap-southeast-1` (matching the region decision
  already locked in for the app itself) and blocks an account from
  leaving the organization. Attach it through **Organizations →
  Policies → Service control policies** once the organization actually
  exists, paste this file's contents in directly.
- `smb-migration-demo-permission-set-org-admin.json`: the IAM Identity
  Center permission set for the Management account (see
  `docs/landing-zone.md`, Phase 7). Organizations, Identity Center
  itself, and read-only billing, nothing else, deliberately excludes
  every service a workload would actually use since the Management
  account should never run one.
- `smb-migration-demo-permission-set-security-auditor.json`: the
  permission set for the Audit account. Read-only across GuardDuty,
  Security Hub, CloudTrail, Config, and the Log Archive bucket, no
  write access anywhere.

(`WorkloadAdmin`, the third permission set, intentionally has no file
here: it's AWS's own managed `AdministratorAccess` policy, assigned
per-account, see `docs/landing-zone.md`, Phase 7 for why that's a
deliberate choice rather than an inconsistency with the scoped policies
above.)

Test any SCP or permission set against a non-critical account before
attaching it for real. A misconfigured one can lock an account out of
actions it actually needs, including sometimes IAM itself, and SCPs
apply even to an account's root user.
