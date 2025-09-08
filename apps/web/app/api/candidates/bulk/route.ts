import { NextResponse } from 'next/server';
import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const candidates = await prisma.candidate.findMany();
    const formattedCandidates = candidates.map((candidate) => ({
      ...candidate,
      ph_number: candidate.ph_number?.toString(),
    }));
    return NextResponse.json({ data: formattedCandidates }, { status: 200 });
  } catch (error) {
    console.error('Error fetching candidates:', error);
    return NextResponse.json(
      { error: 'Failed to fetch candidates.' },
      { status: 500 }
    );
  }
}


const addTimeOffset = (date: string | null): string | null => {
  if (!date) return null;

  // Parse the input as a local time (ignores timezone offset)
  const [datePart, timePart] = date.split('T');
  const [year, month, day] = datePart.split('-').map(Number);
  const [hour, minute] = timePart.split(':').map(Number);

  // Create a Date object in local time
  const localDate = new Date(year, month - 1, day, hour, minute);

  // Add 5 hours and 30 minutes
  localDate.setMinutes(localDate.getMinutes() + (5 * 60 + 30));

  // Convert back to ISO format without the timezone part
  const adjustedYear = localDate.getFullYear();
  const adjustedMonth = String(localDate.getMonth() + 1).padStart(2, '0');
  const adjustedDate = String(localDate.getDate()).padStart(2, '0');
  const adjustedHour = String(localDate.getHours()).padStart(2, '0');
  const adjustedMinute = String(localDate.getMinutes()).padStart(2, '0');

  return `${adjustedYear}-${adjustedMonth}-${adjustedDate}T${adjustedHour}:${adjustedMinute}`;
};


export async function PATCH(req: Request) {
  try {
    const { id, name, email, ph_number, College, Exam_date, Expiry, status } = await req.json();

    // Add 5:30 to Exam_date and Expiry
    const updatedExamDate = addTimeOffset(Exam_date);
    const updatedExpiry = addTimeOffset(Expiry);


    if (!id) throw new Error('ID is required.');

    // Convert local date-time string to a UTC Date object
    const toUTC = (date: string | null) => {
      if (!date) return null;
      const localDate = new Date(date);

      // Set the local date in UTC timezone
      return new Date(localDate.getTime() - localDate.getTimezoneOffset() * 60000);
    };

    const updateData = {
      name,
      email,
      ph_number: ph_number ? BigInt(ph_number) : null,
      College,
      Exam_date: toUTC(updatedExamDate),
      Expiry: toUTC(updatedExpiry),
      status:"PENDING",
    };

    const updatedCandidate = await prisma.candidate.update({
      where: { id },
      data: updateData,
    });

    const formattedCandidate = {
      ...updatedCandidate,
      ph_number: updatedCandidate.ph_number?.toString(),
    };

    return NextResponse.json({ data: formattedCandidate }, { status: 200 });
  } catch (error) {
    console.error('Error updating candidate:', error);
    return NextResponse.json(
      { error: 'Failed to update candidate.' },
      { status: 500 }
    );
  }
}

