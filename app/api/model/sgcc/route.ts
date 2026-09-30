import { NextResponse } from 'next/server';import report from '../../../../lib/sgcc-evaluation.json';
export async function GET(){return NextResponse.json(report)}
