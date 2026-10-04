"""Defines the multi-account landing zone from docs/landing-zone.md as
code: the Security and Workloads OUs, the Log Archive and Audit member
accounts, and the Workloads OU's SCP.

This is a separate CDK app from infrastructure/cdk/ on purpose. That
one deploys the workload itself, inside whatever account it runs
against. This one has to run from the Management account specifically,
before the workload account even exists as a landing-zone member, so
bundling the two into one `cdk deploy --all` would be wrong: this
stack targets the organization's root, not a single workload.

CDK has no L2 (higher-level) constructs for AWS Organizations, only the
L1 Cfn* resources that map directly to CloudFormation. That is a real
AWS limitation, not a gap in this code: Organizations resources are
still comparatively new to CloudFormation and L2 constructs haven't
caught up yet.

Not deployed. See docs/landing-zone.md for why this stays a design
until the decision to actually stand up Organizations is made
separately.
"""
import json
from pathlib import Path

from aws_cdk import Stack
from aws_cdk import aws_organizations as organizations
from constructs import Construct

SCP_PATH = Path(__file__).resolve().parent.parent.parent / "smb-migration-demo-scp-workloads.json"


class LandingZoneStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        root_id = self.node.try_get_context("organization_root_id")
        log_archive_email = self.node.try_get_context("log_archive_email")
        audit_email = self.node.try_get_context("audit_email")

        if not root_id or not log_archive_email or not audit_email:
            raise ValueError(
                "Pass organization_root_id, log_archive_email, and "
                "audit_email via --context, for example:\n"
                "  cdk synth \\\n"
                "    --context organization_root_id=$(aws organizations list-roots --query 'Roots[0].Id' --output text) \\\n"
                "    --context log_archive_email=you+logarchive@example.com \\\n"
                "    --context audit_email=you+audit@example.com\n"
                "organization_root_id only exists once Phase 1 in "
                "docs/landing-zone.md (Create an organization) has "
                "already been done by hand, this stack builds on top "
                "of that, it doesn't create the organization itself."
            )

        security_ou = organizations.CfnOrganizationalUnit(
            self, "SecurityOU",
            name="Security",
            parent_id=root_id,
        )

        workloads_ou = organizations.CfnOrganizationalUnit(
            self, "WorkloadsOU",
            name="Workloads",
            parent_id=root_id,
        )

        organizations.CfnAccount(
            self, "LogArchiveAccount",
            account_name="smb-migration-demo-log-archive",
            email=log_archive_email,
            parent_ids=[security_ou.attr_id],
        )

        organizations.CfnAccount(
            self, "AuditAccount",
            account_name="smb-migration-demo-audit",
            email=audit_email,
            parent_ids=[security_ou.attr_id],
        )

        # Read from the existing real policy file (infrastructure/landing-zone/
        # smb-migration-demo-scp-workloads.json) instead of duplicating the
        # policy content here, one source of truth either way this gets
        # applied, by hand or as code.
        scp_content = json.loads(SCP_PATH.read_text())

        organizations.CfnPolicy(
            self, "WorkloadsScp",
            name="smb-migration-demo-scp-workloads",
            description="Region lock and leave-org block for workload accounts",
            type="SERVICE_CONTROL_POLICY",
            content=scp_content,
            target_ids=[workloads_ou.attr_id],
        )
