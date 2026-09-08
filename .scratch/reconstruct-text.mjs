// Reconstruct streamed final text from text-chunks events of a session dump.
import fs from 'node:fs';
import path from 'node:path';

const f = process.argv[2];
const out = process.argv[3];
const raw = fs.readFileSync(f, 'utf8');
const events = raw.split('\n').filter(Boolean).map((l) => { try { return JSON.parse(l); } catch { return null; } }).filter(Boolean);

const chunks = events.filter((e) => e.type === 'text-chunks');
let text = '';
let prevIndex = -1;
const parts = [];
for (const e of chunks) {
  const d = e.data ?? e;
  const i = d.index ?? 0;
  if (i < prevIndex) console.error('WARN index went backwards');
  prevIndex = i;
  for (const t of d.texts ?? []) parts.push(t);
}
// Note: parts are text fragments; dt suggests incremental typing but texts may be fragments already.
text = parts.join('');
console.log('text-chunks count:', chunks.length, '| reconstructed length:', text.length);
if (out) {
  fs.writeFileSync(out, text, 'utf8');
  console.log('written:', out);
}
const last = events[events.length - 1];
console.log('last event:', last.type, JSON.stringify(last.data ?? {}).slice(0, 200));
console.log('has turn/end:', events.some((e) => e.type === 'turn/end'));
console.log('---- reconstructed head ----');
console.log(text.slice(0, 1200));
console.log('---- reconstructed tail ----');
console.log(text.slice(-1200));
