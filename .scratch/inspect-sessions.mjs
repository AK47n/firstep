// Inspect dumped session JSONL: identify subagent sessions and review briefs.
import fs from 'node:fs';
import path from 'node:path';

const dir = process.argv[2] || '.scratch/session-dump';
const files = fs.readdirSync(dir).filter((f) => f.endsWith('.jsonl.txt')).sort();

for (const f of files) {
  const p = path.join(dir, f);
  const raw = fs.readFileSync(p, 'utf8');
  const lines = raw.split('\n').filter(Boolean);
  let header = null;
  try { header = JSON.parse(lines[0]); } catch {}
  let hasStandardsBrief = false;
  let hasSpecBrief = false;
  let lastAssistant = '';
  const events = [];
  for (const line of lines) {
    let ev;
    try { ev = JSON.parse(line); } catch { continue; }
    events.push(ev);
    const s = JSON.stringify(ev);
    if (s.includes('per file/hunk')) hasStandardsBrief = true;
    if (s.includes('requirements the spec asked for')) hasSpecBrief = true;
    if (ev.type === 'message' && ev.role === 'assistant' && typeof ev.content === 'string' && ev.content.trim()) {
      lastAssistant = ev.content;
    }
  }
  console.log('========================================');
  console.log(f);
  console.log('header:', header ? JSON.stringify({ id: header.id, origin: header.origin, parentSession: header.parentSession, delegationDepth: header.delegationDepth, agentPreset: header.agentPreset, createdAt: header.createdAt }) : 'n/a');
  console.log('events:', events.length, '| standardsBrief:', hasStandardsBrief, '| specBrief:', hasSpecBrief);
  if (lastAssistant) {
    console.log('last assistant (first 300):', lastAssistant.slice(0, 300).replace(/\n/g, ' '));
  }
}
