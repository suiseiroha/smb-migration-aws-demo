from aws_cdk import Stack
from aws_cdk import aws_ec2 as ec2
from constructs import Construct


class NetworkStack(Stack):
    """VPC, 3 subnet tiers across 2 AZs, and the tier-to-tier security
    groups. Mirrors the hand-built Phase 1 network exactly: 10.0.0.0/16,
    public/app/db subnets, one NAT Gateway (not one per AZ -- cost
    decision, matches the manual build) shared by both app subnets.
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.vpc = ec2.Vpc(
            self,
            "Vpc",
            vpc_name="smb-migration-demo-vpc",
            ip_addresses=ec2.IpAddresses.cidr("10.0.0.0/16"),
            max_azs=2,
            nat_gateways=1,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24,
                ),
                ec2.SubnetConfiguration(
                    name="app",
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                    cidr_mask=24,
                ),
                ec2.SubnetConfiguration(
                    name="db",
                    subnet_type=ec2.SubnetType.PRIVATE_ISOLATED,
                    cidr_mask=24,
                ),
            ],
        )

        self.alb_security_group = ec2.SecurityGroup(
            self,
            "AlbSecurityGroup",
            vpc=self.vpc,
            security_group_name="smb-migration-demo-alb-sg",
            description="ALB security group",
            allow_all_outbound=True,
        )
        self.alb_security_group.add_ingress_rule(
            ec2.Peer.any_ipv4(), ec2.Port.tcp(80), "HTTP from internet"
        )

        self.app_security_group = ec2.SecurityGroup(
            self,
            "AppSecurityGroup",
            vpc=self.vpc,
            security_group_name="smb-migration-demo-app-sg",
            description="App instance security group",
            allow_all_outbound=True,
        )
        self.app_security_group.add_ingress_rule(
            self.alb_security_group, ec2.Port.tcp(5000), "App traffic from the ALB only"
        )

        self.db_security_group = ec2.SecurityGroup(
            self,
            "DbSecurityGroup",
            vpc=self.vpc,
            security_group_name="smb-migration-demo-db-sg",
            description="RDS security group",
            allow_all_outbound=False,
        )
        self.db_security_group.add_ingress_rule(
            self.app_security_group, ec2.Port.tcp(3306), "MySQL from the app tier only"
        )
