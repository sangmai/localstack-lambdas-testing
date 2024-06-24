import boto3
import json
from datetime import datetime
import calendar
import os
import time
import json
from faker import Faker
import uuid
import typing
from time import sleep
if typing.TYPE_CHECKING:
    from mypy_boto3_kinesis import KinesisClient

os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_ACCESS_KEY_ID"] = "test"
os.environ["AWS_SECRET_ACCESS_KEY"] = "test"

my_stream_name = 'kinesis_test_stream'
kinesis_client: "KinesisClient" = boto3.client(
    "kinesis", endpoint_url="http://localhost.localstack.cloud:4566",region_name='us-east-1', 
)
faker = Faker()
for i in range(1, 10):
    json_data = {
        "name":faker.name(),
        "city":faker.city(),
        "phone":faker.phone_number(),
        "id":uuid.uuid4().__str__()
    }
    print(json_data)
    sleep(0.5)

    put_response = kinesis_client.put_record(
        StreamName=my_stream_name,
        Data=json.dumps(json_data),
        PartitionKey='name')
    print(put_response)