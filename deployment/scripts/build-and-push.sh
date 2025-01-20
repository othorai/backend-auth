#!/bin/bash

set -e  # Exit on error

# Load environment variables
source deployment/scripts/load-env.sh
load_env

# Function to handle errors
handle_error() {
    echo "Error: $1"
    exit 1
}

# Login to ECR
echo "Logging in to ECR..."
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com || handle_error "Failed to login to ECR"

# Build and push the image directly
echo "Building and pushing Docker image..."
docker buildx build \
    --platform linux/amd64 \
    --push \
    --build-arg DB_HOST=$DB_HOST \
    --build-arg DB_PORT=$DB_PORT \
    --build-arg DB_NAME=$DB_NAME \
    --build-arg DB_NAME=$DB_SSLMODE \
    --build-arg SERVICE_KEY_SALT=$SERVICE_KEY_SALT \
    --build-arg NARRATIVE_SERVICE_URL=$NARRATIVE_SERVICE_URL \
    --build-arg CHATBOT_SERVICE_URL=$CHATBOT_SERVICE_URL \
    --build-arg METRIC_DISCOVERY_SERVICE_URL=$METRIC_DISCOVERY_SERVICE_URL \
    --build-arg METRICS_SERVICE_URL=$METRICS_SERVICE_URL \
    --build-arg ORGANIZATIONS_SERVICE_URL=$ORGANIZATIONS_SERVICE_URL \
    --build-arg DATA_SOURCE_SERVICE_URL=$DATA_SOURCE_SERVICE_URL \
    -t $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$AUTH_APP_NAME:latest \
    -f deployment/Dockerfile . || handle_error "Failed to build and push image"

echo "Build and push complete!"