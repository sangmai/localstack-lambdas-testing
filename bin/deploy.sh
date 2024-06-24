#!/bin/bash

export AWS_DEFAULT_REGION=us-east-1

awslocal s3 mb s3://localstack-poc-upload-images

awslocal ssm put-parameter --name /localstack-poc-upload-images/buckets/images --type "String" --value "localstack-poc-upload-images"
