// Copy markdown content from the project's docs/ tree (and a few root .md
// files) into Starlight's content collection at src/content/docs/guides/.
// Adds front-matter when missing so Starlight can index the page.

import { readdir, readFile, writeFile, mkdir, rm } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { dirname, extname, join, relative, basename } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = join(__dirname, '..', '..');
const SRC_DOCS = join(PROJECT_ROOT, 'docs');
const OUT_DIR = join(__dirname, '..', 'src', 'content', 'docs', 'guides');

const ROOT_FILES = [
  { src: 'README.md', dest: 'overview.md', title: 'Project overview' },
  { src: 'AGENTS.md', dest: 'agents.md', title: 'Agents protocol' },
  { src: 'CLAUDE.md', dest: 'claude.md', title: 'Claude protocol' },
  { src: 'audit_codex_2026-04-26.md', dest: 'audits/audit-codex-2026-04-26.md', title: 'Codex audit (2026-04-26)' },
  { src: 'audit_opus_2026-04-26.md', dest: 'audits/audit-opus-2026-04-26.md', title: 'Opus audit (2026-04-26)' },
  { src: 'audit_opus_27_04_delta.md', dest: 'audits/audit-opus-2026-04-27-delta.md', title: 'Opus audit delta (2026-04-27)' },
  { src: 'codex_review_2026-04-27.md', dest: 'audits/codex-review-2026-04-27.md', title: 'Codex review (2026-04-27)' },
  { src: 'opt.md', dest: 'optimization-notes.md', title: 'Optimization notes' },
];

async function walkMarkdown(dir, prefix = '') {
  const entries = await readdir(dir, { withFileTypes: true });
  const out = [];
  for (const entry of entries) {
    const full = join(dir, entry.name);
    const rel = prefix ? join(prefix, entry.name) : entry.name;
    if (entry.isDirectory()) {
      out.push(...(await walkMarkdown(full, rel)));
    } else if (extname(entry.name) === '.md') {
      out.push({ full, rel });
    }
  }
  return out;
}

function deriveTitle(content, fallbackName) {
  const h1 = content.match(/^#\s+(.+)$/m);
  if (h1) return h1[1].trim();
  return fallbackName.replace(/[-_]/g, ' ').replace(/\.md$/, '');
}

function ensureFrontMatter(content, title, sourcePath) {
  const trimmed = content.replace(/^﻿/, '');
  if (trimmed.startsWith('---')) {
    const fm = trimmed.match(/^---\n([\s\S]*?)\n---/);
    if (fm && !/^title:/m.test(fm[1])) {
      return `---\n${fm[1]}\ntitle: ${JSON.stringify(title)}\n---${trimmed.slice(fm[0].length)}`;
    }
    return trimmed;
  }
  const safeTitle = title.replace(/"/g, '\\"');
  const editUrl = `https://github.com/brownjuly2003-code/GraceKelly/blob/main/${sourcePath.replace(/\\/g, '/')}`;
  return `---\ntitle: "${safeTitle}"\neditUrl: ${editUrl}\n---\n\n${trimmed}`;
}

function slugifyPath(rel) {
  return rel
    .split(/[\\/]/)
    .map((p) => p.toLowerCase().replace(/\s+/g, '-'))
    .join('/');
}

const SITE_BASE = '/GraceKelly';

// Relative `docs/foo/bar.md` links are valid on GitHub but 404 on the
// published site — rewrite them to the Starlight guide slug. http(s) links
// and non-docs relative links are left untouched.
function rewriteLinks(content) {
  return content.replace(
    /\]\((?:\.\/)?docs\/([^)\s#]+?)\.md(#[^)\s]*)?\)/gi,
    (_m, path, anchor) => {
      const slug = path
        .split('/')
        .map((s) => s.toLowerCase().replace(/\s+/g, '-'))
        .join('/');
      return `](${SITE_BASE}/guides/${slug}/${anchor || ''})`;
    },
  );
}

async function copyOne(srcAbs, destAbs, title, sourcePath) {
  const raw = await readFile(srcAbs, 'utf8');
  const patched = rewriteLinks(ensureFrontMatter(raw, title, sourcePath));
  await mkdir(dirname(destAbs), { recursive: true });
  await writeFile(destAbs, patched, 'utf8');
}

async function main() {
  if (existsSync(OUT_DIR)) {
    await rm(OUT_DIR, { recursive: true, force: true });
  }
  await mkdir(OUT_DIR, { recursive: true });

  let count = 0;

  if (existsSync(SRC_DOCS)) {
    const all = await walkMarkdown(SRC_DOCS);
    for (const { full, rel } of all) {
      const raw = await readFile(full, 'utf8');
      const title = deriveTitle(raw, basename(rel));
      const destRel = slugifyPath(rel);
      const destAbs = join(OUT_DIR, destRel);
      const sourcePath = `docs/${rel.replace(/\\/g, '/')}`;
      await copyOne(full, destAbs, title, sourcePath);
      count++;
    }
  }

  for (const file of ROOT_FILES) {
    const srcAbs = join(PROJECT_ROOT, file.src);
    if (!existsSync(srcAbs)) continue;
    const destAbs = join(OUT_DIR, file.dest);
    await copyOne(srcAbs, destAbs, file.title, file.src);
    count++;
  }

  console.log(`[sync-docs] copied ${count} markdown files into ${relative(PROJECT_ROOT, OUT_DIR)}`);
}

main().catch((err) => {
  console.error('[sync-docs] failed:', err);
  process.exit(1);
});
