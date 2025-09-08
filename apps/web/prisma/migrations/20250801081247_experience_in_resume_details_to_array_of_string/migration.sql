/*
  Warnings:

  - The `experience` column on the `ResumeDetails` table would be dropped and recreated. This will lead to data loss if there is data in the column.

*/
-- AlterTable
ALTER TABLE "public"."ResumeDetails" DROP COLUMN "experience",
ADD COLUMN     "experience" TEXT[];
