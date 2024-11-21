#!/bin/bash

# Service URLs
GATEWAY_URL="http://backend-authorization-gatewa-alb-1180704430.eu-north-1.elb.amazonaws.com"
NARRATIVE_URL="http://backend-narrative-and-dataso-alb-338209897.eu-north-1.elb.amazonaws.com"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "🚀 Testing deployed microservices..."

# Get token
echo -e "\n1️⃣  Getting auth token..."
LOGIN_RESPONSE=$(curl -s -X POST "${GATEWAY_URL}/authorization/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin@othor.ai" \
  -d "password=admin")

TOKEN=$(echo $LOGIN_RESPONSE | jq -r '.access_token')

if [ -z "$TOKEN" ] || [ "$TOKEN" = "null" ]; then
    echo -e "${RED}❌ Failed to get token${NC}"
    echo "Login Response: $LOGIN_RESPONSE"
    exit 1
else
    echo -e "${GREEN}✅ Token received${NC}"
    echo "Token: ${TOKEN:0:50}..."
fi

# Function to test endpoint with verbose output
test_endpoint() {
    local name=$1
    local url=$2
    local method=${3:-GET}
    shift 3
    local extra_headers=("$@")

    echo -e "\n${YELLOW}🔍 Testing $name...${NC}"
    echo "URL: $url"
    echo "Method: $method"
    echo "Headers:"
    echo "  Authorization: Bearer ${TOKEN:0:20}..."
    
    # Build curl command with headers
    CURL_CMD="curl -v -s -X $method \"$url\" -H \"Authorization: Bearer $TOKEN\" -H \"Content-Type: application/json\""
    
    # Add extra headers if provided
    for header in "${extra_headers[@]}"; do
        CURL_CMD="$CURL_CMD -H \"$header\""
    done
    
    # Execute curl command
    RESPONSE=$(eval $CURL_CMD 2>&1)

    echo -e "\nResponse:"
    echo "$RESPONSE"
    
    HTTP_CODE=$(echo "$RESPONSE" | grep "< HTTP/" | awk '{print $3}')
    echo -e "\nHTTP Code: $HTTP_CODE"
    
    if [[ "$HTTP_CODE" =~ ^2[0-9][0-9]$ ]]; then
        echo -e "${GREEN}✅ Success${NC}"
    else
        echo -e "${RED}❌ Failed${NC}"
    fi
}

# Test Gateway routes
echo -e "\n${YELLOW}Testing Gateway Routes${NC}"
test_endpoint "Gateway Health" "${GATEWAY_URL}/health"
test_endpoint "Narrative through Gateway" "${GATEWAY_URL}/narrative/health"
test_endpoint "Narrative Feed" "${GATEWAY_URL}/narrative/feed"

# Test Direct Service
echo -e "\n${YELLOW}Testing Direct Service${NC}"
test_endpoint "Direct Narrative" "${NARRATIVE_URL}/health" "GET" \
    "X-User-ID: 123" \
    "X-Organization-ID: 456" \
    "X-User-Role: admin"