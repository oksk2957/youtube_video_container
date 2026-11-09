import { prisma } from "@/lib/db";

export async function ownedProject(projectId: string, userId: string) {
  return prisma.project.findFirst({ where: { id: projectId, ownerId: userId } });
}

export async function ownedAsset(assetId: string, userId: string) {
  return prisma.mediaAsset.findFirst({
    where: { id: assetId, project: { ownerId: userId } },
    include: { project: true, uploadSession: true },
  });
}
