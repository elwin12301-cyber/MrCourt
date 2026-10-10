// Starts the isolated end-to-end API (fresh seeded database) using the backend virtualenv.
import { spawn } from 'node:child_process';
import { existsSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const backend = path.resolve(here, '../../../../backend');
const candidates = [
  path.join(backend, '.venv', 'Scripts', 'python.exe'),
  path.join(backend, '.venv', 'bin', 'python'),
];
const python = candidates.find(existsSync) ?? 'python';

const child = spawn(python, ['scripts/e2e_server.py'], { cwd: backend, stdio: 'inherit' });
child.on('exit', (code) => process.exit(code ?? 0));
for (const signal of ['SIGINT', 'SIGTERM']) process.on(signal, () => child.kill());
