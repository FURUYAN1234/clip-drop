import { copyFile, mkdir, readFile, writeFile } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { secureHtml, verifyBuiltSecurity } from './web-security.mjs';

export const project = fileURLToPath(new URL('../', import.meta.url));
export const publicFiles = ['style.css', 'assets/app-screen.png', 'assets/comparison.png', 'docs/CLIP-Drop-manual.pdf'];

export async function buildPublic(output = join(project, 'dist')) {
  const { version } = JSON.parse(await readFile(join(project, 'package.json'), 'utf8'));
  if (!/^\d+\.\d+\.\d+$/.test(version)) throw new Error('Invalid public version');
  const source = await readFile(join(project, 'index.html'), 'utf8');
  const html = secureHtml(source.replaceAll('{{VERSION}}', version))
    .replace(/connect-src [^;]+/, "connect-src 'none'");
  verifyBuiltSecurity(html);
  await mkdir(output, { recursive: true });
  await Promise.all(publicFiles.map(async file => {
    const target = join(output, file);
    await mkdir(dirname(target), { recursive: true });
    await copyFile(join(project, file), target);
  }));
  await Promise.all([
    writeFile(join(output, 'index.html'), html),
    writeFile(join(output, '.nojekyll'), ''),
  ]);
  return html;
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) await buildPublic();
