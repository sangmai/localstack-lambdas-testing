import json
import boto3
import pytest
import typing
import os
import base64 
if typing.TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client
    from mypy_boto3_ssm import SSMClient
    from mypy_boto3_lambda import LambdaClient

os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_ACCESS_KEY_ID"] = "test"
os.environ["AWS_SECRET_ACCESS_KEY"] = "test"

s3: "S3Client" = boto3.client(
    "s3", endpoint_url="http://localhost.localstack.cloud:4566"
)
ssm: "SSMClient" = boto3.client(
    "ssm", endpoint_url="http://localhost.localstack.cloud:4566"
)
awslambda: "LambdaClient" = boto3.client(
    "lambda", endpoint_url="http://localhost.localstack.cloud:4566"
)
@pytest.fixture(autouse=True)
def _wait_for_lambdas():
    # makes sure that the lambdas are available before running integration tests
    awslambda.get_waiter("function_active").wait(FunctionName="localstack-lambda-s3-upload")

def test_lambda_handler_with_image_data():

  file = os.path.join(os.path.dirname(__file__), "nyan-cat.png")
  with open(file, 'rb') as image_file:
    image_data = image_file.read()
  base64_encoded_image_data = base64.b64encode(image_data).decode('utf-8')

  event = {'headers' : {'content-type' : 'image/jpeg', 'filename': 'test-integration'}, 'body': base64_encoded_image_data}  

  response = awslambda.invoke(
            FunctionName="localstack-lambda-s3-upload",
            Payload=json.dumps(event)
        )
  response_data = json.loads(response['Payload'].read())
   # Assert successful response and message
  assert response_data['statusCode'] == 200
  assert 's3_url' in response_data["body"]
  assert '\"success\": true' in response_data["body"]
  
def test_failure_handler_with_no_image_data():

  response = awslambda.invoke(
            FunctionName="localstack-lambda-s3-upload",
            Payload=''
        )
  response_data = json.loads(response['Payload'].read())
   # Assert response and message
  assert 'Missing image data in body' in response_data["message"]
  assert response_data['statusCode'] == 400
