import { NextResponse } from 'next/server';
import { db } from './db';
import { scoreReadings, type Reading } from './data';
export function errorResponse(error:unknown){const msg=error instanceof Error?error.message:'Unable to process request';const client=/missing|invalid|Expected|Upload|CSV|reading|Limit|account|timestamp|kWh|values|negative|72|timezone/i.test(msg);return NextResponse.json({detail:msg},{status:client?422:503})}
export async function analyze(readings:Reading[]){const scored=scoreReadings(readings),stamp=new Date().toISOString();
 for(const r of scored.results){await db().prepare(`INSERT INTO reviews (account_id,risk_level,risk_score,status,notes,result_json,analyzed_at)
 VALUES (?,?,?,'New','',?,?) ON CONFLICT(account_id) DO UPDATE SET risk_level=excluded.risk_level,risk_score=excluded.risk_score,result_json=excluded.result_json,analyzed_at=excluded.analyzed_at`).bind(r.account_id,r.risk_level,r.risk_score,JSON.stringify(r),stamp).run()}
 return {results:scored.results,quality:scored.quality,analyzed_at:stamp,model:'Logistic Regression'}
}
