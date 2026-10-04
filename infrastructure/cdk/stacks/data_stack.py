from aws_cdk import Duration, RemovalPolicy, Stack
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_rds as rds
from aws_cdk import aws_s3 as s3
from constructs import Construct


class DataStack(Stack):
    """RDS (Single-AZ MySQL), the sessions DynamoDB table, and the
    uploads S3 bucket. RDS credentials are auto-generated into Secrets
    Manager by CDK -- no manual `aws ssm put-parameter` step needed,
    unlike the hand-built version. Instance role permissions are
    granted later in ComputeStack via `.grant_*()` calls on the actual
    objects created here, never a hardcoded ARN.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        vpc: ec2.Vpc,
        db_security_group: ec2.SecurityGroup,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.db_instance = rds.DatabaseInstance(
            self,
            "Database",
            instance_identifier="smb-migration-demo-db",
            engine=rds.DatabaseInstanceEngine.mysql(
                version=rds.MysqlEngineVersion.VER_8_0_46
            ),
            instance_type=ec2.InstanceType.of(
                ec2.InstanceClass.BURSTABLE3, ec2.InstanceSize.MICRO
            ),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_ISOLATED),
            security_groups=[db_security_group],
            credentials=rds.Credentials.from_generated_secret("app_user"),
            database_name="smb_migration_demo",
            multi_az=False,  # cost decision -- Single-AZ, matches the manual build
            allocated_storage=20,
            storage_encrypted=True,
            backup_retention=Duration.days(7),
            publicly_accessible=False,
            # Snapshot automatically on `cdk destroy` instead of requiring
            # a manual snapshot step first -- automates Milestone 7.
            removal_policy=RemovalPolicy.SNAPSHOT,
        )

        self.sessions_table = dynamodb.Table(
            self,
            "SessionsTable",
            table_name="smb-migration-demo-sessions",
            partition_key=dynamodb.Attribute(
                name="session_id", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            time_to_live_attribute="expires_at",
            removal_policy=RemovalPolicy.DESTROY,
        )

        self.uploads_bucket = s3.Bucket(
            self,
            "UploadsBucket",
            bucket_name="smb-migration-demo-uploads",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )
