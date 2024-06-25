
import json
import logging
import time
import boto3
import os
import typing
from time import sleep
from faker import Faker
import uuid

from botocore.exceptions import ClientError
import lambda_basic as lambda_helper
if typing.TYPE_CHECKING:
    from mypy_boto3_kinesis import KinesisClient
    from mypy_boto3_s3 import S3Client
    from mypy_boto3_firehose import FirehoseClient
    from mypy_boto3_iam import IAMClient
    from mypy_boto3_lambda import LambdaClient

os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_ACCESS_KEY_ID"] = "test"
os.environ["AWS_SECRET_ACCESS_KEY"] = "test"

kinesis_client: "KinesisClient" = boto3.client(
    "kinesis", endpoint_url="http://localhost.localstack.cloud:4566",region_name='us-east-1', 
)
s3: "S3Client" = boto3.client(
    "s3", endpoint_url="http://localhost.localstack.cloud:4566"
)
firehose_client: "FirehoseClient" = boto3.client(
    "firehose", endpoint_url="http://localhost.localstack.cloud:4566",region_name='us-east-1', 
)
iam_client: "IAMClient" = boto3.client(
    "iam", endpoint_url="http://localhost.localstack.cloud:4566",region_name='us-east-1', 
)
lambda_client: "LambdaClient" = boto3.client(
    "lambda", endpoint_url="http://localhost.localstack.cloud:4566"
)
iam_resource: "IAMClient" = boto3.resource(
    "iam", endpoint_url="http://localhost.localstack.cloud:4566",region_name='us-east-1', 
)

def create_kinesis_stream(stream_name, num_shards=1):
    """Create a Kinesis data stream

    :param stream_name: Data stream name
    :param num_shards: Number of stream shards
    :return: True if creation of stream was started. Otherwise, False.
    """

    # Create the data stream
    if not kinesis_exists: 
        try:
            kinesis_client.create_stream(StreamName=stream_name,
                                        ShardCount=num_shards)
        except ClientError as e:
            logging.error(e)
            return False
    return True

def get_kinesis_arn(stream_name):
    """Retrieve the ARN for a Kinesis data stream

    :param stream_name: Kinesis data stream name
    :return: ARN of stream. If error, return None.
    """

    # Retrieve stream info
    try:
        result = kinesis_client.describe_stream_summary(StreamName=stream_name)
    except ClientError as e:
        logging.error(e)
        return None
    return result['StreamDescriptionSummary']['StreamARN']

def kinesis_exists(kinesis_name):
    """Check if the specified Kinesis exists

    :param firehose_name: Kinesis stream name
    :return: True if Kinesis exists, else False
    """

    # Try to get the description of the Firehose
    if get_kinesis_arn(kinesis_name) is None:
        return False
    return True

def wait_for_active_kinesis_stream(stream_name):
    """Wait for a new Kinesis data stream to become active

    :param stream_name: Data stream name
    :return: True if steam is active. False if error creating stream.
    """

    # Wait until the stream is active
    while True:
        try:
            # Get the stream's current status
            result = kinesis_client.describe_stream_summary(StreamName=stream_name)
        except ClientError as e:
            logging.error(e)
            return False
        status = result['StreamDescriptionSummary']['StreamStatus']
        if status == 'ACTIVE':
            return True
        if status == 'DELETING':
            logging.error(f'Kinesis stream {stream_name} is being deleted.')
            return False
        time.sleep(5)


def get_firehose_arn(firehose_name):
    """Retrieve the ARN of the specified Firehose

    :param firehose_name: Firehose stream name
    :return: If the Firehose stream exists, return ARN, else None
    """
    try:
        result = firehose_client.describe_delivery_stream(DeliveryStreamName=firehose_name)
    except ClientError as e:
        logging.error(e)
        return None
    return result['DeliveryStreamDescription']['DeliveryStreamARN']


def firehose_exists(firehose_name):
    """Check if the specified Firehose exists

    :param firehose_name: Firehose stream name
    :return: True if Firehose exists, else False
    """

    # Try to get the description of the Firehose
    if get_firehose_arn(firehose_name) is None:
        return False
    return True


def get_iam_role_arn(iam_role_name):
    """Retrieve the ARN of the specified IAM role

    :param iam_role_name: IAM role name
    :return: If the IAM role exists, return ARN, else None
    """

    # Try to retrieve information about the role
    try:
        result = iam_client.get_role(RoleName=iam_role_name)
    except ClientError as e:
        logging.error(e)
        return None
    return result['Role']['Arn']


def iam_role_exists(iam_role_name):
    """Check if the specified IAM role exists

    :param iam_role_name: IAM role name
    :return: True if IAM role exists, else False
    """

    # Try to retrieve information about the role
    if get_iam_role_arn(iam_role_name) is None:
        return False
    return True


def create_iam_role_for_firehose_to_s3(iam_role_name, s3_bucket,
                                       firehose_src_stream=None):
    """Create an IAM role for a Firehose delivery system to S3

    :param iam_role_name: Name of IAM role
    :param s3_bucket: ARN of S3 bucket
    :param firehose_src_stream: ARN of source Kinesis Data Stream. If
        Firehose data source is via direct puts then arg should be None.
    :return: ARN of IAM role. If error, returns None.
    """

    # Firehose trusted relationship policy document
    firehose_assume_role = {
        'Version': '2012-10-17',
        'Statement': [
            {
                'Sid': '',
                'Effect': 'Allow',
                'Principal': {
                    'Service': 'firehose.amazonaws.com'
                },
                'Action': 'sts:AssumeRole'
            }
        ]
    }
    try:
        result = iam_client.create_role(RoleName=iam_role_name,
                                        AssumeRolePolicyDocument=json.dumps(firehose_assume_role))
    except ClientError as e:
        logging.error(e)
        return None
    firehose_role_arn = result['Role']['Arn']

    # Define and attach a policy that grants sufficient S3 permissions
    policy_name = 'firehose_s3_access'
    s3_access = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "",
                "Effect": "Allow",
                "Action": [
                    "s3:AbortMultipartUpload",
                    "s3:GetBucketLocation",
                    "s3:GetObject",
                    "s3:ListBucket",
                    "s3:ListBucketMultipartUploads",
                    "s3:PutObject"
                ],
                "Resource": [
                    f"{s3_bucket}/*",
                    f"{s3_bucket}"
                ]
            }
        ]
    }
    try:
        iam_client.put_role_policy(RoleName=iam_role_name,
                                   PolicyName=policy_name,
                                   PolicyDocument=json.dumps(s3_access))
    except ClientError as e:
        logging.error(e)
        return None

    # If the Firehose source is a Kinesis data stream then access to the
    # stream must be allowed.
    if firehose_src_stream is not None:
        policy_name = 'firehose_kinesis_access'
        kinesis_access = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "",
                    "Effect": "Allow",
                    "Action": [
                        "kinesis:DescribeStream",
                        "kinesis:GetShardIterator",
                        "kinesis:GetRecords"
                    ],
                    "Resource": [
                        f"{firehose_src_stream}"
                    ]
                }
             ]
        }
        try:
            iam_client.put_role_policy(RoleName=iam_role_name,
                                       PolicyName=policy_name,
                                       PolicyDocument=json.dumps(kinesis_access))
        except ClientError as e:
            logging.error(e)
            return None

    # Return the ARN of the created IAM role
    return firehose_role_arn


