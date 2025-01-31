#!/bin/bash
set -e  # Exit on error

# Load environment variables
source deployment/scripts/load-env.sh
load_env

# Register new task definition
echo "Registering new task definition..."
TASK_DEFINITION_ARN=$(aws ecs register-task-definition \
    --cli-input-json file://deployment/ecs/task-definition.json \
    --query 'taskDefinition.taskDefinitionArn' \
    --output text)

echo "Task definition registered: $TASK_DEFINITION_ARN"

echo "Creating ECS service..."
aws ecs create-service \
    --cluster ${AUTH_CLUSTER_NAME} \
    --service-name backend-authorization-gateway-service \
    --task-definition backend-authorization-gateway \
    --desired-count 1 \
    --launch-type FARGATE \
    --network-configuration "awsvpcConfiguration={subnets=[${VPC_SUBNET_1},${VPC_SUBNET_2}],securityGroups=[${SECURITY_GROUP}],assignPublicIp=ENABLED}" \
    --load-balancers "targetGroupArn=${AUTH_TARGET_GROUP_ARN},containerName=backend-authorization-gateway,containerPort=8000" \
    --health-check-grace-period-seconds 120 \
    --region eu-north-1

echo "Waiting for service to become stable..."
aws ecs wait services-stable \
    --cluster ${AUTH_CLUSTER_NAME} \
    --services backend-authorization-gateway-service \
    --region eu-north-1

echo "Service created successfully!"