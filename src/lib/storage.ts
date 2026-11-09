import {
  S3Client,
  CreateMultipartUploadCommand,
  UploadPartCommand,
  CompleteMultipartUploadCommand,
  AbortMultipartUploadCommand,
  HeadObjectCommand,
  GetObjectCommand,
} from "@aws-sdk/client-s3";
import { getSignedUrl } from "@aws-sdk/s3-request-presigner";

export const PART_SIZE = 8 * 1024 * 1024;
export const MAX_FILE_SIZE = 1024 * 1024 * 1024;

let client: S3Client | undefined;

function storage() {
  if (!client) {
    if (!process.env.S3_BUCKET || !process.env.S3_ACCESS_KEY_ID || !process.env.S3_SECRET_ACCESS_KEY) {
      throw new Error("S3 environment is not configured");
    }
    client = new S3Client({
      endpoint: process.env.S3_ENDPOINT || undefined,
      region: process.env.S3_REGION || "us-east-1",
      forcePathStyle: process.env.S3_FORCE_PATH_STYLE === "true",
      credentials: {
        accessKeyId: process.env.S3_ACCESS_KEY_ID,
        secretAccessKey: process.env.S3_SECRET_ACCESS_KEY,
      },
    });
  }
  return client;
}

function bucket() {
  const name = process.env.S3_BUCKET;
  if (!name) throw new Error("S3_BUCKET is missing");
  return name;
}

export async function initiateUpload(key: string, contentType: string) {
  const output = await storage().send(new CreateMultipartUploadCommand({
    Bucket: bucket(), Key: key, ContentType: contentType,
  }));
  if (!output.UploadId) throw new Error("Storage upload ID missing");
  return output.UploadId;
}

export async function getPartUrl(key: string, uploadId: string, partNumber: number) {
  return getSignedUrl(storage(), new UploadPartCommand({
    Bucket: bucket(), Key: key, UploadId: uploadId, PartNumber: partNumber,
  }), { expiresIn: 900 });
}

export async function completeUpload(key: string, uploadId: string, parts: { partNumber: number; etag: string }[]) {
  await storage().send(new CompleteMultipartUploadCommand({
    Bucket: bucket(), Key: key, UploadId: uploadId,
    MultipartUpload: {
      Parts: parts.map((part) => ({ PartNumber: part.partNumber, ETag: part.etag })),
    },
  }));
}

export async function abortUpload(key: string, uploadId: string) {
  await storage().send(new AbortMultipartUploadCommand({
    Bucket: bucket(), Key: key, UploadId: uploadId,
  }));
}

export async function objectSize(key: string) {
  const head = await storage().send(new HeadObjectCommand({ Bucket: bucket(), Key: key }));
  return head.ContentLength;
}

export async function getReadUrl(key: string) {
  return getSignedUrl(storage(), new GetObjectCommand({ Bucket: bucket(), Key: key }), { expiresIn: 3600 });
}
