/*
  Warnings:

  - You are about to drop the column `education` on the `ResumeDetails` table. All the data in the column will be lost.

*/
-- AlterTable
ALTER TABLE "public"."ResumeDetails" DROP COLUMN "education",
ADD COLUMN     "PG_cgpa" TEXT,
ADD COLUMN     "PG_college" TEXT,
ADD COLUMN     "PG_yop" TEXT,
ADD COLUMN     "UG_cgpa" TEXT,
ADD COLUMN     "UG_college" TEXT,
ADD COLUMN     "UG_yop" TEXT,
ADD COLUMN     "email" TEXT,
ADD COLUMN     "fileName" TEXT,
ADD COLUMN     "name" TEXT,
ADD COLUMN     "phone" TEXT,
ADD COLUMN     "processedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
ADD COLUMN     "skills" TEXT[];
