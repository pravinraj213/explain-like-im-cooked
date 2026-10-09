#!/bin/bash

# Explain Like I'm Cooked - Complete Setup Script
# Creates the IAM role, policy, and deploys the Lambda function in ap-south-1

set -e

echo "=== Explain Like I'm Cooked: Infrastructure Setup ==="
echo ""

# Check prerequisites
if ! command -v aws &> /dev/null; then
    echo "[ERROR] AWS CLI not found. Please install it first."
    exit 1
fi

if ! command -v jq &> /dev/null; then
    echo "[ERROR] jq not found. Please install it first."
    exit 1
fi

echo "[OK] Prerequisites found."

# Variables
ROLE_NAME="explain-like-im-cooked-role"
POLICY_NAME="explain-like-im-cooked-policy"
FUNCTION_NAME="explain-like-im-cooked"
REGION="${AWS_REGION:-ap-south-1}"
RUNTIME="python3.12"
HANDLER="lambda_function.lambda_handler"
TIMEOUT=30
MEMORY=512

# Get AWS Account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo "[INFO] AWS Account ID: $ACCOUNT_ID"
echo "[INFO] Target Region: $REGION"
echo "[INFO] Function Name: $FUNCTION_NAME"
echo ""

# Create IAM Role
echo "[STEP 1/3] Creating IAM execution role..."
ROLE_ARN=$(aws iam get-role --role-name "$ROLE_NAME" --query 'Role.Arn' --output text 2>/dev/null || echo "")

if [ -z "$ROLE_ARN" ]; then
    echo "Creating role: $ROLE_NAME"
    ROLE_ARN=$(aws iam create-role \
        --role-name "$ROLE_NAME" \
        --assume-role-policy-document file://trust-policy.json \
        --query 'Role.Arn' \
        --output text)
    echo "[OK] Created role: $ROLE_ARN"
    
    echo "Waiting 10 seconds for IAM propagation..."
    sleep 10
else
    echo "[OK] Existing role found: $ROLE_ARN"
fi

# Attach policy to role
echo ""
echo "[STEP 2/3] Configuring IAM policy..."
POLICY_ARN="arn:aws:iam::$ACCOUNT_ID:policy/$POLICY_NAME"

if aws iam get-policy --policy-arn "$POLICY_ARN" &> /dev/null; then
    echo "[OK] Policy exists. Updating..."
    # Update default version if needed
else
    echo "Creating policy: $POLICY_NAME"
    POLICY_ARN=$(aws iam create-policy \
        --policy-name "$POLICY_NAME" \
        --policy-document file://iam-policy.json \
        --query 'Policy.Arn' \
        --output text)
    echo "[OK] Created policy: $POLICY_ARN"
fi

aws iam attach-role-policy \
    --role-name "$ROLE_NAME" \
    --policy-arn "$POLICY_ARN" 2>/dev/null || true

echo "[OK] Policy attached to role."

# Create deployment package
echo ""
echo "[STEP 3/3] Packaging and deploying Lambda function..."
zip -q function.zip lambda_function.py

if aws lambda get-function --function-name "$FUNCTION_NAME" --region "$REGION" &> /dev/null; then
    echo "Updating existing function code..."
    FUNCTION_ARN=$(aws lambda update-function-code \
        --function-name "$FUNCTION_NAME" \
        --zip-file fileb://function.zip \
        --region "$REGION" \
        --query 'FunctionArn' \
        --output text)
    echo "[OK] Function code updated."
else
    echo "Creating new Lambda function..."
    FUNCTION_ARN=$(aws lambda create-function \
        --function-name "$FUNCTION_NAME" \
        --runtime "$RUNTIME" \
        --role "$ROLE_ARN" \
        --handler "$HANDLER" \
        --zip-file fileb://function.zip \
        --timeout "$TIMEOUT" \
        --memory-size "$MEMORY" \
        --environment "Variables={BEDROCK_MODEL_ID=apac.amazon.nova-lite-v1:0}" \
        --region "$REGION" \
        --query 'FunctionArn' \
        --output text)
    echo "[OK] Function created: $FUNCTION_ARN"
fi

rm -f function.zip

echo ""
echo "=== Deployment Successful ==="
echo "Lambda Function ARN: $FUNCTION_ARN"
echo "Region: $REGION"
