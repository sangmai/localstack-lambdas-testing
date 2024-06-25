
import logging
import os
import boto3
import typing

from botocore.exceptions import ClientError
if typing.TYPE_CHECKING:
    from mypy_boto3_ssm import SSMClient
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_ACCESS_KEY_ID"] = "test"
os.environ["AWS_SECRET_ACCESS_KEY"] = "test"

ssm_client: "SSMClient" = boto3.client(
    "ssm", endpoint_url="http://localhost.localstack.cloud:4566"
)
logger = logging.getLogger(__name__)

def put_parameter(parameter_name, parameter_value, parameter_type):
    """Creates new parameter in AWS SSM

    :param parameter_name: Name of the parameter to create in AWS SSM
    :param parameter_value: Value of the parameter to create in AWS SSM
    :param parameter_type: Type of the parameter to create in AWS SSM ('String'|'StringList'|'SecureString')
    :return: Return version of the parameter if successfully created else None
    """

    try:
        result = ssm_client.put_parameter(
            Name=parameter_name,
            Value=parameter_value,
            Type=parameter_type
        )
    except ClientError as e:
        logging.error(e)
        return None
    return result['Version']