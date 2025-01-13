#!/bin/bash

# Function to load .env file and substitute variables
load_env() {
    if [ -f .env ]; then
        export $(cat .env | sed 's/#.*//g' | xargs)

        # If task definition template exists, substitute variables
        if [ -f deployment/ecs/task-definition.template.json ]; then
            template=$(cat deployment/ecs/task-definition.template.json)
            output=$(echo "$template" | \
                sed "s|\${AWS_REGION}|$AWS_REGION|g" | \
                sed "s|\${AWS_ACCOUNT_ID}|$AWS_ACCOUNT_ID|g" | \
                sed "s|\${DB_HOST}|$DB_HOST|g" | \
                sed "s|\${DB_PORT}|$DB_PORT|g" | \
                sed "s|\${DB_NAME}|$DB_NAME|g" | \
                sed "s|\${AUTH_APP_NAME}|$AUTH_APP_NAME|g" | \
                sed "s|\${AUTH_SERVICE_URL}|$AUTH_SERVICE_URL|g" | \
                sed "s|\${ORGANIZATIONS_SERVICE_URL}|$ORGANIZATIONS_SERVICE_URL|g" | \
                sed "s|\${METRICS_SERVICE_URL}|$METRICS_SERVICE_URL|g" | \
                sed "s|\${NARRATIVE_SERVICE_URL}|$NARRATIVE_SERVICE_URL|g" | \
                sed "s|\${CHATBOT_SERVICE_URL}|$CHATBOT_SERVICE_URL|g" | \
                sed "s|\${DATA_SOURCE_SERVICE_URL}|$DATA_SOURCE_SERVICE_URL|g" | \
                sed "s|\${METRIC_DISCOVERY_SERVICE_URL}|$METRIC_DISCOVERY_SERVICE_URL|g")

            echo "$output" > deployment/ecs/task-definition.json
        fi
    else
        echo ".env file not found"
        exit 1
    fi
}