def create_firehose_to_s3(firehose_name, s3_bucket_arn, iam_role_name,
                          firehose_src_type='DirectPut',
                          firehose_src_stream=None,
                          isLambdaTransformFunction=False,):
    """Create a Kinesis Firehose delivery stream to S3

    The data source can be either a Kinesis Data Stream or puts sent directly
    to the Firehose stream.

    :param firehose_name: Delivery stream name
    :param s3_bucket_arn: ARN of S3 bucket
    :param iam_role_name: Name of Firehose-to-S3 IAM role. If the role doesn't
        exist, it is created.
    :param firehose_src_type: 'DirectPut' or 'KinesisStreamAsSource'
    :param firehose_src_stream: ARN of source Kinesis Data Stream. Required if
        firehose_src_type is 'KinesisStreamAsSource'
    :return: ARN of Firehose delivery stream. If error, returns None.
    """

    # Create Firehose-to-S3 IAM role if necessary
    if iam_role_exists(iam_role_name):
        # Retrieve its ARN
        iam_role = get_iam_role_arn(iam_role_name)
    else:
        iam_role = create_iam_role_for_firehose_to_s3(iam_role_name,
                                                      s3_bucket_arn,
                                                      firehose_src_stream)
        if iam_role is None:
            # Error creating IAM role
            return None

    # Create the S3 configuration dictionary
    # Both BucketARN and RoleARN are required
    # Set the buffer interval=60 seconds (Default=300 seconds)
    if not isLambdaTransformFunction: 
        s3_config = {
            'BucketARN': s3_bucket_arn,
            'RoleARN': iam_role,
            'BufferingHints': {
                'IntervalInSeconds': 60,
            },
        }
    else:
        lambda_function_filename = 'lambda_transform_json_to_csv.py'
        lambda_handler_name = 'lambda_transform_json_to_csv.handler'
        lambda_function_name = 'lambda_transform_json_to_csv'
        lambda_role_name = 'lambda-role'
        deployment_package = lambda_helper.create_lambda_deployment_package(lambda_function_filename)
        iam_role_for_lambda = lambda_helper.create_iam_role_for_lambda(iam_resource, lambda_role_name)
        lambdaFunctionArn = lambda_helper.deploy_lambda_function(lambda_client, lambda_function_name,lambda_handler_name, iam_role_for_lambda, deployment_package )
        s3_config = {
            'BucketARN': s3_bucket_arn,
            'RoleARN': iam_role,
            'BufferingHints': {
                'IntervalInSeconds': 60,
            },
            "ProcessingConfiguration": {
                "Enabled": True,
                "Processors": [
                {
                    "Type": "Lambda",
                        "Parameters": [
                        {
                            "ParameterName": "LambdaArn",
                            "ParameterValue": lambdaFunctionArn
                        },
                        {
                            "ParameterName": "NumberOfRetries",
                            "ParameterValue": "3"
                        },
                        {
                            "ParameterName": "RoleArn",
                            "ParameterValue": iam_role
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
        }

    # Create the delivery stream
    # By default, the DeliveryStreamType='DirectPut'
    try:
        if firehose_src_type == 'KinesisStreamAsSource':
            # Define the Kinesis Data Stream configuration
            stream_config = {
                'KinesisStreamARN': firehose_src_stream,
                'RoleARN': iam_role,
            }
            result = firehose_client.create_delivery_stream(
                DeliveryStreamName=firehose_name,
                DeliveryStreamType=firehose_src_type,
                KinesisStreamSourceConfiguration=stream_config,
                ExtendedS3DestinationConfiguration=s3_config)
        else:
            result = firehose_client.create_delivery_stream(
                DeliveryStreamName=firehose_name,
                DeliveryStreamType=firehose_src_type,
                ExtendedS3DestinationConfiguration=s3_config)
    except ClientError as e:
        logging.error(e)
        return None
    return result['DeliveryStreamARN']


def wait_for_active_firehose(firehose_name):
    """Wait until the Firehose delivery stream is active

    :param firehose_name: Name of Firehose delivery stream
    :return: True if delivery stream is active. Otherwise, False.
    """

    # Wait until the stream is active
    while True:
        try:
            # Get the stream's current status
            result = firehose_client.describe_delivery_stream(DeliveryStreamName=firehose_name)
        except ClientError as e:
            logging.error(e)
            return False
        status = result['DeliveryStreamDescription']['DeliveryStreamStatus']
        if status == 'ACTIVE':
            return True
        if status == 'DELETING':
            logging.error(f'Firehose delivery stream {firehose_name} is being deleted.')
            return False
        time.sleep(2)


def main():
    """Exercise Kinesis Firehose methods"""
    print('-'*88)
    print("Welcome to the POC LocalStack Kinesis Stream to Firehose to S3.")
    print("This is Demo for JSON Data streaming from Kinesis and delivery to Firehose then using Lambda Transform function convert to CSV format and save to S3")
    print('-'*88)
    # Assign these values before running the program
    # If the specified IAM role does not exist, it will be created
    kinesis_name = 'kinesis_test_stream'
    firehose_name = 'firehose_to_s3_stream_3'
    bucket_arn = 'kinesis-poc-storage'
    iam_role_name = 'lambda-role'

    # Set up logging
    logging.basicConfig(level=logging.DEBUG,
                        format='%(levelname)s: %(asctime)s: %(message)s')
    # Create a Kinesis stream (this is an asynchronous method)
    success = create_kinesis_stream(kinesis_name)
    if not success:
        exit(1)

    # Wait for the stream to become active
    logging.info(f'Waiting for new Kinesis stream {kinesis_name} to become active...')
    if not wait_for_active_kinesis_stream(kinesis_name):
        exit(1)
    logging.info(f'Kinesis stream {kinesis_name} is active')  

    # Retrieve the Kinesis stream's ARN
    kinesis_arn = get_kinesis_arn(kinesis_name) 

    # Create a Firehose delivery stream as a consumer of the Kinesis stream
    firehose_src_type = 'KinesisStreamAsSource'

    # If Firehose doesn't exist, create it
    if not firehose_exists(firehose_name):
        # Create a Firehose delivery stream to S3. The Firehose will receive
        # data from direct puts.
        firehose_arn = create_firehose_to_s3(firehose_name, bucket_arn, iam_role_name, firehose_src_type, kinesis_arn, isLambdaTransformFunction=True)

        if firehose_arn is None:
            exit(1)
        logging.info(f'Created Firehose delivery stream to S3: {firehose_arn}')

        # Wait for the stream to become active
        if not wait_for_active_firehose(firehose_name):
            exit(1)
        logging.info('Firehose stream is active')

    # Put records into the Firehose stream
    faker = Faker()
    for i in range(1, 10):
        json_data = {
            "name":faker.name(),
            "city":faker.city(),
            "phone":faker.phone_number(),
            "id":uuid.uuid4().__str__()
        }
        logging.info(json_data)
        sleep(0.5)
        put_response = kinesis_client.put_record(
            StreamName=kinesis_name,
            Data=json.dumps(json_data),
            PartitionKey='name')
        logging.info(put_response)
        logging.info('Test data sent to Firehose stream')


if __name__ == '__main__':
    main()