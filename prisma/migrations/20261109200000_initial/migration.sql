-- Initial schema: existing editor, authenticated projects, AI provider and rendering jobs.
CREATE TYPE "AssetStatus" AS ENUM ('UPLOADING', 'READY', 'FAILED');

CREATE TABLE "User" (
 "id" TEXT NOT NULL,
 "githubId" TEXT NOT NULL,
 "login" TEXT NOT NULL,
 "avatarUrl" TEXT,
 "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
 CONSTRAINT "User_pkey" PRIMARY KEY ("id")
);
CREATE TABLE "Session" (
 "id" TEXT NOT NULL,
 "tokenHash" TEXT NOT NULL,
 "userId" TEXT NOT NULL,
 "expiresAt" TIMESTAMP(3) NOT NULL,
 "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
 CONSTRAINT "Session_pkey" PRIMARY KEY ("id")
);
CREATE TABLE "Project" (
 "id" TEXT NOT NULL,
 "ownerId" TEXT NOT NULL,
 "name" TEXT NOT NULL,
 "timeline" JSONB NOT NULL,
 "revision" INTEGER NOT NULL DEFAULT 0,
 "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
 "updatedAt" TIMESTAMP(3) NOT NULL,
 CONSTRAINT "Project_pkey" PRIMARY KEY ("id")
);
CREATE TABLE "MediaAsset" (
 "id" TEXT NOT NULL,
 "projectId" TEXT NOT NULL,
 "objectKey" TEXT NOT NULL,
 "fileName" TEXT NOT NULL,
 "contentType" TEXT NOT NULL,
 "bytes" BIGINT NOT NULL,
 "status" "AssetStatus" NOT NULL DEFAULT 'UPLOADING',
 "durationMs" INTEGER,
 "width" INTEGER,
 "height" INTEGER,
 "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
 CONSTRAINT "MediaAsset_pkey" PRIMARY KEY ("id")
);
CREATE TABLE "UploadSession" (
 "id" TEXT NOT NULL,
 "assetId" TEXT NOT NULL,
 "uploadId" TEXT NOT NULL,
 "partSize" INTEGER NOT NULL,
 "status" TEXT NOT NULL DEFAULT 'UPLOADING',
 "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
 CONSTRAINT "UploadSession_pkey" PRIMARY KEY ("id")
);
CREATE TABLE "AiProviderConfig" (
 "userId" TEXT NOT NULL,
 "baseUrl" TEXT NOT NULL,
 "chatModel" TEXT NOT NULL,
 "transcriptionModel" TEXT NOT NULL,
 "encryptedApiKey" TEXT NOT NULL,
 "updatedAt" TIMESTAMP(3) NOT NULL,
 CONSTRAINT "AiProviderConfig_pkey" PRIMARY KEY ("userId")
);
CREATE TABLE "AutoEditJob" (
 "id" TEXT NOT NULL,
 "projectId" TEXT NOT NULL,
 "assetId" TEXT NOT NULL,
 "ownerId" TEXT NOT NULL,
 "format" TEXT NOT NULL,
 "style" TEXT NOT NULL,
 "targetSeconds" INTEGER NOT NULL,
 "status" TEXT NOT NULL DEFAULT 'QUEUED',
 "progress" INTEGER NOT NULL DEFAULT 0,
 "title" TEXT,
 "plan" JSONB,
 "resultKey" TEXT,
 "error" TEXT,
 "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
 "updatedAt" TIMESTAMP(3) NOT NULL,
 CONSTRAINT "AutoEditJob_pkey" PRIMARY KEY ("id")
);
CREATE UNIQUE INDEX "User_githubId_key" ON "User"("githubId");
CREATE UNIQUE INDEX "Session_tokenHash_key" ON "Session"("tokenHash");
CREATE INDEX "Session_userId_idx" ON "Session"("userId");
CREATE INDEX "Session_expiresAt_idx" ON "Session"("expiresAt");
CREATE INDEX "Project_ownerId_updatedAt_idx" ON "Project"("ownerId", "updatedAt");
CREATE UNIQUE INDEX "MediaAsset_objectKey_key" ON "MediaAsset"("objectKey");
CREATE INDEX "MediaAsset_projectId_createdAt_idx" ON "MediaAsset"("projectId", "createdAt");
CREATE UNIQUE INDEX "UploadSession_assetId_key" ON "UploadSession"("assetId");
CREATE INDEX "AutoEditJob_status_createdAt_idx" ON "AutoEditJob"("status", "createdAt");
CREATE INDEX "AutoEditJob_ownerId_createdAt_idx" ON "AutoEditJob"("ownerId", "createdAt");
ALTER TABLE "Session" ADD CONSTRAINT "Session_userId_fkey" FOREIGN KEY ("userId") REFERENCES "User"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "Project" ADD CONSTRAINT "Project_ownerId_fkey" FOREIGN KEY ("ownerId") REFERENCES "User"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "MediaAsset" ADD CONSTRAINT "MediaAsset_projectId_fkey" FOREIGN KEY ("projectId") REFERENCES "Project"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "UploadSession" ADD CONSTRAINT "UploadSession_assetId_fkey" FOREIGN KEY ("assetId") REFERENCES "MediaAsset"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "AiProviderConfig" ADD CONSTRAINT "AiProviderConfig_userId_fkey" FOREIGN KEY ("userId") REFERENCES "User"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "AutoEditJob" ADD CONSTRAINT "AutoEditJob_projectId_fkey" FOREIGN KEY ("projectId") REFERENCES "Project"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "AutoEditJob" ADD CONSTRAINT "AutoEditJob_assetId_fkey" FOREIGN KEY ("assetId") REFERENCES "MediaAsset"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "AutoEditJob" ADD CONSTRAINT "AutoEditJob_ownerId_fkey" FOREIGN KEY ("ownerId") REFERENCES "User"("id") ON DELETE CASCADE ON UPDATE CASCADE;
