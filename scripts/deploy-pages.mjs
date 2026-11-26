import { copyFile, mkdir, mkdtemp, readFile, realpath, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { execFileSync, spawnSync } from 'node:child_process';
import { project, publicFiles } from './build-public.mjs';
import { verifyBuiltSecurity } from './web-security.mjs';

const repository = 'FURUYAN1234/clip-drop';
const origin = 'https://github.com/' + repository + '.git';
const git = (args, cwd = project) => execFileSync('git', args, { cwd, encoding: 'utf8', windowsHide: true }).trim();
if (git(['remote', 'get-url', 'origin']) !== origin) throw new Error('Publication origin does not match this application.');
const dist = path.join(project, 'dist');
verifyBuiltSecurity(await readFile(path.join(dist, 'index.html'), 'utf8'));
const work = await mkdtemp(path.join(tmpdir(), 'clip-drop-pages-'));
try {
  git(['init', '--initial-branch=gh-pages'], work);
  git(['config', 'user.name', git(['config', 'user.name'])], work);
  git(['config', 'user.email', git(['config', 'user.email'])], work);
  if (git(['ls-remote', origin, 'refs/heads/gh-pages'], work)) {
    git(['fetch', origin, 'refs/heads/gh-pages'], work);
    git(['update-ref', 'refs/heads/gh-pages', 'FETCH_HEAD'], work);
  }
  const directories = new Set(publicFiles.map(path.dirname));
  await Promise.all([...directories].map(directory => mkdir(path.join(work, directory), { recursive: true })));
  await Promise.all(['index.html', '.nojekyll', ...publicFiles].map(file =>
    copyFile(path.join(dist, file), path.join(work, file))));
  git(['add', '--all'], work);
  if (git(['status', '--porcelain'], work)) git(['commit', '-m', 'Publish verified CLIP Drop download guide'], work);
  git(['push', origin, 'HEAD:refs/heads/gh-pages'], work);
  const endpoint = 'repos/' + repository + '/pages';
  const settings = spawnSync('gh', ['api', endpoint], { encoding: 'utf8', windowsHide: true });
  const source = ['-f', 'source[branch]=gh-pages', '-f', 'source[path]=/'];
  if (settings.status !== 0) {
    if (!/HTTP 404/.test(settings.stderr || '')) throw new Error('The Pages settings could not be read.');
    execFileSync('gh', ['api', endpoint, '--method', 'POST', ...source, '-f', 'build_type=legacy'], { windowsHide: true });
  } else {
    const current = JSON.parse(settings.stdout);
    if (current.source?.branch !== 'gh-pages' || current.source?.path !== '/') {
      execFileSync('gh', ['api', endpoint, '--method', 'PUT', ...source], { windowsHide: true });
    }
  }
  console.log('CLIP_DROP_PAGES_PUBLISHED');
} finally {
  const actual = await realpath(work);
  const parent = await realpath(tmpdir());
  if (path.dirname(actual).toLowerCase() !== parent.toLowerCase() || !path.basename(actual).startsWith('clip-drop-pages-')) {
    throw new Error('Unexpected Pages staging directory.');
  }
  await rm(actual, { recursive: true, force: true });
}
