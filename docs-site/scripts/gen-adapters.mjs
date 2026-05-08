// Walk src/gracekelly/adapters/**/*.py, find concrete classes subclassing
// ExecutionAdapter or BaseApiAdapter, and emit a table of registered
// execution adapters with transports + lifecycle hooks. Regex-based, no
// Python runtime, no Playwright import.

import { readdir, readFile, writeFile, mkdir } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { dirname, extname, join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = join(__dirname, '..', '..');
const ADAPTERS_DIR = join(PROJECT_ROOT, 'src', 'gracekelly', 'adapters');
const OUT_FILE = join(__dirname, '..', 'src', 'content', 'docs', 'architecture', 'adapters.mdx');

const CLASS_RE = /^class\s+(\w+)\s*\(([^)]+)\)\s*:/gm;
const NAME_RE = /^\s{4}name(?:\s*:\s*[^=]+)?\s*=\s*["']([^"']+)["']/m;
const HOOKS = ['execute', 'execute_async', 'execute_stream', 'refresh_model_catalog', 'close', 'aclose', 'healthcheck'];

const BASE_CLASSES = new Set(['ExecutionAdapter', 'BaseApiAdapter']);

function transportFromPath(relPath) {
  const norm = relPath.replace(/\\/g, '/');
  if (norm.includes('/browser/')) return 'browser (Playwright)';
  if (norm.includes('/api/')) return 'HTTP API';
  if (norm.endsWith('/dry_run.py') || norm.endsWith('dry_run.py')) return 'in-process (dry-run)';
  return 'other';
}

async function walk(dir) {
  const entries = await readdir(dir, { withFileTypes: true });
  const out = [];
  for (const e of entries) {
    if (e.name.startsWith('__pycache__')) continue;
    const full = join(dir, e.name);
    if (e.isDirectory()) {
      out.push(...(await walk(full)));
    } else if (extname(e.name) === '.py' && !e.name.startsWith('_')) {
      out.push(full);
    }
  }
  return out;
}

function classBody(content, classStartIdx) {
  const rest = content.slice(classStartIdx);
  const firstLineEnd = rest.indexOf('\n');
  const afterFirstLine = firstLineEnd === -1 ? rest.length : firstLineEnd + 1;
  const tail = rest.slice(afterFirstLine);
  const next = tail.search(/^class\s+\w+/m);
  return next === -1 ? rest : rest.slice(0, afterFirstLine + next);
}

function detectHooks(body) {
  const found = [];
  for (const h of HOOKS) {
    const re = new RegExp(`^\\s{4}(?:async\\s+)?def\\s+${h}\\s*\\(`, 'm');
    if (re.test(body)) found.push(h);
  }
  return found;
}

async function main() {
  if (!existsSync(ADAPTERS_DIR)) {
    console.warn(`[gen-adapters] ${ADAPTERS_DIR} not found, skipping`);
    return;
  }
  const files = await walk(ADAPTERS_DIR);
  const adapters = [];

  for (const file of files) {
    const content = await readFile(file, 'utf8');
    let m;
    const localClassRe = new RegExp(CLASS_RE.source, CLASS_RE.flags);
    while ((m = localClassRe.exec(content))) {
      const clsName = m[1];
      const bases = m[2].split(',').map((s) => s.trim());
      const isAdapter = bases.some((b) => BASE_CLASSES.has(b));
      if (!isAdapter) continue;

      const body = classBody(content, m.index);
      const nameMatch = body.match(NAME_RE);
      if (!nameMatch) continue;

      const adapterName = nameMatch[1];
      const hooks = detectHooks(body);
      const relPath = relative(PROJECT_ROOT, file).replace(/\\/g, '/');
      const transport = transportFromPath(relPath);
      adapters.push({
        adapterName,
        className: clsName,
        baseClass: bases.find((b) => BASE_CLASSES.has(b)),
        transport,
        hooks,
        file: relPath,
      });
    }
  }

  adapters.sort((a, b) => a.adapterName.localeCompare(b.adapterName));

  const byTransport = new Map();
  for (const a of adapters) {
    if (!byTransport.has(a.transport)) byTransport.set(a.transport, 0);
    byTransport.set(a.transport, byTransport.get(a.transport) + 1);
  }

  const transportRows = [...byTransport.entries()]
    .map(([t, n]) => `| ${t} | ${n} |`)
    .join('\n');

  const tableRows = adapters
    .map(
      (a) =>
        `| \`${a.adapterName}\` | \`${a.className}\` | ${a.transport} | ${a.hooks.map((h) => `\`${h}\``).join(', ') || '—'} | <span style="font-size:0.75rem;color:var(--sl-color-gray-3)">${a.file}</span> |`,
    )
    .join('\n');

  const mermaidLines = ['flowchart LR', '  Orchestrator[Orchestrator dispatch]'];
  for (const a of adapters) {
    const node = a.className;
    mermaidLines.push(`  ${node}["${a.className}\\n${a.adapterName}"]`);
    mermaidLines.push(`  Orchestrator --> ${node}`);
  }

  const mdx = `---
title: Execution adapters
description: Auto-generated catalog of registered ExecutionAdapter implementations.
---

import { Aside, Card, CardGrid } from '@astrojs/starlight/components';

<CardGrid>
  <Card title="Adapters" icon="puzzle">
    ${adapters.length}
  </Card>
  <Card title="Transports" icon="random">
    ${byTransport.size}
  </Card>
</CardGrid>

## Dispatch overview

\`\`\`mermaid
${mermaidLines.join('\n')}
\`\`\`

## By transport

| Transport | Adapters |
| --- | ---: |
${transportRows || '| _none_ | 0 |'}

## All adapters

<div class="route-table">

| Adapter name | Class | Transport | Lifecycle hooks | Source |
| --- | --- | --- | --- | --- |
${tableRows || '| _no adapters detected_ | | | | |'}

</div>

<Aside type="tip" title="Source">
  Generated from <code>src/gracekelly/adapters/**/*.py</code> via regex on
  <code>class X(ExecutionAdapter)</code> or
  <code>class X(BaseApiAdapter)</code> declarations. Re-run
  <code>npm run dev</code> or <code>npm run build</code> to refresh.
</Aside>
`;

  await mkdir(dirname(OUT_FILE), { recursive: true });
  await writeFile(OUT_FILE, mdx, 'utf8');
  console.log(`[gen-adapters] wrote ${adapters.length} adapters across ${byTransport.size} transports`);
}

main().catch((err) => {
  console.error('[gen-adapters] failed:', err);
  process.exit(1);
});
