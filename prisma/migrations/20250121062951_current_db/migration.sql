/*
  Warnings:

  - The `status` column on the `Candidate` table would be dropped and recreated. This will lead to data loss if there is data in the column.
  - You are about to drop the column `tempExpiry` on the `User` table. All the data in the column will be lost.
  - You are about to drop the column `tempPassword` on the `User` table. All the data in the column will be lost.
  - A unique constraint covering the columns `[temp_name]` on the table `Candidate` will be added. If there are existing duplicate values, this will fail.

*/
-- AlterTable
ALTER TABLE "Candidate" ADD COLUMN     "College" TEXT,
ADD COLUMN     "Exam_URL" TEXT,
ADD COLUMN     "Exam_date" TIMESTAMP(3),
ADD COLUMN     "Expiry" TIMESTAMP(3),
ADD COLUMN     "tempPassword" TEXT,
ADD COLUMN     "temp_name" TEXT,
DROP COLUMN "status",
ADD COLUMN     "status" TEXT NOT NULL DEFAULT 'PENDING';

-- AlterTable
ALTER TABLE "User" DROP COLUMN "tempExpiry",
DROP COLUMN "tempPassword";

-- DropEnum
DROP TYPE "Status";

-- CreateTable
CREATE TABLE "Question" (
    "id" TEXT NOT NULL,
    "question" TEXT NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL,
    "constraints" TEXT[],
    "testcases" JSONB NOT NULL,
    "internalTestCases" JSONB NOT NULL,
    "title" TEXT,

    CONSTRAINT "Question_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Interview" (
    "id" TEXT NOT NULL,
    "candidate_id" INTEGER NOT NULL,
    "interview_date" TIMESTAMP(3) NOT NULL,
    "status" TEXT NOT NULL,
    "Interviewscore" INTEGER,
    "Codingscore" INTEGER,
    "Answers" TEXT[],
    "code" TEXT NOT NULL,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "codeEvaluation" JSONB NOT NULL,
    "interview_start_time" TIMESTAMP(3),
    "questions" TEXT,

    CONSTRAINT "Interview_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Feedback" (
    "id" TEXT NOT NULL,
    "interview_id" TEXT NOT NULL,
    "ratings" INTEGER NOT NULL DEFAULT 0,
    "provided_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "feedback_text" JSONB NOT NULL,

    CONSTRAINT "Feedback_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "Question_id_key" ON "Question"("id");

-- CreateIndex
CREATE UNIQUE INDEX "Interview_id_key" ON "Interview"("id");

-- CreateIndex
CREATE UNIQUE INDEX "Interview_candidate_id_key" ON "Interview"("candidate_id");

-- CreateIndex
CREATE UNIQUE INDEX "Feedback_id_key" ON "Feedback"("id");

-- CreateIndex
CREATE UNIQUE INDEX "Feedback_interview_id_key" ON "Feedback"("interview_id");

-- CreateIndex
CREATE UNIQUE INDEX "Candidate_temp_name_key" ON "Candidate"("temp_name");

-- AddForeignKey
ALTER TABLE "Interview" ADD CONSTRAINT "Interview_candidate_id_fkey" FOREIGN KEY ("candidate_id") REFERENCES "Candidate"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Feedback" ADD CONSTRAINT "Feedback_interview_id_fkey" FOREIGN KEY ("interview_id") REFERENCES "Interview"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
