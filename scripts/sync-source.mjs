import { cpSync, mkdirSync } from 'node:fs';
import { resolve } from 'node:path';

const root = resolve(import.meta.dirname, '..');
for (const [from, to] of [
  ['frontend', 'public'],
  ['backend/api', 'app/api'],
  ['backend/lib', 'lib'],
  ['backend/db', 'db'],
  ['backend/drizzle', 'drizzle'],
]) {
  mkdirSync(resolve(root, to), { recursive: true });
  cpSync(resolve(root, from), resolve(root, to), { recursive: true, force: true });
}
console.log('MeterGuard source synchronized for the framework.');
