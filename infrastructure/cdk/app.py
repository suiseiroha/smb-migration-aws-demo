#!/usr/bin/env python3
import aws_cdk as cdk

from stacks.compute_stack import ComputeStack
from stacks.data_stack import DataStack
from stacks.monitoring_stack import MonitoringStack
from stacks.network_stack import NetworkStack

app = cdk.App()

env = cdk.Environment(region="ap-southeast-1")
tags = {"Project": "smb-migration-demo"}

network = NetworkStack(app, "SmbMigrationDemo-Network", env=env, tags=tags)

data = DataStack(
    app,
    "SmbMigrationDemo-Data",
    env=env,
    tags=tags,
    vpc=network.vpc,
    db_security_group=network.db_security_group,
)

compute = ComputeStack(
    app,
    "SmbMigrationDemo-Compute",
    env=env,
    tags=tags,
    vpc=network.vpc,
    app_security_group=network.app_security_group,
    alb_security_group=network.alb_security_group,
    db_instance=data.db_instance,
    sessions_table=data.sessions_table,
    uploads_bucket=data.uploads_bucket,
)

MonitoringStack(
    app,
    "SmbMigrationDemo-Monitoring",
    env=env,
    tags=tags,
    asg=compute.asg,
    db_instance=data.db_instance,
    alb=compute.alb,
    target_group=compute.target_group,
)

app.synth()
