import { sqliteTable, text, real } from 'drizzle-orm/sqlite-core';
export const reviews = sqliteTable('reviews', {
 accountId: text('account_id').primaryKey(),
 riskLevel: text('risk_level').notNull(),
 riskScore: real('risk_score').notNull(),
 status: text('status').notNull().default('New'),
 notes: text('notes').notNull().default(''),
 evidenceJson: text('evidence_json').notNull().default('{}'),
 resultJson: text('result_json').notNull(),
 analyzedAt: text('analyzed_at').notNull(),
});
