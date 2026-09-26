# infrastructure/landing-zone/

Policy files for the multi-account landing zone design in
`docs/landing-zone.md`. Nothing here is deployed, this is the actual
policy content referenced by that doc, kept as a real file instead of a
code block buried in prose, the same reasoning `infrastructure/iam/`
already follows for the IAM policies this project actually uses.

- `smb-migration-demo-scp-workloads.json`: the Service Control Policy
  for the `Workloads` OU (see `docs/landing-zone.md`, Phase 6). Locks
  workload accounts to `ap-southeast-1` (matching the region decision
  already locked in for the app itself) and blocks an account from
  leaving the organization. Attach it through **Organizations →
  Policies → Service control policies** once the organization actually
  exists, paste this file's contents in directly.

Test any SCP against a non-critical account before attaching it to a
real OU. A misconfigured SCP can lock an account out of actions it
actually needs, including sometimes IAM itself, and SCPs apply even to
an account's root user.
