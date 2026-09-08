// One-off helper: decompress (multi-frame) DSH session.jsonl.zstd files for inspection.
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';

const require = createRequire('C:/Users/luoji/AppData/Local/DSH Desktop/dsh-desktop/package.json');
const { ZSTDDecoder } = require('zstddec/stream');

const base = process.argv[2];
const outDir = process.argv[3] || '.scratch/session-dump';
fs.mkdirSync(outDir, { recursive: true });

const decoder = new ZSTDDecoder();
await decoder.init();

const entries = fs.readdirSync(base, { withFileTypes: true });
let count = 0;
for (const e of entries) {
  if (!e.isDirectory()) continue;
  const src = path.join(base, e.name, 'session.jsonl.zstd');
  if (!fs.existsSync(src)) continue;
  const st = fs.statSync(src);
  if (Date.now() - st.mtimeMs > 1000 * 60 * 120) continue;
  const buf = decoder.decode(new Uint8Array(fs.readFileSync(src)), 0);
  const dst = path.join(outDir, e.name + '.jsonl.txt');
  fs.writeFileSync(dst, buf);
  const firstLine = buf.toString('utf8').split('\n')[0];
  console.log(`${dst}\t${buf.length}\t${firstLine.slice(0, 220)}`);
  count++;
}
console.log(`decompressed=${count}`);
