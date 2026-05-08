// Read src/gracekelly/config.py — extract the Settings dataclass field
// list and the env-var bindings inside Settings.from_env(). Render a
// configuration matrix as MDX. Regex-based, no Python runtime.

import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = join(__dirname, '..', '..');
const CONFIG_FILE = join(PROJECT_ROOT, 'src', 'gracekelly', 'config.py');
const OUT_FILE = join(__dirname, '..', 'src', 'content', 'docs', 'architecture', 'config.mdx');

function extractSettingsFields(src) {
  const dataclassMatch = src.match(/@dataclass[^\n]*\nclass Settings:\s*\n([\s\S]*?)(?=\n    def\s+validate)/);
  if (!dataclassMatch) return [];
  const block = dataclassMatch[1];
  const fields = [];
  const fieldRe = /^\s{4}(\w+)\s*:\s*([^=\n]+?)\s*=\s*([^\n]+)$/gm;
  let m;
  while ((m = fieldRe.exec(block))) {
    const name = m[1];
    if (name === 'name') continue;
    fields.push({
      name,
      type: m[2].trim(),
      defaultRaw: m[3].trim(),
    });
  }
  return fields;
}

function extractEnvBindings(src) {
  const fromEnvMatch = src.match(/def from_env\(cls\)[\s\S]*?return cls\(([\s\S]*?)\n\s{8}\)\s*\n/);
  if (!fromEnvMatch) return new Map();
  const block = fromEnvMatch[1];
  const map = new Map();
  const envRe = /(\w+)\s*=\s*[^\n]*?["'](GRACEKELLY_[A-Z0-9_]+)["']/g;
  let m;
  while ((m = envRe.exec(block))) {
    if (!map.has(m[1])) map.set(m[1], m[2]);
  }
  return map;
}

function categorize(name) {
  if (name.startsWith('browser_') || name.startsWith('max_browser')) return 'Browser execution';
  if (name.startsWith('postgres_') || name === 'storage_backend') return 'Storage';
  if (name.startsWith('mistral_') || name.startsWith('openai_') || name.startsWith('anthropic_')) return 'API providers';
  if (name.startsWith('rate_limit') || name === 'redis_url') return 'Rate limiting';
  if (name.startsWith('sentry_') || name.startsWith('otel_') || name.startsWith('usage_telemetry') || name === 'health_expose_details') return 'Observability';
  if (name === 'api_key' || name === 'host' || name === 'port' || name === 'env' || name === 'log_level') return 'Service';
  if (name.startsWith('orchestrate_') || name === 'execution_profile' || name === 'enable_model_fallback' || name.startsWith('context_') || name.startsWith('max_context')) return 'Orchestration';
  return 'Other';
}

const CATEGORY_ORDER = [
  'Service',
  'Orchestration',
  'API providers',
  'Browser execution',
  'Storage',
  'Rate limiting',
  'Observability',
  'Other',
];

async function main() {
  if (!existsSync(CONFIG_FILE)) {
    console.warn(`[gen-config] ${CONFIG_FILE} not found, skipping`);
    return;
  }
  const src = await readFile(CONFIG_FILE, 'utf8');
  const fields = extractSettingsFields(src);
  const envBindings = extractEnvBindings(src);

  const grouped = new Map();
  for (const cat of CATEGORY_ORDER) grouped.set(cat, []);
  for (const f of fields) {
    const cat = categorize(f.name);
    grouped.get(cat).push({ ...f, env: envBindings.get(f.name) || null });
  }

  const sections = [];
  for (const cat of CATEGORY_ORDER) {
    const items = grouped.get(cat);
    if (!items.length) continue;
    const rows = items
      .map(
        (i) =>
          `| ${i.env ? `\`${i.env}\`` : '—'} | \`${i.name}\` | \`${i.type}\` | <code>${i.defaultRaw.replace(/</g, '&lt;').replace(/>/g, '&gt;')}</code> |`,
      )
      .join('\n');
    sections.push(`### ${cat}\n\n| Env var | Settings field | Type | Default |\n| --- | --- | --- | --- |\n${rows}\n`);
  }

  const mdx = `---
title: Configuration matrix
description: Auto-generated environment variable and Settings dataclass matrix from src/gracekelly/config.py.
---

import { Aside, Card, CardGrid } from '@astrojs/starlight/components';

<CardGrid>
  <Card title="Settings fields" icon="setting">
    ${fields.length}
  </Card>
  <Card title="Env-var bindings" icon="rocket">
    ${envBindings.size}
  </Card>
  <Card title="Categories" icon="random">
    ${sections.length}
  </Card>
</CardGrid>

GraceKelly reads its configuration from environment variables (with
\`.env\` autoloaded outside pytest). Every \`GRACEKELLY_*\` variable maps
to a frozen \`Settings\` dataclass field. Validation runs in
\`Settings.validate()\` at startup; invalid combinations raise
\`ValueError\` before the app accepts traffic.

${sections.join('\n')}

<Aside type="tip" title="Source">
  Generated from <code>src/gracekelly/config.py</code>. Re-run
  <code>npm run dev</code> or <code>npm run build</code> to refresh.
</Aside>
`;

  await mkdir(dirname(OUT_FILE), { recursive: true });
  await writeFile(OUT_FILE, mdx, 'utf8');
  console.log(`[gen-config] wrote ${fields.length} settings fields, ${envBindings.size} env bindings`);
}

main().catch((err) => {
  console.error('[gen-config] failed:', err);
  process.exit(1);
});
