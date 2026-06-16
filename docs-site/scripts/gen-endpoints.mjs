// Render a full API reference page from docs-site/openapi.json — per endpoint:
// method/path, summary, description, request-body field table + JSON example,
// and response status codes with the success-schema shape.
//
// openapi.json is committed (regenerated locally via scripts/dump_openapi.py)
// so this step needs no Python on the Node-only docs CI runner.

import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const SPEC_FILE = join(__dirname, '..', 'openapi.json');
const OUT_FILE = join(__dirname, '..', 'src', 'content', 'docs', 'architecture', 'api.mdx');

const METHOD_ORDER = ['get', 'post', 'put', 'patch', 'delete'];

function resolveRef(spec, node) {
  let cur = node;
  let guard = 0;
  while (cur && cur.$ref && guard++ < 20) {
    const name = cur.$ref.split('/').pop();
    cur = spec.components?.schemas?.[name];
  }
  return cur || {};
}

// Human-readable type label, unwrapping Optional (anyOf [...null]) and arrays.
function typeLabel(spec, schema) {
  if (!schema) return 'any';
  if (schema.$ref) return schema.$ref.split('/').pop();
  if (schema.anyOf || schema.oneOf) {
    const branches = (schema.anyOf || schema.oneOf)
      .filter((b) => !(b.type === 'null'))
      .map((b) => typeLabel(spec, b));
    const nullable = (schema.anyOf || schema.oneOf).some((b) => b.type === 'null');
    const label = [...new Set(branches)].join(' | ') || 'any';
    return nullable ? `${label} | null` : label;
  }
  if (schema.enum) return schema.enum.map((v) => JSON.stringify(v)).join(' | ');
  if (schema.type === 'array') return `${typeLabel(spec, schema.items || {})}[]`;
  if (schema.type === 'object' && schema.additionalProperties) {
    return `{ [key]: ${typeLabel(spec, schema.additionalProperties)} }`;
  }
  if (schema.format) return `${schema.type} <${schema.format}>`;
  return schema.type || 'object';
}

// Pick the non-null branch of an Optional/union schema.
function effectiveSchema(spec, schema) {
  const s = resolveRef(spec, schema);
  if (s.anyOf || s.oneOf) {
    const branch = (s.anyOf || s.oneOf).find((b) => b.type !== 'null') || {};
    return resolveRef(spec, branch);
  }
  return s;
}

// Synthesize an illustrative JSON value for a schema.
function exampleValue(spec, schema, name, depth, seen) {
  if (depth > 4) return null;
  const direct = schema?.example ?? schema?.default;
  if (direct !== undefined && direct !== null) return direct;

  const s = effectiveSchema(spec, schema);
  if (s.example !== undefined) return s.example;
  if (s.default !== undefined && s.default !== null) return s.default;
  if (s.enum && s.enum.length) return s.enum[0];

  // friendly values for common field names so the flagship examples read real
  const n = (name || '').toLowerCase();
  if (s.type === 'string' || (!s.type && !s.properties)) {
    if (n.includes('prompt')) return 'Summarize the latest incident report.';
    if (n === 'model') return 'gpt-5.4';
    if (n.includes('session')) return 'sess-3f9c';
    if (n.includes('id')) return 'abc123';
    if (s.format === 'date-time') return '2026-01-01T00:00:00Z';
    return 'string';
  }
  if (s.type === 'integer' || s.type === 'number') {
    if (s.minimum !== undefined) return s.minimum;
    return n.includes('quorum') ? 2 : 0;
  }
  if (s.type === 'boolean') return false;
  if (s.type === 'array') {
    if (n === 'models') return ['gpt-5.4', 'claude'];
    return [exampleValue(spec, s.items || {}, name, depth + 1, seen)];
  }
  if (s.type === 'object' || s.properties) {
    if (s.additionalProperties) return {};
    return exampleObject(spec, s, depth + 1, seen);
  }
  return null;
}

// Build an example object: required fields + fields with a meaningful default.
function exampleObject(spec, schema, depth, seen) {
  const s = resolveRef(spec, schema);
  const props = s.properties || {};
  const required = new Set(s.required || []);
  const ref = s.title || JSON.stringify(Object.keys(props));
  if (seen.has(ref)) return {};
  seen = new Set(seen);
  seen.add(ref);

  const out = {};
  for (const [name, propSchema] of Object.entries(props)) {
    const hasDefault = propSchema.default !== undefined && propSchema.default !== null;
    if (required.has(name) || hasDefault) {
      out[name] = exampleValue(spec, propSchema, name, depth, seen);
    }
  }
  // ensure at least the first property shows up
  if (!Object.keys(out).length && Object.keys(props).length) {
    const [name, propSchema] = Object.entries(props)[0];
    out[name] = exampleValue(spec, propSchema, name, depth, seen);
  }
  return out;
}

// Pipes break Markdown table cells (even inside code spans) — escape them.
function escCell(s) {
  return String(s).replace(/\|/g, '\\|');
}

