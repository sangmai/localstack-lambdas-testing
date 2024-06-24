import os
import boto3
import typing
import base64
import json
import logging
import uuid
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

if typing.TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client
    from mypy_boto3_ssm import SSMClient

endpoint_url = None
if os.getenv("STAGE") == "local":
    endpoint_url = "https://localhost.localstack.cloud:4566"

s3: "S3Client" = boto3.client("s3", endpoint_url=endpoint_url)
ssm: "SSMClient" = boto3.client("ssm", endpoint_url=endpoint_url)

def get_bucket_name() -> str:
    parameter = ssm.get_parameter(Name="/localstack-poc-upload-images/buckets/images")
    return parameter["Parameter"]["Value"]

s3_bucket = get_bucket_name()

# main lambda handler method
def handler(event, context):
    # print(event)
    payload = event.get('body')
    if not payload: 
        return {'statusCode': 400, 'message': 'Missing image data in body'}
    
    # upload image to get s3 URL
    logger.info('upload_image_to_s3 , bucket=' + s3_bucket)

    file_extension = get_file_extension_from_header(event)

    # print(event.get('headers'))

    # check we have file name in input
    if 'filename' in event.get('headers'):
        file_name = f"{event.get('headers').get('filename')}.{file_extension}"
    else:
        file_name = f"{str(uuid.uuid1())}.{file_extension}"
    
    file_content = base64.b64decode(payload)

    s3_upload(file_name, file_content, {})

    # image uploaded successfully return presigned url to download 
    response = {
        'success': True,
        's3_url': create_presigned_url(s3_bucket, file_name)
    }
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json'
        },
        'body': json.dumps(response)
    }

def get_file_extension_from_header(event):
    file_type = event.get('headers').get('content-type')
    if file_type:
        return  file_type.split('/')[1]
    else:
        return 'png'
    # default to PNG if we are not able to extract extension or string is not bas64 encoded

# The response contains the presigned URL
def create_presigned_url(bucket_name, object_name, expiration=3600):
    try:
        return s3.generate_presigned_url('get_object', Params={'Bucket': bucket_name, 'Key': object_name}, ExpiresIn=expiration)
    except ClientError as e:
        logging.error(e)
        raise

# upload object to s3
def s3_upload(s3_key, file_content, metadata):
    logger.info(f'saving_s3_file , bucket={s3_bucket} , path={s3_key}')
    try:
        response = s3.put_object(Body=file_content, Bucket=s3_bucket, Key=s3_key, Metadata=metadata)
        logger.info('S3 Result' + json.dumps(response, indent=2))
    except ClientError as e:
        logging.error(e)
        raise

