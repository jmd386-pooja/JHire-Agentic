import { NextResponse } from "next/server";
import { spawn } from "child_process";
import { PrismaClient } from "@prisma/client";
import crypto from "crypto";
import path from "path";
import fs from "fs/promises";

import { prisma } from "@/lib/prisma";

export const config = {
  api: { bodyParser: false },
};

// Helpers
function generateRandomString(length: number): string {
  return crypto.randomBytes(length).toString("hex").slice(0, length);
}
function generateUUID(): string {
  return crypto.randomUUID();
}
function calculateExpiryDate(
  baseDate?: Date | null,
  daysToAdd: number = 7
): Date {
  const date = baseDate ? new Date(baseDate) : new Date();
  return new Date(date.getTime() + daysToAdd * 24 * 60 * 60 * 1000);
}
async function readCsv(filePath: string): Promise<any[]> {
  const results: any[] = [];
  const data = await fs.readFile(filePath, "utf8");
  data
    .split("\n")
    .slice(1)
    .forEach((row) => {
      const columns = row.split(",");
      results.push({
        id: columns[0]?.trim(),
        gender: columns[2]?.trim(),
      });
    });
  return results;
}
function parseAsUTC(dateString: string): Date {
  if (dateString.endsWith("Z")) return new Date(dateString);
  return new Date(dateString + "Z");
}
// Normalize possibly-string-or-array into clean string[]
const toArray = (v: unknown): string[] => {
  if (Array.isArray(v)) {
    return v
      .filter((p) => p != null && String(p).trim() !== "")
      .map((p) => String(p).trim());
  }
  return v != null && String(v).trim() !== "" ? [String(v).trim()] : [];
};

