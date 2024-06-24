(cd lambdas; zip function.zip index.py)

awslocal lambda update-function-code --function-name localstack-lambda-s3-upload --zip-file fileb://lambdas/function.zip