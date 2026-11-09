"""Database-backed Python worker for AI highlights and burned-caption MP4 output."""
import logging
import os
import tempfile
import time
from pathlib import Path

import boto3
import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from media import probe, extract_audio, render
from planner import make_plan
from provider import AIProvider, decrypt_api_key

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOG = logging.getLogger("auto-edit-worker")


def connect():
    return psycopg.connect(os.environ["DATABASE_URL"], autocommit=True, row_factory=dict_row)


def claim(conn) -> dict | None:
    with conn.transaction():
        row = conn.execute('''
            SELECT j.id, j."projectId", j."ownerId", j."targetSeconds",
                   j.format, j.style, a."objectKey",
                   c."baseUrl", c."chatModel", c."transcriptionModel", c."encryptedApiKey"
            FROM "AutoEditJob" j
            JOIN "MediaAsset" a ON a.id = j."assetId"
            LEFT JOIN "AiProviderConfig" c ON c."userId" = j."ownerId"
            WHERE j.status = 'QUEUED'
            ORDER BY j."createdAt"
            LIMIT 1 FOR UPDATE OF j SKIP LOCKED
        ''').fetchone()
        if row:
            conn.execute('''
                UPDATE "AutoEditJob" SET status='RUNNING', progress=1, "updatedAt"=NOW()
                WHERE id=%s
            ''', (row["id"],))
        return row


def progress(conn, job_id: str, value: int):
    conn.execute('''
        UPDATE "AutoEditJob" SET progress=%s, "updatedAt"=NOW()
        WHERE id=%s AND status='RUNNING'
    ''', (value, job_id))


def storage():
    return boto3.client(
        "s3",
        endpoint_url=os.getenv("S3_ENDPOINT") or None,
        region_name=os.getenv("S3_REGION", "us-east-1"),
        aws_access_key_id=os.environ["S3_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["S3_SECRET_ACCESS_KEY"],
    )


def process(conn, job: dict):
    job_id = job["id"]
    if not job.get("encryptedApiKey"):
        raise ValueError("AI provider credentials are missing")
    client = AIProvider(job["baseUrl"], job["chatModel"], job["transcriptionModel"],
                        decrypt_api_key(job["encryptedApiKey"]))
    s3 = storage()
    bucket = os.environ["S3_BUCKET"]
    with tempfile.TemporaryDirectory(prefix="videoedit-") as folder:
        directory = Path(folder)
        extension = Path(job["objectKey"]).suffix.lower()
        if extension not in {".mp4", ".mov", ".webm"}:
            raise ValueError("Unsupported input media extension")
        source = directory / ("source" + extension)
        s3.download_file(bucket, job["objectKey"], str(source))
        progress(conn, job_id, 10)
        metadata = probe(source)
        audio = directory / "speech.mp3"
        extract_audio(source, audio)
        progress(conn, job_id, 25)
        transcript = client.transcribe(audio)
        progress(conn, job_id, 45)
        plan = make_plan(client, transcript, job["targetSeconds"], metadata["duration"], job["style"])
        conn.execute('''
            UPDATE "AutoEditJob" SET plan=%s, title=%s, progress=55, "updatedAt"=NOW()
            WHERE id=%s
        ''', (Jsonb(plan), plan["title"], job_id))
        result = directory / "output.mp4"
        render(source, result, plan, transcript, job["format"],
               progress=lambda p: progress(conn, job_id, p))
        progress(conn, job_id, 90)
        output_key = ("users/" + job["ownerId"] + "/projects/" + job["projectId"] +
                      "/exports/" + job_id + ".mp4")
        s3.upload_file(str(result), bucket, output_key,
                       ExtraArgs={"ContentType": "video/mp4"})
        progress(conn, job_id, 98)
        # Do not persist API keys, raw transcript, or unverified AI claims as separate output.
        conn.execute('''
            UPDATE "AutoEditJob"
            SET status='DONE', progress=100, "resultKey"=%s, error=NULL, "updatedAt"=NOW()
            WHERE id=%s
        ''', (output_key, job_id))
        LOG.info("Completed job %s: %s seconds", job_id, metadata["duration"])


def work_forever():
    LOG.info("Python auto-edit worker started")
    while True:
        try:
            with connect() as conn:
                job = claim(conn)
                if job:
                    LOG.info("Processing job %s", job["id"])
                    try:
                        process(conn, job)
                    except Exception as exc:
                        LOG.exception("Job %s failed", job["id"])
                        # Do not expose stack traces, credentials, or full response bodies to users.
                        reason = str(exc).replace("\n", " ")[:350]
                        conn.execute('''
                            UPDATE "AutoEditJob" SET status='FAILED', error=%s, "updatedAt"=NOW()
                            WHERE id=%s
                        ''', (reason, job["id"]))
                else:
                    time.sleep(3)
        except Exception:
            LOG.exception("Worker database connection error")
            time.sleep(6)


if __name__ == "__main__":
    work_forever()
