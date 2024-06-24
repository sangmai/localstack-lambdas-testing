import io
import json
import logging
import os
import time
import zipfile
import boto3
import typing
import base64 
import uuid

from botocore.exceptions import ClientError
if typing.TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client
    from mypy_boto3_ssm import SSMClient
    from mypy_boto3_lambda import LambdaClient
    from mypy_boto3_iam import IAMClient

os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_ACCESS_KEY_ID"] = "test"
os.environ["AWS_SECRET_ACCESS_KEY"] = "test"

s3: "S3Client" = boto3.resource(
    "s3", endpoint_url="http://localhost.localstack.cloud:4566",region_name='us-east-1'
)
ssm: "SSMClient" = boto3.client(
    "ssm", endpoint_url="http://localhost.localstack.cloud:4566"
)
lambda_client: "LambdaClient" = boto3.client(
    "lambda", endpoint_url="http://localhost.localstack.cloud:4566"
)
iam_resource: "IAMClient" = boto3.resource(
    "iam", endpoint_url="http://localhost.localstack.cloud:4566",region_name='us-east-1', 
)
logger = logging.getLogger(__name__)

def list_my_buckets(s3):
    print('Buckets:\n\t', *[b.name for b in s3.buckets.all()], sep="\n\t")

def create_and_delete_my_bucket(bucket_name, keep_bucket):

    list_my_buckets(s3)

    try:
        logger.info('Creating new bucket:  %s.', bucket_name)
        bucket = s3.create_bucket(
            Bucket=bucket_name
        )
    except ClientError as e:
        print(e)
        logger.exception("Exiting the script because bucket creation failed. %s.", e)

    bucket.wait_until_exists()
    list_my_buckets(s3)

    if not keep_bucket:
        logger.info('Deleting bucket: %s.', bucket.name)
        bucket.delete()

        bucket.wait_until_not_exists()
        list_my_buckets(s3)
    else:
        logger.info('Keeping bucket: %s.', bucket.name)

def create_lambda_deployment_package(function_file_name):
    """
    Creates a Lambda deployment package in ZIP format in an in-memory buffer. This
    buffer can be passed directly to AWS Lambda when creating the function.

    :param function_file_name: The name of the file that contains the Lambda handler
                               function.
    :return: The deployment package.
    """
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as zipped:
        zipped.write(function_file_name)
    buffer.seek(0)
    return buffer.read()


def create_iam_role_for_lambda(iam_resource, iam_role_name):
    """
    Creates an AWS Identity and Access Management (IAM) role that grants the
    AWS Lambda function basic permission to run. If a role with the specified
    name already exists, it is used for the demo.

    :param iam_resource: The Boto3 IAM resource object.
    :param iam_role_name: The name of the role to create.
    :return: The newly created role.
    """
    lambda_assume_role_policy = {
        'Version': '2012-10-17',
        'Statement': [
            {
                'Effect': 'Allow',
                'Principal': {
                    'Service': 'lambda.amazonaws.com'
                },
                'Action': 'sts:AssumeRole'
            }
        ]
    }
    policy_arn = 'arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole'

    try:
        role = iam_resource.create_role(
            RoleName=iam_role_name,
            AssumeRolePolicyDocument=json.dumps(lambda_assume_role_policy))
        iam_resource.meta.client.get_waiter('role_exists').wait(RoleName=iam_role_name)

        logger.info("Created role %s.", role.name)

        role.attach_policy(PolicyArn=policy_arn)
        logger.info("Attached basic execution policy to role %s.", role.name)
    except ClientError as error:
        if error.response['Error']['Code'] == 'EntityAlreadyExists':
            role = iam_resource.Role(iam_role_name)
            logger.warning("The role %s already exists. Using it.", iam_role_name)
        else:
            logger.exception(
                "Couldn't create role %s or attach policy %s.",
                iam_role_name, policy_arn)
            raise

    return role


