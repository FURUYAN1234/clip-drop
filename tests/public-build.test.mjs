import assert from 'node:assert/strict';
import { mkdtemp, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { test } from 'node:test';
import { buildPublic, publicFiles } from '../scripts/build-public.mjs';
import { verifyBuiltSecurity } from '../scripts/web-security.mjs';

test('the static guide points to the matching release and serves its manual and screenshots', async () => {
  const output = await mkdtemp(join(tmpdir(), 'clip-drop-public-'));
  try {
    const html = await buildPublic(output);
    verifyBuiltSecurity(html);
    assert.match(html, /connect-src 'none'/);
    const pkg = JSON.parse(await readFile(new URL('../package.json', import.meta.url), 'utf8'));
    assert.ok(html.includes('/releases/download/v' + pkg.version + '/CLIP-Drop-v' + pkg.version + '-win-x64.zip'));
    const manual = await readFile(join(output, 'docs', 'CLIP-Drop-manual.pdf'));
    assert.ok(manual.subarray(0, 5).equals(Buffer.from('%PDF-')));
    assert.doesNotMatch(html, /\{\{VERSION\}\}/);
    for (const file of publicFiles) {
      assert.ok((await readFile(join(output, file))).length > 0);
      assert.ok(html.includes(file));
    }
  } finally {
    await rm(output, { recursive: true, force: true });
  }
});
