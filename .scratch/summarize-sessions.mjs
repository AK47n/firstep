// Extract user/message and assistant/message contents from session JSONL dumps.
import fs from 'node:fs';
import path from 'node:path';

const files = process.argv.slice(2);
for (const f of files) {
  const raw = fs.readFileSync(f, 'utf8');
  const lines = raw.split('\n').filter(Boolean);
  console.log('\n################ ' + path.basename(f) + ' ################');
  const events = [];
  for (const line of lines) {
    try { events.push(JSON.parse(line)); } catch {}
  }
  const users = events.filter((e) => e.type === 'user/message');
  const assts = events.filter((e) => e.type === 'assistant/message');
  console.log('user/message count:', users.length, '| assistant/message count:', assts.length);
  users.forEach((e, i) => {
    const d = e.data || {};
    const c = typeof d.content === 'string' ? d.content : JSON.stringify(d.content ?? d);
    console.log(`\n--- USER[${i}] (${c.length} chars) ---`);
    console.log(c.slice(0, 1200));
  });
  assts.forEach((e, i) => {
    if (i < Math.max(0, assts.length - 1)) return; // only last
    const d = e.data || {};
    const c = typeof d.content === 'string' ? d.content : JSON.stringify(d.content ?? d);
    console.log(`\n--- LAST ASSISTANT[${i}] (${c.length} chars) ---`);
    console.log(c.slice(0, 4000));
  });
}
