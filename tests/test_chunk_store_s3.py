from dataclasses import dataclass

import boto3
import pytest
from moto import mock_aws

from pipeline.store import ChunkStore

BUCKET = "test-bucket"
REGION = "eu-north-1"


@dataclass
class FakeChunk:
    """Minimal stand-in: save_chunks only needs a dataclass with these fields."""
    chunk_id: str
    text: str
    source: str = "news"
    company: str = "ACME"


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


def test_round_trip_merges_by_chunk_id(s3_store):
    s3_store.save_chunks([FakeChunk("a", "old A"), FakeChunk("b", "B")], "news_2026-10-20")
    s3_store.save_chunks([FakeChunk("a", "new A"), FakeChunk("c", "C")], "news_2026-10-20")

    chunks = s3_store.load_all_chunks()
    by_id = {c["chunk_id"]: c for c in chunks}

    assert len(chunks) == 3                    # append would give 4
    assert set(by_id) == {"a", "b", "c"}       # old "b" kept
    assert by_id["a"]["text"] == "new A"       # new wins


def test_empty_prefix_returns_empty_list(s3_store):
    assert s3_store.load_all_chunks() == []


def test_key_uses_prefix_and_jsonl_extension(s3_store):
    s3_store.save_chunks([FakeChunk("a", "A")], "10k_2025")
    keys = [o["Key"] for o in s3_store.s3.list_objects_v2(Bucket=BUCKET)["Contents"]]
    assert keys == ["chunks/10k_2025.jsonl"]
