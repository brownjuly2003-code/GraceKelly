// Guard against a stale committed openapi.json. The docs CI is Node-only and
// cannot regenerate the spec (that needs Python), so this fails the build when
// the route set parsed from source no longer matches openapi.json — i.e. a
// route was added, removed or renamed without running scripts/dump_openapi.py.

import { readFile, readdir } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { dirname, join, extname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = join(__dirname, '..', '..');
const ROUTES_DIR = join(PROJECT_ROOT, 'src', 'gracekelly', 'api', 'routes');
const APP_FILE = join(PROJECT_ROOT, 'src', 'gracekelly', 'main.py');
const SPEC_FILE = join(__dirname, '..', 'openapi.json');

const METHOD_RE = /@(?:app|router)\.(get|post|put|patch|delete|head|options)\(\s*["']([^"']+)["']/gi;
const PREFIX_RE = /APIRouter\([^)]*prefix\s*=\s*["']([^"']+)["']/i;
const HTTP_METHODS = new Set(['get', 'post', 'put', 'patch', 'delete']);

const norm = (method, path) => `${method.toUpperCase()} ${path.replace(/\/+$/, '') || '/'}`;

async function parseFile(file) {
  const content = await readFile(file, 'utf8');
  const prefixMatch = content.match(PREFIX_RE);
  const prefix = prefixMatch ? prefixMatch[1] : '';
  const out = [];
  let m;
  while ((m = METHOD_RE.exec(content))) {
    if (!HTTP_METHODS.has(m[1].toLowerCase())) continue;
    out.push(norm(m[1], prefix + m[2]));
  }
  return out;
}

async function main() {
  if (!existsSync(SPEC_FILE)) {
    console.error('[check-openapi-fresh] openapi.json missing — run: python scripts/dump_openapi.py');
    process.exit(1);
  }

  const routes = new Set();
  if (existsSync(APP_FILE)) (await parseFile(APP_FILE)).forEach((r) => routes.add(r));
  if (existsSync(ROUTES_DIR)) {
    for (const e of await readdir(ROUTES_DIR, { withFileTypes: true })) {
      if (e.isFile() && extname(e.name) === '.py' && !e.name.startsWith('_')) {
        (await parseFile(join(ROUTES_DIR, e.name))).forEach((r) => routes.add(r));
      }
    }
  }

  const spec = JSON.parse(await readFile(SPEC_FILE, 'utf8'));
  const fromSpec = new Set();
  for (const [path, item] of Object.entries(spec.paths || {})) {
    for (const method of Object.keys(item)) {
      if (HTTP_METHODS.has(method)) fromSpec.add(norm(method, path));
    }
  }

  const missingFromSpec = [...routes].filter((r) => !fromSpec.has(r)).sort();
  const staleInSpec = [...fromSpec].filter((r) => !routes.has(r)).sort();

  if (missingFromSpec.length || staleInSpec.length) {
    console.error('[check-openapi-fresh] openapi.json is out of date with the source routes.');
    if (missingFromSpec.length) {
      console.error('  Routes in source but not in openapi.json:\n    ' + missingFromSpec.join('\n    '));
    }
    if (staleInSpec.length) {
      console.error('  Paths in openapi.json but no longer in source:\n    ' + staleInSpec.join('\n    '));
    }
    console.error('  Fix: run `python scripts/dump_openapi.py` and commit docs-site/openapi.json.');
    process.exit(1);
  }

  console.log(`[check-openapi-fresh] OK — ${routes.size} routes match openapi.json`);
}

main().catch((err) => {
  console.error('[check-openapi-fresh] failed:', err);
  process.exit(1);
});
