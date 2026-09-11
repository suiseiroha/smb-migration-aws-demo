from aws_cdk import Duration, Stack
from aws_cdk import aws_autoscaling as autoscaling
from aws_cdk import aws_cloudwatch as cloudwatch
from aws_cdk import aws_elasticloadbalancingv2 as elbv2
from aws_cdk import aws_rds as rds
from constructs import Construct


class MonitoringStack(Stack):
    """Dashboard + alarms. Every metric here is built from the actual
    resource object (`db_instance.metric_free_storage_space()`,
    `alb.metrics.request_count()`, etc., or the live
    `asg.auto_scaling_group_name` token for the one metric ASG has no
    built-in helper for) -- CDK fills in the right namespace/dimensions
    itself, so there's no metric name/dimension string to keep in sync
    by hand.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        asg: autoscaling.AutoScalingGroup,
        db_instance: rds.DatabaseInstance,
        alb: elbv2.ApplicationLoadBalancer,
        target_group: elbv2.ApplicationTargetGroup,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ASG has no built-in CPU metric helper (unlike RDS/ALB below) --
        # still built from the live `asg.auto_scaling_group_name` token,
        # never a hardcoded name.
        cpu_metric = cloudwatch.Metric(
            namespace="AWS/EC2",
            metric_name="CPUUtilization",
            dimensions_map={"AutoScalingGroupName": asg.auto_scaling_group_name},
            statistic="Average",
            period=Duration.minutes(5),
        )
        storage_metric = db_instance.metric_free_storage_space(period=Duration.minutes(5))

        dashboard = cloudwatch.Dashboard(
            self, "Dashboard", dashboard_name="smb-migration-demo-dashboard"
        )
        dashboard.add_widgets(
            cloudwatch.GraphWidget(title="ASG Average CPU", left=[cpu_metric]),
            cloudwatch.GraphWidget(title="RDS Free Storage Space", left=[storage_metric]),
            cloudwatch.GraphWidget(
                title="ALB Request Count", left=[alb.metrics.request_count()]
            ),
            cloudwatch.GraphWidget(
                title="ALB Target Response Time",
                left=[target_group.metrics.target_response_time()],
            ),
        )

        cloudwatch.Alarm(
            self,
            "AsgHighCpuAlarm",
            alarm_name="smb-migration-demo-asg-high-cpu",
            metric=cpu_metric,
            threshold=70,
            evaluation_periods=2,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
        )

        cloudwatch.Alarm(
            self,
            "RdsLowStorageAlarm",
            alarm_name="smb-migration-demo-rds-low-storage",
            metric=storage_metric,
            threshold=2 * 1024 * 1024 * 1024,  # 2 GB, bytes
            evaluation_periods=1,
            comparison_operator=cloudwatch.ComparisonOperator.LESS_THAN_THRESHOLD,
        )
