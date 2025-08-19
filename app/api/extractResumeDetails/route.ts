import { NextResponse } from 'next/server';
import { spawn } from 'child_process';
import { PrismaClient } from '@prisma/client';
import crypto from 'crypto';
import path from 'path';
import fs from 'fs/promises';
import { string } from 'zod';

const prisma = new PrismaClient();

export const config = {
  api: {
    bodyParser: false,
  },
};

// Helper function to generate a random string
function generateRandomString(length: number): string {
  return crypto.randomBytes(length).toString('hex').slice(0, length);
}

// Helper function to generate a UUID
function generateUUID(): string {
  return crypto.randomUUID();
}

// Calculate expiry date
function calculateExpiryDate(baseDate?: Date | null, daysToAdd: number = 7): Date {
  const date = baseDate ? new Date(baseDate) : new Date();
  return new Date(date.getTime() + daysToAdd * 24 * 60 * 60 * 1000); // Add specified days
}

// Read CSV helper function
async function readCsv(filePath: string): Promise<any[]> {
  const results: any[] = [];
  return new Promise((resolve, reject) => {
    fs.readFile(filePath, 'utf8')
      .then((data) => {
        data
          .split('\n')
          .slice(1) // Skip the header row
          .forEach((row) => {
            const columns = row.split(',');
            results.push({
              id: columns[0]?.trim(),
              gender: columns[2]?.trim(),
            });
          });
        resolve(results);
      })
      .catch((err) => reject(err));
  });
}

function parseAsUTC(dateString: string): Date {
  if(dateString.endsWith('Z'))
    return new Date(dateString);
  return new Date(dateString + 'Z'); // Appends 'Z' to treat it as UTC
}

