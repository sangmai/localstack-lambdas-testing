#!/bin/bash

export AWS_DEFAULT_REGION=us-east-1

awslocal s3 mb s3://localstack-poc-upload-images

awslocal ssm put-parameter --name /localstack-poc-upload-images/buckets/images --type "String" --value "localstack-poc-upload-images"

awslocal sns create-topic --name failed-resize-topic
awslocal sns subscribe \
    --topic-arn arn:aws:sns:us-east-1:000000000000:failed-resize-topic \
    --protocol email \
    --notification-endpoint my-email@example.com

(cd lambdas; zip function.zip index.py)

awslocal lambda create-function \
    --function-name localstack-lambda-s3-upload \
    --runtime python3.11 \
    --timeout 10 \
    --zip-file fileb://lambdas/function.zip \
    --handler index.handler \
    --role arn:aws:iam::000000000000:role/lambda-role \
    --environment Variables="{STAGE=local}"

awslocal lambda wait function-active-v2 --function-name localstack-lambda-s3-upload

awslocal lambda create-function-url-config \
    --function-name localstack-lambda-s3-upload \
    --auth-type NONE

awslocal lambda put-function-event-invoke-config --function-name localstack-lambda-s3-upload --maximum-event-age-in-seconds 3600 --maximum-retry-attempts 0

echo
echo "Fetching function URL for Lambda..."
awslocal lambda list-function-url-configs --function-name localstack-lambda-s3-upload --output json | jq -r '.FunctionUrlConfigs[0].FunctionUrl'

echo "Now open the Postman then send POST api to this URL with image in the binary and filename in the header"
