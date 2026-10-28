const fs = require('node:fs');
const path = require('node:path');
const { execFileSync } = require('node:child_process');
const root = path.resolve(__dirname, '../../..');
const local = path.join(root, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
execFileSync(fs.existsSync(local) ? local : 'python', ['scripts/seed-demo-users.py', '--ui'], { cwd: root, stdio: 'inherit' });
