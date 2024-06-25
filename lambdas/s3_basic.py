
import logging
import os
import boto3
import typing

from botocore.exceptions import ClientError
if typing.TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client

os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_ACCESS_KEY_ID"] = "test"
os.environ["AWS_SECRET_ACCESS_KEY"] = "test"

s3: "S3Client" = boto3.resource(
    "s3", endpoint_url="http://localhost.localstack.cloud:4566",region_name='us-east-1'
)
logger = logging.getLogger(__name__)

def list_my_buckets(s3):
    for b in s3.buckets.all() : 
        logger.info('My Buckets: %s', b.name)

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


def bucket_exists(bucket_name):
    """
    Determine whether a bucket with the specified name exists.

    Usage is shown in usage_demo at the end of this module.

    :param bucket_name: The name of the bucket to check.
    :return: True when the bucket exists; otherwise, False.
    """
    try:
        s3.meta.client.head_bucket(Bucket=bucket_name)
        logger.info("Bucket %s exists.", bucket_name)
        exists = True
    except ClientError:
        logger.warning("Bucket %s doesn't exist or you don't have access to it.",
                       bucket_name)
        exists = False
    return exists


def delete_bucket(bucket):
    """
    Delete a bucket. The bucket must be empty or an error is raised.

    Usage is shown in usage_demo at the end of this module.

    :param bucket: The bucket to delete.
    """
    try:
        bucket.delete()
        bucket.wait_until_not_exists()
        logger.info("Bucket %s successfully deleted.", bucket.name)
    except ClientError:
        logger.exception("Couldn't delete bucket %s.", bucket.name)
        raise