export async function POST(req: Request) {
  try {
    // Read CSV files for avatars and voices
    const avatars = await readCsv(path.join(process.cwd(), 'data/avatars.csv'));
    const voices = await readCsv(path.join(process.cwd(), 'data/voices.csv'));

    // Retrieve the form data
    const formData = await req.formData();
    const files = formData.getAll('files');
    const college = formData.get('college')?.toString() || null;
    const examDate = formData.get('exam_date')?.toString() || null;
    const expiryDate = formData.get('expiry_date')?.toString() || null;
    const examDate1 = examDate ? parseAsUTC(examDate) : null;
    const expiryDate1 = expiryDate ? parseAsUTC(expiryDate) : null;

    if (!files || files.length === 0) {
      return NextResponse.json({ error: 'No files uploaded.' }, { status: 400 });
    }

    const candidates = [];
    const resumeDetails: {
      education?: string;
      projects: string[];
      certifications: string[];
      experience: string[];
    }[] = [];

    for (const file of files) {
      if (!(file instanceof File)) {
        return NextResponse.json({ error: 'Invalid file uploaded.' }, { status: 400 });
      }

      // Convert file to buffer
      const arrayBuffer = await file.arrayBuffer();
      const buffer = Buffer.from(arrayBuffer);

      // Spawn Python process and pass the buffer via stdin
      const pythonProcess = spawn('python', ['scripts/extract_resume.py']);
      let stdout = '';
      let stderr = '';

      pythonProcess.stdin.write(buffer); // Pass buffer via stdin
      pythonProcess.stdin.end();

      pythonProcess.stdout.on('data', (data) => {
        stdout += data.toString();
      });

      pythonProcess.stderr.on('data', (data) => {
        stderr += data.toString();
      });

      const pythonExit = new Promise<void>((resolve, reject) => {
        pythonProcess.on('close', (code) => {
          if (code === 0) {
            resolve();
          } else {
            reject(new Error(stderr || 'Python script failed'));
          }
        });
      });

      await pythonExit;

      if (stderr) {
        console.warn(`Warning from Python script: ${stderr}`);
      }

      const result = JSON.parse(stdout);

      // Match avatars and voices by gender
      const matchingAvatars = avatars.filter(
      (avatar) =>
        typeof avatar.gender === 'string' &&
        avatar.gender?.toLowerCase().trim() === 'male'
    );

    const matchingVoices = voices.filter(
      (voice) =>
        typeof voice.gender === 'string' &&
        voice.gender?.toLowerCase().trim() === 'male'
    );


      // Select random avatar and voice
      const selectedAvatar = matchingAvatars.length
        ? matchingAvatars[Math.floor(Math.random() * matchingAvatars.length)].id
        : null;

      const selectedVoice = matchingVoices.length
        ? matchingVoices[Math.floor(Math.random() * matchingVoices.length)].id
        : null;

      const tempName = generateUUID();

      // Generate random tempPassword
      const tempPassword = generateRandomString(12);

      // Construct Exam_URL
      const host = req.headers.get('host');
      const protocol = req.headers.get('x-forwarded-proto') || 'http'; // fallback for local
      const examUrl = `${protocol}://${host}/${tempName}`;

      // Determine expiry date
      const expiry = expiryDate1
        ? new Date(expiryDate1)
        : calculateExpiryDate(examDate1);

      if (result) {
        candidates.push({
          name: result.name,
          email: result.email.toLowerCase().trim(),
          ph_number: result.phone
            ? BigInt(result.phone.replace(/\D/g, ''))
            : null,
          Skills: result.skills,
          Avatar: selectedAvatar,
          Voice: selectedVoice,
          temp_name: tempName,
          tempPassword: tempPassword,
          Exam_URL: examUrl,
          College: college,
          Exam_date: examDate1 ? examDate1 : null,
          Expiry: expiry,
        });
        resumeDetails.push({
          education: result.education,
          projects: result.projects,
          certifications: result.certifications,
          experience: result.experience
        });
      }
    }

    const insertedCandidates = [];
    const insertedResumeDetails = [];
    const interviews = [];

    for (const candidate of candidates) {
      try {
        const createdCandidate = await prisma.candidate.upsert({
          where: { email: candidate.email },
          update: candidate,
          create: candidate,
        });
        insertedCandidates.push({
          ...createdCandidate,
          ph_number: createdCandidate.ph_number?.toString() || null,
        });

        const i = insertedCandidates.length - 1;
        const detail = resumeDetails[i];

        let projects: string[] = [];
        let certifications: string[] = [];
        let experience: string[] = [];

        if(detail.projects) {
          projects = Array.isArray(detail.projects) ? 
          detail.projects.filter(p => p != undefined || p != null) : 
          [detail.projects]
        }
        if(detail.certifications) {
          certifications = Array.isArray(detail.certifications) ? 
          detail.certifications.filter(p => p != undefined || p != null) : 
          [detail.certifications]
        }
        if(detail.experience) {
          experience = Array.isArray(detail.experience) ? 
          detail.experience.filter(p => p != undefined || p != null) : 
          [detail.experience]
        }

        // const projects = Array.isArray(detail.projects) ? detail.projects : [detail.projects];
        // const certifications = Array.isArray(detail.certifications) ? detail.certifications : [detail.certifications];
        // const experience = Array.isArray(detail.experience) ? detail.experience : [detail.experience];

        const upsertResumeDetails = await prisma.resumeDetails.upsert({
          where: { candidateId: createdCandidate.id },
          update: {
            education: detail.education || '',
            projects: projects || [],
            certifications: certifications || [],
            experience: experience || [],
          },
          create: {
            candidateId: createdCandidate.id,
            education: detail.education || '',
            projects: projects || [],
            certifications: certifications || [],
            experience: experience || [],
          },
        });

        insertedResumeDetails.push(upsertResumeDetails);

        const interviewDate = candidate.Exam_date || new Date();

        // Upsert into the Interview table
        const upsertedInterview = await prisma.interview.upsert({
          where: { candidate_id: createdCandidate.id },
          update: {
            interview_date: interviewDate, // Update interview_date if already exists
            status: 'pending', // Update status to pending
            Interviewscore: 0, // Default value
            Codingscore: 0, // Default value
            Answers: [], // Default empty array for answers
            code: '', // Default empty string for code
            codeEvaluation: {}, // Default empty JSON object for code evaluation
            interview_start_time: null, // Default to null
            questions: '', // Default empty string for questions
          },
          create: {
            candidate_id: createdCandidate.id, // Associate with the candidate
            interview_date: interviewDate, // Set interview_date
            status: 'pending', // Default status
            Interviewscore: null, // Default value
            Codingscore: null, // Default value
            Answers: [], // Default empty array for answers
            code: '', // Default empty string for code
            created_at: new Date(), // Automatically set the created_at timestamp
            codeEvaluation: {}, // Default empty JSON object for code evaluation
            interview_start_time: null, // Default to null
            questions: '', // Default empty string for questions
          },
        });

        interviews.push(upsertedInterview);
      } catch (error) {
        console.error(`Error inserting candidate: ${candidate.email}`, error);
      }
    }

    return NextResponse.json({ data: insertedCandidates });
  } catch (error: any) {
    console.error('API Error:', error);
    return NextResponse.json(
      { error: error.message || 'Unexpected error.' },
      { status: 500 }
    );
  }
}