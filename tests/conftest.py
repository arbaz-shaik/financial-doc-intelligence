import boto3
import pytest
from moto import mock_aws

from pipeline.store import ChunkStore

BUCKET = "test-bucket"
REGION = "eu-north-1"


@pytest.fixture
def s3_store(monkeypatch):
    # Fake credentials so nothing can ever reach real AWS
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", REGION)
    with mock_aws():
        client = boto3.client("s3", region_name=REGION)
        client.create_bucket(
            Bucket=BUCKET,
            CreateBucketConfiguration={"LocationConstraint": REGION},
        )
        yield ChunkStore(bucket=BUCKET, prefix="chunks", s3_client=client)
        