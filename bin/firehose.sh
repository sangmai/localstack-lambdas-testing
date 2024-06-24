echo "Creating Firehose stream"
awslocal firehose create-delivery-stream --delivery-stream-name my-delivery-stream-local --delivery-stream-type KinesisStreamAsSource \
    --kinesis-stream-source-configuration "KinesisStreamARN=arn:aws:kinesis:us-east-1:000000000000:stream/my-kinesis-lambda-stream,RoleARN=aarn:aws:iam::000000000000:role/lambda-role" \
    --extended-s3-destination-configuration \
    '{
      "BucketARN": "kinesis-poc-storage",
      "Prefix": "export-data/",
      "RoleARN": "aarn:aws:iam::000000000000:role/lambda-role",
      "BufferingHints": {"IntervalInSeconds": 60, "SizeInMBs": 1},
      "ProcessingConfiguration": {
        "Enabled": true,
        "Processors": [
          {
            "Type": "Lambda",
            "Parameters": [
              {
                "ParameterName": "LambdaArn",
                "ParameterValue": "arn:aws:lambda:us-east-1:000000000000:function:kinesis-example"
              },
              {
                "ParameterName": "NumberOfRetries",
                "ParameterValue": "3"
              },
              {
                "ParameterName": "RoleArn",
                "ParameterValue": "aarn:aws:iam::000000000000:role/lambda-role"
              },
              {
                "ParameterName": "BufferSizeInMBs",
                "ParameterValue": "1"
              },
              {
                "ParameterName": "BufferIntervalInSeconds",
                "ParameterValue": "60"
              }
            ]
          }
        ]
      }
    }'