import { NextResponse } from 'next/server';
import { getApiDocs } from '../../../utils/swagger';

export async function GET() {
  return NextResponse.json(getApiDocs());
}
