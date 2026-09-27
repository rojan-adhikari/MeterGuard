CREATE TABLE `reviews` (
	`account_id` text PRIMARY KEY NOT NULL,
	`risk_level` text NOT NULL,
	`risk_score` real NOT NULL,
	`status` text DEFAULT 'New' NOT NULL,
	`notes` text DEFAULT '' NOT NULL,
	`result_json` text NOT NULL,
	`analyzed_at` text NOT NULL
);
