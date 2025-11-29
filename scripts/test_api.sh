#!/bin/bash

# ==============================================
# APK Extractor - API Test Script
# ==============================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# Configuration
BASE_URL="${BASE_URL:-http://localhost:8000}"
USERNAME="${USERNAME:-admin}"
PASSWORD="${PASSWORD:-apkextractor}"
TEST_PACKAGE="${TEST_PACKAGE:-com.android.chrome}"

echo -e "${CYAN}=============================================="
echo "APK Extractor - API Tests"
echo -e "==============================================${NC}"
echo ""
echo "Base URL: $BASE_URL"
echo "Test Package: $TEST_PACKAGE"
echo ""

# Function to make authenticated request
auth_curl() {
    curl -s -u "$USERNAME:$PASSWORD" "$@"
}

# Function to check response
check_response() {
    local response="$1"
    local expected="$2"
    local test_name="$3"
    
    if echo "$response" | grep -q "$expected"; then
        echo -e "${GREEN}✓ $test_name${NC}"
        return 0
    else
        echo -e "${RED}✗ $test_name${NC}"
        echo "  Response: $response"
        return 1
    fi
}

PASSED=0
FAILED=0

# ===========================================
# Test 1: Health Check
# ===========================================
echo -e "\n${YELLOW}Test 1: Health Check${NC}"

response=$(auth_curl "$BASE_URL/api/health")
if check_response "$response" "healthy\|orchestrator" "Health endpoint responds"; then
    ((PASSED++))
else
    ((FAILED++))
fi

# ===========================================
# Test 2: Invalid Package Name
# ===========================================
echo -e "\n${YELLOW}Test 2: Invalid Package Name${NC}"

response=$(auth_curl -X POST "$BASE_URL/api/extract" \
    -H "Content-Type: application/json" \
    -d '{"package": "invalid name"}')

if check_response "$response" "Invalid\|error" "Rejects invalid package name"; then
    ((PASSED++))
else
    ((FAILED++))
fi

# ===========================================
# Test 3: Empty Package Name
# ===========================================
echo -e "\n${YELLOW}Test 3: Empty Package Name${NC}"

response=$(auth_curl -X POST "$BASE_URL/api/extract" \
    -H "Content-Type: application/json" \
    -d '{"package": ""}')

if check_response "$response" "required\|error" "Rejects empty package name"; then
    ((PASSED++))
else
    ((FAILED++))
fi

# ===========================================
# Test 4: Extract Package (if installed)
# ===========================================
echo -e "\n${YELLOW}Test 4: Extract APK${NC}"
echo "  Package: $TEST_PACKAGE"
echo "  (This may take a while...)"

response=$(auth_curl -X POST "$BASE_URL/api/extract" \
    -H "Content-Type: application/json" \
    -d "{\"package\": \"$TEST_PACKAGE\"}" \
    --max-time 180)

# Check for success or queued (orchestrator mode)
if echo "$response" | grep -q "completed\|queued\|files"; then
    echo -e "${GREEN}✓ Extraction request accepted${NC}"
    ((PASSED++))
    
    # If queued, check status
    if echo "$response" | grep -q "job_id"; then
        job_id=$(echo "$response" | grep -o '"job_id":"[^"]*"' | cut -d'"' -f4)
        echo "  Job ID: $job_id"
        
        # Poll for completion
        echo "  Waiting for completion..."
        for i in {1..60}; do
            sleep 3
            status_response=$(auth_curl "$BASE_URL/api/status/$job_id")
            
            if echo "$status_response" | grep -q "completed"; then
                echo -e "${GREEN}✓ Job completed${NC}"
                response="$status_response"
                break
            elif echo "$status_response" | grep -q "failed"; then
                echo -e "${RED}✗ Job failed${NC}"
                echo "  $status_response"
                break
            fi
            
            echo -ne "  Polling... ($i/60)\r"
        done
    fi
    
    # Extract file info
    if echo "$response" | grep -q "files"; then
        echo "  Files extracted:"
        echo "$response" | grep -o '"filename":"[^"]*"' | while read line; do
            filename=$(echo "$line" | cut -d'"' -f4)
            echo "    - $filename"
        done
    fi
else
    echo -e "${YELLOW}⚠ Extraction result: $response${NC}"
    # Not installed is not necessarily a failure
    if echo "$response" | grep -q "not installed"; then
        echo "  (App not installed - this is expected if app isn't on the device)"
    else
        ((FAILED++))
    fi
fi

# ===========================================
# Test 5: List Packages
# ===========================================
echo -e "\n${YELLOW}Test 5: List Packages${NC}"

response=$(auth_curl "$BASE_URL/api/packages")

if check_response "$response" "packages" "List packages endpoint responds"; then
    ((PASSED++))
    count=$(echo "$response" | grep -o '"total_packages":[0-9]*' | cut -d':' -f2)
    echo "  Packages available: ${count:-0}"
else
    ((FAILED++))
fi

# ===========================================
# Test 6: Download (if file exists)
# ===========================================
echo -e "\n${YELLOW}Test 6: Download APK${NC}"

# Try to download a file (may not exist)
http_code=$(curl -s -o /dev/null -w "%{http_code}" \
    -u "$USERNAME:$PASSWORD" \
    "$BASE_URL/api/download/$TEST_PACKAGE/base.apk")

if [ "$http_code" = "200" ]; then
    echo -e "${GREEN}✓ Download endpoint works (200)${NC}"
    ((PASSED++))
elif [ "$http_code" = "404" ]; then
    echo -e "${YELLOW}⚠ File not found (404) - expected if not extracted${NC}"
else
    echo -e "${RED}✗ Unexpected response code: $http_code${NC}"
    ((FAILED++))
fi

# ===========================================
# Test 7: Authentication Required
# ===========================================
echo -e "\n${YELLOW}Test 7: Authentication Required${NC}"

response=$(curl -s "$BASE_URL/api/extract" \
    -X POST \
    -H "Content-Type: application/json" \
    -d '{"package": "com.test"}')

# Should redirect to login or return 401
http_code=$(curl -s -o /dev/null -w "%{http_code}" \
    "$BASE_URL/api/health")

if [ "$http_code" = "401" ] || [ "$http_code" = "302" ]; then
    echo -e "${GREEN}✓ Unauthenticated requests rejected${NC}"
    ((PASSED++))
else
    echo -e "${YELLOW}⚠ Auth may be disabled (code: $http_code)${NC}"
fi

# ===========================================
# Summary
# ===========================================
echo -e "\n${CYAN}=============================================="
echo "Test Summary"
echo -e "==============================================${NC}"
echo -e "${GREEN}Passed: $PASSED${NC}"
echo -e "${RED}Failed: $FAILED${NC}"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}All tests passed!${NC}"
    exit 0
else
    echo -e "${RED}Some tests failed.${NC}"
    exit 1
fi

