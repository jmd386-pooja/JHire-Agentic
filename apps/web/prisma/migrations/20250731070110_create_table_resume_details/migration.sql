-- CreateTable
CREATE TABLE "public"."ResumeDetails" (
    "id" SERIAL NOT NULL,
    "candidateId" INTEGER NOT NULL,
    "education" TEXT,
    "projects" TEXT[],
    "certifications" TEXT[],
    "experience" TEXT,

    CONSTRAINT "ResumeDetails_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "ResumeDetails_candidateId_key" ON "public"."ResumeDetails"("candidateId");

-- AddForeignKey
ALTER TABLE "public"."ResumeDetails" ADD CONSTRAINT "ResumeDetails_candidateId_fkey" FOREIGN KEY ("candidateId") REFERENCES "public"."Candidate"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