export async function POST(req: Request) {
  try {
    // Read CSVs
    const avatars = await readCsv(path.join(process.cwd(), "data/avatars.csv"));
    const voices = await readCsv(path.join(process.cwd(), "data/voices.csv"));

    // Form data
    const formData = await req.formData();
    const files = formData.getAll("files");
    const college = formData.get("college")?.toString() || null;
    const examDate = formData.get("exam_date")?.toString() || null;
    const expiryDate = formData.get("expiry_date")?.toString() || null;
    const examDate1 = examDate ? parseAsUTC(examDate) : null;
    const expiryDate1 = expiryDate ? parseAsUTC(expiryDate) : null;

    if (!files || files.length === 0) {
      return NextResponse.json(
        { error: "No files uploaded." },
        { status: 400 }
      );
    }

    // Accumulators
    const candidates: any[] = [];
    const resumeDetailsPayloads: any[] = [];

    // Process each uploaded file via Python
    for (const file of files) {
      if (!(file instanceof File)) {
        return NextResponse.json(
          { error: "Invalid file uploaded." },
          { status: 400 }
        );
      }

      const arrayBuffer = await file.arrayBuffer();
      const buffer = Buffer.from(arrayBuffer);

      const python = spawn("python", ["scripts/extract_resume.py"]);
      let stdout = "";
      let stderr = "";

      python.stdin.write(buffer);
      python.stdin.end();

      python.stdout.on("data", (d) => (stdout += d.toString()));
      python.stderr.on("data", (d) => (stderr += d.toString()));

      await new Promise<void>((resolve, reject) => {
        python.on("close", (code) => {
          if (code === 0) resolve();
          else reject(new Error(stderr || "Python script failed"));
        });
      });

      // Only surface serious stderr (ignore DEBUG/INFO)
      if (stderr) {
        const serious = stderr
          .split(/\r?\n/)
          .filter((line) => line.trim() && !/^debug:|^info:/i.test(line))
          .join("\n");
        if (serious) console.warn(`Warning from Python script:\n${serious}`);
      }

      const result = JSON.parse(stdout);

      // Map & normalize model fields
      const name = result.name?.toString().trim() || "";
      const email = result.email?.toString().toLowerCase().trim() || "";
      const phoneRaw = result.phone ? String(result.phone) : "";
      const phoneDigits = phoneRaw.replace(/\D/g, "");
      const ph_number = phoneDigits ? BigInt(phoneDigits) : null;

      const skillsArr = toArray(result.skills);
      const projectsArr = toArray(result.projects);
      const certsArr = toArray(result.certifications);
      const expArr = toArray(result.experience);

      // Map YOP field names coming from Python -> Prisma schema fields
      const UG_college = result.UG_college ?? null;
      const UG_cgpa = result.UG_cgpa ?? null;
      const UG_yop = result.UG_year_of_passing ?? result.UG_yop ?? null;

      const PG_college = result.PG_college ?? null;
      const PG_cgpa = result.PG_cgpa ?? null;
      const PG_yop = result.PG_year_of_passing ?? result.PG_yop ?? null;

      const fileName = result.fileName || file.name;

      // Gender-based avatar/voice (fallback to 'male' unless your model adds gender)
      const gender = (result.gender || "male").toString().toLowerCase().trim();
      const matchingAvatars = avatars.filter(
        (a) =>
          typeof a.gender === "string" &&
          a.gender.toLowerCase().trim() === gender
      );
      const matchingVoices = voices.filter(
        (v) =>
          typeof v.gender === "string" &&
          v.gender.toLowerCase().trim() === gender
      );
      const selectedAvatar = matchingAvatars.length
        ? matchingAvatars[Math.floor(Math.random() * matchingAvatars.length)].id
        : null;
      const selectedVoice = matchingVoices.length
        ? matchingVoices[Math.floor(Math.random() * matchingVoices.length)].id
        : null;

      // Temp login + URL
      const tempName = generateUUID();
      const tempPassword = generateRandomString(12);
      const host = req.headers.get("host");
      const protocol = req.headers.get("x-forwarded-proto") || "http";
      const examUrl = `${protocol}://${host}/${tempName}`;

      // Expiry calculation
      const expiry = expiryDate1
        ? new Date(expiryDate1)
        : calculateExpiryDate(examDate1);

      // Candidate payload (Prisma Candidate)
      candidates.push({
        name,
        email,
        ph_number,
        Skills: skillsArr, // Candidate.Skills (String[])
        Avatar: selectedAvatar,
        Voice: selectedVoice,
        temp_name: tempName,
        tempPassword,
        Exam_URL: examUrl,
        College: college,
        Exam_date: examDate1 || null,
        Expiry: expiry,
      });

      // ResumeDetails payload (Prisma ResumeDetails)
      resumeDetailsPayloads.push({
        name,
        email,
        phone: phoneDigits,
        skills: skillsArr,
        UG_college: UG_college || undefined,
        UG_cgpa: UG_cgpa || undefined,
        UG_yop: UG_yop || undefined,
        PG_college: PG_college || undefined,
        PG_cgpa: PG_cgpa || undefined,
        PG_yop: PG_yop || undefined,
        projects: projectsArr,
        certifications: certsArr,
        experience: expArr,
        fileName,
      });
    }

    // Persist to DB (upsert per candidate)
    const insertedCandidates: any[] = [];

    for (let i = 0; i < candidates.length; i++) {
      const candidate = candidates[i];
      const detail = resumeDetailsPayloads[i];

      // Upsert Candidate
      const createdCandidate = await prisma.candidate.upsert({
        where: { email: candidate.email },
        update: candidate,
        create: candidate,
      });

      insertedCandidates.push({
        ...createdCandidate,
        ph_number: createdCandidate.ph_number?.toString() || null,
      });

      // Upsert ResumeDetails (1:1 on candidateId)
      await prisma.resumeDetails.upsert({
        where: { candidateId: createdCandidate.id },
        update: {
          // only updatable fields
          skills: detail.skills,
          UG_college: detail.UG_college,
          UG_cgpa: detail.UG_cgpa,
          UG_yop: detail.UG_yop,
          PG_college: detail.PG_college,
          PG_cgpa: detail.PG_cgpa,
          PG_yop: detail.PG_yop,
          projects: detail.projects,
          certifications: detail.certifications,
          experience: detail.experience,
          fileName: detail.fileName,
        },
        create: {
          candidateId: createdCandidate.id,
          name: detail.name,
          email: detail.email,
          phone: detail.phone,
          skills: detail.skills,
          UG_college: detail.UG_college,
          UG_cgpa: detail.UG_cgpa,
          UG_yop: detail.UG_yop,
          PG_college: detail.PG_college,
          PG_cgpa: detail.PG_cgpa,
          PG_yop: detail.PG_yop,
          projects: detail.projects,
          certifications: detail.certifications,
          experience: detail.experience,
          fileName: detail.fileName,
        },
      });

      // Upsert Interview (1:1 on candidate_id)
      const interviewDate = createdCandidate.Exam_date || new Date();
      await prisma.interview.upsert({
        where: { candidate_id: createdCandidate.id },
        update: {
          interview_date: interviewDate,
          status: "pending",
          Interviewscore: 0,
          Codingscore: 0,
          Answers: [],
          code: "",
          codeEvaluation: {},
          interview_start_time: null,
          questions: "",
        },
        create: {
          candidate_id: createdCandidate.id,
          interview_date: interviewDate,
          status: "pending",
          Interviewscore: null,
          Codingscore: null,
          Answers: [],
          code: "",
          created_at: new Date(),
          codeEvaluation: {},
          interview_start_time: null,
          questions: "",
        },
      });
    }

    return NextResponse.json({ data: insertedCandidates });
  } catch (error: any) {
    console.error("API Error:", error);
    return NextResponse.json(
      { error: error.message || "Unexpected error." },
      { status: 500 }
    );
  }
}
