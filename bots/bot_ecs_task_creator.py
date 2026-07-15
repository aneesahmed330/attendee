import logging
import os

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class BotEcsTaskCreator:
    def __init__(self):
        self.cluster = os.getenv("ECS_CLUSTER_NAME", "meeting-joiner-cluster")
        self.task_definition = os.getenv("ECS_BOT_TASK_DEFINITION", "meeting-joiner-bot")
        self.container_name = os.getenv("ECS_BOT_CONTAINER_NAME", "bot-proc")
        self.subnets = [s.strip() for s in os.getenv("ECS_BOT_SUBNETS", "").split(",") if s.strip()]
        self.security_groups = [s.strip() for s in os.getenv("ECS_BOT_SECURITY_GROUPS", "").split(",") if s.strip()]
        # Subnet is public with no NAT gateway, so the task needs a public IP to
        # reach ECR/pull its image and to reach the outside world (Graph API,
        # Gemini, Teams webhooks). Postgres/Redis/orchestrator stay reachable
        # over the private IP within the VPC regardless.
        self.assign_public_ip = os.getenv("ECS_BOT_ASSIGN_PUBLIC_IP", "ENABLED")
        self.client = boto3.client("ecs", region_name=os.getenv("AWS_DEFAULT_REGION", "us-east-1"))

    def create_bot_task(self, bot_id, bot_name=None):
        if not self.subnets or not self.security_groups:
            raise ValueError("ECS_BOT_SUBNETS and ECS_BOT_SECURITY_GROUPS must be set to launch bots via ECS Fargate")

        try:
            response = self.client.run_task(
                cluster=self.cluster,
                taskDefinition=self.task_definition,
                launchType="FARGATE",
                count=1,
                networkConfiguration={
                    "awsvpcConfiguration": {
                        "subnets": self.subnets,
                        "securityGroups": self.security_groups,
                        "assignPublicIp": self.assign_public_ip,
                    }
                },
                overrides={
                    "containerOverrides": [
                        {
                            "name": self.container_name,
                            "command": ["python", "manage.py", "run_bot", "--botid", str(bot_id)],
                        }
                    ]
                },
                startedBy=(bot_name or f"bot-{bot_id}")[:36],
                tags=[{"key": "bot_id", "value": str(bot_id)}],
            )
        except ClientError as e:
            logger.error(f"Failed to launch ECS Fargate task for bot {bot_id}: {e}")
            return {"created": False, "error": str(e)}

        failures = response.get("failures", [])
        if failures:
            logger.error(f"ECS RunTask returned failures for bot {bot_id}: {failures}")
            return {"created": False, "error": str(failures)}

        tasks = response.get("tasks", [])
        if not tasks:
            return {"created": False, "error": "ECS RunTask returned no tasks and no failures"}

        task_arn = tasks[0]["taskArn"]
        logger.info(f"Launched ECS Fargate task {task_arn} for bot {bot_id}")
        return {"created": True, "task_arn": task_arn}

    def stop_bot_task(self, task_arn, reason="Bot stopped"):
        try:
            self.client.stop_task(cluster=self.cluster, task=task_arn, reason=reason)
            return {"stopped": True}
        except ClientError as e:
            logger.error(f"Failed to stop ECS task {task_arn}: {e}")
            return {"stopped": False, "error": str(e)}
