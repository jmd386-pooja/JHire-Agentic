/*
  Warnings:

  - You are about to drop the column `resumeUrl` on the `Candidate` table. All the data in the column will be lost.

*/
-- AlterTable
ALTER TABLE "Candidate" DROP COLUMN "resumeUrl",
ADD COLUMN     "Avatar" TEXT,
ADD COLUMN     "Voice" TEXT,
ADD COLUMN     "resume_embedding" vector(1536);
