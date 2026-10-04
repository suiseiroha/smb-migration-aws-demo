#!/usr/bin/env python3
import aws_cdk as cdk

from stacks.landing_zone_stack import LandingZoneStack

app = cdk.App()

LandingZoneStack(
    app, "SmbMigrationDemo-LandingZone",
    env=cdk.Environment(region="ap-southeast-1"),
    tags={"Project": "smb-migration-demo"},
)

app.synth()