function fieldTable(spec, schema) {
  const s = resolveRef(spec, schema);
  const props = s.properties || {};
  if (!Object.keys(props).length) return '';
  const required = new Set(s.required || []);
  const rows = ['| Field | Type | Required | Description |', '| --- | --- | :---: | --- |'];
  for (const [name, propSchema] of Object.entries(props)) {
    const type = typeLabel(spec, propSchema);
    const req = required.has(name) ? '✓' : '';
    let desc = escCell((propSchema.description || '').replace(/\s*\n\s*/g, ' ').trim());
    const def = propSchema.default;
    if (def !== undefined && def !== null && def !== '') {
      desc += `${desc ? ' ' : ''}_(default: \`${escCell(JSON.stringify(def))}\`)_`;
    }
    rows.push(`| \`${name}\` | \`${escCell(type)}\` | ${req} | ${desc || '—'} |`);
  }
  return rows.join('\n');
}

function methodBadge(method) {
  const m = method.toUpperCase();
  return `<span class="route-method route-method-${method.toLowerCase()}">${m}</span>`;
}

function jsonBlock(value) {
  return '```json\n' + JSON.stringify(value, null, 2) + '\n```';
}

function renderEndpoint(spec, method, path, op) {
  const lines = [];
  lines.push(`### ${methodBadge(method)} \`${path}\``);
  lines.push('');
  if (op.summary) lines.push(`**${op.summary}**`);
  if (op.description) {
    lines.push('');
    lines.push(op.description.trim());
  }
  lines.push('');

  const reqSchema = op.requestBody?.content?.['application/json']?.schema;
  if (reqSchema) {
    lines.push('**Request body**');
    lines.push('');
    const table = fieldTable(spec, reqSchema);
    if (table) {
      lines.push(table);
      lines.push('');
    }
    const example = exampleValue(spec, reqSchema, '', 0, new Set());
    if (example && Object.keys(example).length) {
      lines.push(jsonBlock(example));
      lines.push('');
    }
  }

  const responses = op.responses || {};
  const rows = ['| Status | Meaning |', '| --- | --- |'];
  for (const [code, resp] of Object.entries(responses)) {
    rows.push(`| \`${code}\` | ${escCell((resp.description || '').replace(/\s*\n\s*/g, ' ').trim()) || '—'} |`);
  }
  lines.push('**Responses**');
  lines.push('');
  lines.push(rows.join('\n'));
  lines.push('');

  const okCode = Object.keys(responses).find((c) => c.startsWith('2'));
  const okSchema = responses[okCode]?.content?.['application/json']?.schema;
  if (okSchema) {
    const eff = effectiveSchema(spec, okSchema);
    const name = okSchema.$ref ? okSchema.$ref.split('/').pop() : typeLabel(spec, okSchema);
    if (eff.properties) {
      lines.push(`<details>\n<summary>${okCode} response shape — ${name}</summary>`);
      lines.push('');
      const table = fieldTable(spec, eff);
      if (table) lines.push(table);
      lines.push('');
      const example = exampleValue(spec, okSchema, '', 0, new Set());
      if (example && typeof example === 'object' && Object.keys(example).length) {
        lines.push('Example response:');
        lines.push('');
        lines.push(jsonBlock(example));
        lines.push('');
      }
      lines.push('</details>');
      lines.push('');
    }
  }
  return lines.join('\n');
}

async function main() {
  if (!existsSync(SPEC_FILE)) {
    throw new Error(`openapi.json not found at ${SPEC_FILE}. Run: python scripts/dump_openapi.py`);
  }
  const spec = JSON.parse(await readFile(SPEC_FILE, 'utf8'));
  const paths = spec.paths || {};

  // group endpoints by their first tag
  const groups = new Map();
  for (const [path, item] of Object.entries(paths)) {
    for (const method of METHOD_ORDER) {
      const op = item[method];
      if (!op) continue;
      const tag = (op.tags && op.tags[0]) || 'other';
      if (!groups.has(tag)) groups.set(tag, []);
      groups.get(tag).push({ method, path, op });
    }
  }

  const total = [...groups.values()].reduce((n, g) => n + g.length, 0);
  const sortedTags = [...groups.keys()].sort();

  const out = [];
  out.push('---');
  out.push('title: API reference');
  out.push('description: Every HTTP endpoint with request and response schemas, generated from the live FastAPI OpenAPI spec.');
  out.push('---');
  out.push('');
  out.push("import { Aside } from '@astrojs/starlight/components';");
  out.push('');
  out.push('<Aside type="note">');
  out.push(`  Generated from the application's OpenAPI 3.1 schema (\`openapi.json\`),`);
  out.push('  regenerated with `python scripts/dump_openapi.py`. The running app also');
  out.push('  serves interactive docs at `/docs` and the raw schema at `/openapi.json`.');
  out.push('</Aside>');
  out.push('');
  out.push(`This catalog documents **${total} endpoints** across **${sortedTags.length} groups**.`);
  out.push(`All request and response bodies are \`application/json\` unless noted.`);
  out.push('');

  for (const tag of sortedTags) {
    const eps = groups.get(tag).sort(
      (a, b) => a.path.localeCompare(b.path) ||
        METHOD_ORDER.indexOf(a.method) - METHOD_ORDER.indexOf(b.method),
    );
    out.push(`## ${tag[0].toUpperCase()}${tag.slice(1)}`);
    out.push('');
    for (const { method, path, op } of eps) {
      out.push(renderEndpoint(spec, method, path, op));
    }
  }

  await mkdir(dirname(OUT_FILE), { recursive: true });
  await writeFile(OUT_FILE, out.join('\n').replace(/\n{3,}/g, '\n\n') + '\n', 'utf8');
  console.log(`gen-endpoints: wrote ${total} endpoints in ${sortedTags.length} groups -> ${OUT_FILE}`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
