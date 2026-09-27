import { NextResponse } from 'next/server';import report from '../../../lib/evaluation.json';
export async function GET(){return NextResponse.json(report)}
