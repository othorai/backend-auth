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

# Update service with desired count 1
echo "Updating service..."
aws ecs update-service \
    --cluster "${AUTH_CLUSTER_NAME}" \
    --service backend-authorization-gateway-service \
    --task-definition "${TASK_DEFINITION_ARN}" \
    --desired-count 1 \
    --force-new-deployment

# Wait for deployment
echo "Waiting for service to stabilize..."
aws ecs wait services-stable \
    --cluster "${AUTH_CLUSTER_NAME}" \
    --services backend-authorization-gateway-service

# Get the latest task ARN
TASK_ARN=$(aws ecs list-tasks \
    --cluster "${AUTH_CLUSTER_NAME}" \
    --service-name backend-authorization-gateway-service \
    --desired-status RUNNING \
    --query 'taskArns[0]' \
    --output text)

# If no running task, check stopped tasks
if [ "$TASK_ARN" == "None" ]; then
    echo "No running tasks found. Checking stopped tasks..."
    TASK_ARN=$(aws ecs list-tasks \
        --cluster "${AUTH_CLUSTER_NAME}" \
        --service-name backend-authorization-gateway-service \
        --desired-status STOPPED \
        --query 'taskArns[0]' \
        --output text)
fi

if [ "$TASK_ARN" != "None" ]; then
    echo "Fetching logs for task: $TASK_ARN"
    aws ecs describe-tasks \
        --cluster "${AUTH_CLUSTER_NAME}" \
        --tasks "$TASK_ARN"
    
    # Get CloudWatch logs
    TASK_ID=$(echo $TASK_ARN | cut -d'/' -f3)
    echo "Fetching CloudWatch logs..."
    aws logs get-log-events \
        --log-group-name "/ecs/${AUTH_APP_NAME}" \
        --log-stream-name "ecs/backend-authorization-gateway/${TASK_ID}" \
        --query 'events[*].message' \
        --output text
fi

echo "Deployment complete!"