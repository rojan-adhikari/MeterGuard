import { env } from 'cloudflare:workers';
export function db(){if(!env.DB)throw new Error('Review storage is unavailable');return env.DB}
