// Show tail events of a session dump, focusing on text-chunks / turn/end / assistant/message.
import fs from 'node:fs';
import path from 'node:path';

const f = process.argv[2];
const raw = fs.readFileSync(f, 'utf8');
const events = raw.split('\n').filter(Boolean).map((l) => { try { return JSON.parse(l); } catch { return null; } }).filter(Boolean);
console.log('total events:', events.length);

const typesOfInterest = ['text-chunks', 'turn/end', 'assistant/message', 'turn/start', 'step/end'];
for (let i = events.length - 1; i >= 0 && i >= events.length - 40; i--) {
  const ev = events[i];
  if (!typesOfInterest.includes(ev.type)) continue;
  console.log('\n--- [' + i + '] ' + ev.type + ' seq=' + ev.seq + ' time=' + ev.time);
  const d = ev.data ?? ev;
  const s = JSON.stringify(d);
  console.log(s.slice(0, 3000));
}
