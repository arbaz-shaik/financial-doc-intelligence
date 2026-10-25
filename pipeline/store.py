import json
from dataclasses import asdict
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

from pipeline.chunker import Chunk
from src.logger import get_logger

logger = get_logger(__name__)


# ---------- shared helpers (used by local AND S3 modes) ----------

def merge_chunks(existing: list[dict], new: list[dict]) -> list[dict]:
    """Merge by chunk_id. New wins. Existing order kept; brand-new IDs appended."""
    merged = {c["chunk_id"]: c for c in existing}
    for c in new:
        merged[c["chunk_id"]] = c
    return list(merged.values())


def to_jsonl(chunks: list[dict]) -> str:
    return "".join(json.dumps(c) + "\n" for c in chunks)


def parse_jsonl(text: str) -> list[dict]:
    return [json.loads(line) for line in text.splitlines() if line.strip()]


class ChunkStore:
    def __init__(self, directory: str | None = None, bucket: str | None = None,
                 prefix: str = "", s3_client=None):
        self.bucket = bucket
        if bucket:
            clean = prefix.strip("/")
            self.prefix = f"{clean}/" if clean else ""
            self.s3 = s3_client or boto3.client("s3")
        else:
            if directory is None:
                raise ValueError("directory is required in local mode")
            self.directory = Path(directory)
            self.directory.mkdir(parents=True, exist_ok=True)

    def save_chunks(self, chunks: list[Chunk], filename: str) -> int:
        if self.bucket:
            return self._save_s3(chunks, filename)
        return self._save_local(chunks, filename)

    def _save_local(self, chunks: list[Chunk], filename: str) -> int:
        path = self.directory / f"{filename}.jsonl"
        try:
            existing = parse_jsonl(path.read_text(encoding="utf-8")) if path.exists() else []
            merged = merge_chunks(existing, [asdict(c) for c in chunks])
            path.write_text(to_jsonl(merged), encoding="utf-8")   # replace, not append
            return len(chunks)
        except PermissionError as e:
            logger.error(f"permission denied {e}")
            return -1
        except OSError as e:
            logger.error(f"wrong path {e}")
            return -1

    def _save_s3(self, chunks: list[Chunk], filename: str) -> int:
        key = f"{self.prefix}{filename}.jsonl"           # same extension rule as local
        try:
            resp = self.s3.get_object(Bucket=self.bucket, Key=key)
            existing = parse_jsonl(resp["Body"].read().decode("utf-8"))
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":  # only "missing" counts as empty
                existing = []
            else:
                raise                                        # AccessDenied etc. must surface
        merged = merge_chunks(existing, [asdict(c) for c in chunks])
        self.s3.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=to_jsonl(merged).encode("utf-8"),
            ContentType="application/x-ndjson",
        )
        return len(chunks)

    def _load_s3(self) -> list[dict]:
        chunk_list = []
        paginator = self.s3.get_paginator("list_objects_v2")
        try:
            for page in paginator.paginate(Bucket=self.bucket, Prefix=self.prefix):
                for obj in page.get("Contents", []):          # empty pages have no "Contents"
                    key = obj["Key"]
                    if not key.endswith(".jsonl"):
                        continue
                    resp = self.s3.get_object(Bucket=self.bucket, Key=key)
                    text = resp["Body"].read().decode("utf-8")
                    try:
                        chunk_list.extend(parse_jsonl(text))
                    except json.JSONDecodeError as e:
                        raise ValueError(f"Bad JSONL in s3://{self.bucket}/{key}: {e}") from e
        except ClientError as e:
            logger.error(f"S3 load failed for s3://{self.bucket}/{self.prefix}: {e}")
            raise
        return chunk_list
        
    def stats(self) -> dict:
        chunks = self.load_all_chunks()
        by_source = {}
        by_company = {}
        for chunk in chunks:
            source = chunk["source"]
            company = chunk["company"]
            by_source[source] = by_source.get(source, 0) + 1
            by_company[company] = by_company.get(company, 0) + 1
        return {
            "total_chunks": len(chunks),
            "by_source": by_source,
            "by_company": by_company
        }
            
    def load_all_chunks(self) -> list[dict]:
        if self.bucket:
            return self._load_s3()
        return self._load_local()

    def _load_local(self) -> list[dict]:
        try:
            chunk_list = []
            for filepath in self.directory.glob("*.jsonl"):
                chunk_list.extend(parse_jsonl(filepath.read_text(encoding="utf-8")))
            return chunk_list
        except FileNotFoundError as e:
            logger.error(f"file not found {e}")
            return []
        except json.JSONDecodeError as e:
            logger.error(f"JSONDecodeError {e}")
            return []