def deploy_lambda_function(
        lambda_client, function_name, handler_name, iam_role, deployment_package):
    """
    Deploys the AWS Lambda function.

    :param lambda_client: The Boto3 AWS Lambda client object.
    :param function_name: The name of the AWS Lambda function.
    :param handler_name: The fully qualified name of the handler function. This
                         must include the file name and the function name.
    :param iam_role: The IAM role to use for the function.
    :param deployment_package: The deployment package that contains the function
                               code in ZIP format.
    :return: The Amazon Resource Name (ARN) of the newly created function.
    """
    try:
        response = lambda_client.create_function(
            FunctionName=function_name,
            Runtime='python3.11',
            Role=iam_role.arn,
            Handler=handler_name,
            Code={'ZipFile': deployment_package},
            Publish=True)
        function_arn = response['FunctionArn']
        logger.info("Created function '%s' with ARN: '%s'.",
                    function_name, response['FunctionArn'])
    except ClientError:
        logger.exception("Couldn't create function %s.", function_name)
        raise
    else:
        return function_arn


def delete_lambda_function(lambda_client, function_name):
    """
    Deletes an AWS Lambda function.

    :param lambda_client: The Boto3 AWS Lambda client object.
    :param function_name: The name of the function to delete.
    """
    try:
        lambda_client.delete_function(FunctionName=function_name)
    except ClientError:
        logger.exception("Couldn't delete function %s.", function_name)
        raise


def create_lambda_url_config_function(lambda_client, function_name):
    """
    Create the URL config for AWS Lambda function.

    :param lambda_client: The Boto3 AWS Lambda client object.
    :param function_name: The name of the function to create url.
    """
    try:
       response =  lambda_client.create_function_url_config(FunctionName=function_name, AuthType='NONE')
    except ClientError:
        logger.exception("Couldn't create URL config for function %s.", function_name)
        raise
    return response

def invoke_lambda_function(lambda_client, function_name, function_params):
    """
    Invokes an AWS Lambda function.

    :param lambda_client: The Boto3 AWS Lambda client object.
    :param function_name: The name of the function to invoke.
    :param function_params: The parameters of the function as a dict. This dict
                            is serialized to JSON before it is sent to AWS Lambda.
    :return: The response from the function invocation.
    """
    try:
        response = lambda_client.invoke(
            FunctionName=function_name,
            Payload=json.dumps(function_params))
        logger.info("Invoked function %s.", function_name)
    except ClientError:
        logger.exception("Couldn't invoke function %s.", function_name)
        raise
    return response

def usage_demo():

    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    print('-'*88)
    print("Welcome to the POC LocalStack Lambda basics demo.")
    print("This is Lambda function to upload image into S3")
    print('-'*88)
    lambda_function_filename = 'lambda_upload_image_to_s3.py'
    lambda_handler_name = 'lambda_upload_image_to_s3.handler'
    lambda_role_name = 'lambda-role'
    lambda_function_name = 'upload-image-to-s3'
    s3_bucket_name = 'localstack-poc-upload-images'

    create_and_delete_my_bucket(s3_bucket_name, 1)

    logger.info(f"Creating AWS Lambda function {lambda_function_name} from the "
          f"{lambda_handler_name} function in {lambda_function_filename}...")
    deployment_package = create_lambda_deployment_package(lambda_function_filename)
    iam_role = create_iam_role_for_lambda(iam_resource, lambda_role_name)

    deploy_lambda_function(lambda_client, lambda_function_name,lambda_handler_name, iam_role, deployment_package )
    lambda_client.get_waiter("function_active").wait(FunctionName=lambda_function_name)

    file = os.path.join(os.path.dirname(__file__), "nyan-cat.png")
    with open(file, 'rb') as image_file:
        image_data = image_file.read()
        base64_encoded_image_data = base64.b64encode(image_data).decode('utf-8')

    event = {'headers' : {'content-type' : 'image/jpeg', 'filename': f'test-integration-{uuid.uuid4().__str__()}'}, 'body': base64_encoded_image_data}  

    response = invoke_lambda_function(lambda_client, lambda_function_name,event)
    response_data = json.loads(response['Payload'].read())

    logger.info(f"The status code is {response_data['statusCode']} resulted in "
          f"{response_data}")
    
    response = create_lambda_url_config_function(lambda_client, lambda_function_name)
    print(f"Please using the url for this function {response['FunctionUrl']} ")
    print('-'*88)
    print("This is end of our Lambda basics demo.")
    print(f"Please check the S3 bucket with image name: 'test-integration-{uuid.uuid4().__str__()}'")
    print('-'*88)

    # delete_lambda_function(lambda_client, lambda_function_name)
    # logger.info(f"Deleted function {lambda_function_name}.")

if __name__ == '__main__':
    usage_demo()