import { NextRequest, NextResponse } from 'next/server';
import prisma from '@/lib/prisma';

export async function GET(
  req: NextRequest,
  context: { params: Promise<{ uniqueId: string; action: string }> }
) {
  try {
    // Await the params as Next.js requires
    const { uniqueId, action } = await context.params;

    if (!uniqueId || !action) {
      return NextResponse.json(
        { message: 'Missing uniqueId or action' },
        { status: 400 }
      );
    }

    if (!['accept', 'decline'].includes(action)) {
      return NextResponse.json(
        { message: 'Invalid action' },
        { status: 400 }
      );
    }

    // Parse uniqueId to integer
    const candidateId = parseInt(uniqueId, 10);

    // Validate if the parsing was successful
    if (isNaN(candidateId)) {
      return NextResponse.json(
        { message: 'Invalid uniqueId format' },
        { status: 400 }
      );
    }

    const updatedCandidate = await prisma.candidate.update({
      where: { id: candidateId },
      data: {
        status: action === 'accept' ? 'ACCEPTED' : 'DECLINED',
      },
    });

    if (!updatedCandidate) {
      return NextResponse.json(
        { message: 'Candidate not found' },
        { status: 404 }
      );
    }
        // Conditional message formatting
    const actionMessage =
        action === 'accept'
          ? `Invitation ${action}ed for candidate ${updatedCandidate.name}`
          : `Invitation ${action}d for candidate ${updatedCandidate.name}`;

    return NextResponse.json(
      {
        uniqueId,
        message: actionMessage,
      },
      { status: 200 }
    );
  } catch (error) {
    console.error('Error processing candidate action:', error);

    // Check if the error is a Prisma error
    if (error instanceof Error && error.name === 'PrismaClientKnownRequestError') {
      return NextResponse.json(
        { message: 'Database operation failed', error: error.message },
        { status: 400 }
      );
    }

    return NextResponse.json(
      {
        message: 'An error occurred while processing the request',
        error: error instanceof Error ? error.message : 'Unknown error',
      },
      { status: 500 }
    );
  }
}