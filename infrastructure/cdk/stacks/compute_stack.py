from aws_cdk import Duration, Stack
from aws_cdk import aws_autoscaling as autoscaling
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_elasticloadbalancingv2 as elbv2
from aws_cdk import aws_iam as iam
from aws_cdk import aws_rds as rds
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_s3_assets as s3_assets
from aws_cdk import aws_secretsmanager as secretsmanager
from constructs import Construct


class ComputeStack(Stack):
    """Launch template, ASG, ALB, target group, and the IAM instance
    role. Every permission the instance role gets is a `.grant_*()`
    call on the actual DynamoDB table / S3 bucket / RDS secret object
    passed in -- never a hand-written ARN string, so it can't drift
    from what those resources actually are.

    modern-app's code is packaged as a CDK asset (zipped and uploaded
    to the CDK bootstrap bucket automatically on `cdk deploy`) instead
    of a manual `tar` + `aws s3 cp` step. User data downloads it from
    there and does the same venv + systemd setup as the hand-built
    version's `modern-app/deploy/ec2-user-data.sh`, but every value in
    it -- the DB endpoint, the secret ARN, the table/bucket names -- is
    a live reference to the resource CDK just created, not a copied
    string.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        vpc: ec2.Vpc,
        app_security_group: ec2.SecurityGroup,
        alb_security_group: ec2.SecurityGroup,
        db_instance: rds.DatabaseInstance,
        sessions_table: dynamodb.Table,
        uploads_bucket: s3.Bucket,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        app_asset = s3_assets.Asset(
            self, "ModernAppAsset", path="../../modern-app"
        )

        flask_secret = secretsmanager.Secret(
            self,
            "FlaskSecretKey",
            description="modern-app Flask session-signing key",
            generate_secret_string=secretsmanager.SecretStringGenerator(
                exclude_punctuation=True, password_length=48
            ),
        )

        role = iam.Role(
            self,
            "AppInstanceRole",
            role_name="smb-migration-demo-app-role",
            assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "AmazonSSMManagedInstanceCore"
                )
            ],
        )
        sessions_table.grant_read_write_data(role)
        uploads_bucket.grant_read_write(role)
        db_instance.secret.grant_read(role)
        flask_secret.grant_read(role)
        app_asset.grant_read(role)

        user_data = ec2.UserData.for_linux()
        user_data.add_commands(
            "dnf install -y python3-pip unzip",
            "mkdir -p /home/ec2-user/app-deploy/modern-app",
            f"aws s3 cp s3://{app_asset.s3_bucket_name}/{app_asset.s3_object_key} "
            f"/tmp/modern-app.zip --region {Stack.of(self).region}",
            "cd /home/ec2-user/app-deploy/modern-app && unzip -q /tmp/modern-app.zip",
            "chown -R ec2-user:ec2-user /home/ec2-user/app-deploy",
            "cd /home/ec2-user/app-deploy/modern-app",
            "python3 -m venv .venv",
            "./.venv/bin/pip install -q --upgrade pip",
            "./.venv/bin/pip install -q -r requirements.txt",
            "cat > /etc/systemd/system/modern-app.service << 'UNIT'",
            "[Unit]",
            "Description=SMB modern invoice tracker (stateless)",
            "After=network.target",
            "",
            "[Service]",
            "Type=simple",
            "WorkingDirectory=/home/ec2-user/app-deploy/modern-app",
            f"Environment=AWS_REGION={Stack.of(self).region}",
            f"Environment=DB_HOST={db_instance.instance_endpoint.hostname}",
            f"Environment=DB_PORT={db_instance.instance_endpoint.port}",
            "Environment=DB_NAME=smb_migration_demo",
            "Environment=DB_USER=app_user",
            f"Environment=DB_PASSWORD_SECRET_ARN={db_instance.secret.secret_arn}",
            f"Environment=SESSION_DYNAMODB_TABLE={sessions_table.table_name}",
            f"Environment=S3_UPLOAD_BUCKET={uploads_bucket.bucket_name}",
            f"Environment=SECRET_KEY_SECRET_ARN={flask_secret.secret_arn}",
            "Environment=FLASK_DEBUG=0",
            "ExecStart=/home/ec2-user/app-deploy/modern-app/.venv/bin/python "
            "/home/ec2-user/app-deploy/modern-app/app.py",
            "Restart=on-failure",
            "",
            "[Install]",
            "WantedBy=multi-user.target",
            "UNIT",
            # Seed the database (creates schema + admin user, safe to
            # re-run since seed.py only inserts if empty) before
            # starting the app, so the first request never hits a
            # missing-table error. Runs on every instance boot,
            # including scale-up and replacement, which is fine since
            # it's a no-op once already seeded.
            "grep Environment= /etc/systemd/system/modern-app.service > /tmp/envs.txt",
            "while IFS= read -r line; do export \"${line#Environment=}\"; done < /tmp/envs.txt",
            "./.venv/bin/python seed.py || true",
            "systemctl daemon-reload",
            "systemctl enable --now modern-app",
        )

        launch_template = ec2.LaunchTemplate(
            self,
            "AppLaunchTemplate",
            launch_template_name="smb-migration-demo-lt",
            machine_image=ec2.MachineImage.latest_amazon_linux2023(),
            instance_type=ec2.InstanceType.of(
                ec2.InstanceClass.BURSTABLE3, ec2.InstanceSize.MICRO
            ),
            security_group=app_security_group,
            role=role,
            require_imdsv2=True,
            user_data=user_data,
        )

        alb = elbv2.ApplicationLoadBalancer(
            self,
            "Alb",
            load_balancer_name="smb-migration-demo-alb",
            vpc=vpc,
            internet_facing=True,
            security_group=alb_security_group,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
        )

        target_group = elbv2.ApplicationTargetGroup(
            self,
            "AppTargetGroup",
            target_group_name="smb-migration-demo-tg",
            vpc=vpc,
            port=5000,
            protocol=elbv2.ApplicationProtocol.HTTP,
            target_type=elbv2.TargetType.INSTANCE,
            health_check=elbv2.HealthCheck(
                path="/login",
                healthy_threshold_count=2,
                unhealthy_threshold_count=2,
                interval=Duration.seconds(10),
                timeout=Duration.seconds(5),
            ),
        )
        alb.add_listener(
            "HttpListener", port=80, default_target_groups=[target_group]
        )

        self.asg = autoscaling.AutoScalingGroup(
            self,
            "AppAsg",
            auto_scaling_group_name="smb-migration-demo-asg",
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
            launch_template=launch_template,
            min_capacity=1,
            max_capacity=2,
            health_checks=autoscaling.HealthChecks.with_additional_checks(
                grace_period=Duration.seconds(300),
                additional_types=[autoscaling.AdditionalHealthCheckType.ELB],
            ),
        )
        self.asg.attach_to_application_target_group(target_group)

        self.alb = alb
        self.target_group = target_group
