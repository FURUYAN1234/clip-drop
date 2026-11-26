"""Create and check a Windows distribution ZIP from a PyInstaller onedir build."""
from argparse import ArgumentParser
from hashlib import sha256
from importlib.metadata import distribution
from pathlib import Path, PurePosixPath
from sys import base_prefix
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

MANUAL_NAME = 'CLIP-Drop-manual.pdf'
SAMPLE_NAMES = ('vector.clip', 'raster.clip', 'mixed.clip')


def digest(content):
    return sha256(content).hexdigest()


def runtime_licenses():
    libs = ('clipparse', 'psdparse', 'resvg-py', 'tkinterdnd2', 'vtracer', 'Pillow', 'PyInstaller')
    for library in libs:
        package = distribution(library)
        matches = [
            f for f in package.files
            if '.dist-info' in f.as_posix().lower()
            and f.name.upper().startswith(('LICENSE', 'COPYING', 'NOTICE'))
        ]
        if not matches:
            raise ValueError(f'Missing license for {library}')
        for file in matches:
            yield f'licenses/{library}/{file.name}', file.locate().read_bytes()

    runtime = Path(base_prefix)
    yield 'licenses/Python/LICENSE.txt', (runtime / 'LICENSE.txt').read_bytes()
    terms = sorted((runtime / 'tcl').glob('*/license.terms'))
    for file in terms:
        yield f'licenses/{file.parent.name}/license.terms', file.read_bytes()


def build_zip(app, archive, readme):
    entries = {
        path.relative_to(app).as_posix(): path.read_bytes()
        for path in app.rglob('*') if path.is_file()
    }
    if 'CLIP Drop.exe' not in entries:
        raise ValueError('A PyInstaller CLIP Drop onedir output is required')
    entries.update(runtime_licenses())
    entries['README.md'] = readme.read_bytes()
    entries[MANUAL_NAME] = (readme.parent / 'docs' / MANUAL_NAME).read_bytes()
    for sample in SAMPLE_NAMES:
        entries[f'samples/{sample}'] = (readme.parent / 'samples' / sample).read_bytes()
    entries['SHA256SUMS.txt'] = ''.join(
        f'{digest(content)}  {name}\n' for name, content in sorted(entries.items())
    ).encode('utf-8')
    with ZipFile(archive, 'w') as output:
        for name, content in sorted(entries.items()):
            member = ZipInfo(f'CLIP Drop/{name}', date_time=(1980, 1, 1, 0, 0, 0))
            output.writestr(member, content, compress_type=ZIP_DEFLATED, compresslevel=6)


def verify_zip(archive):
    with ZipFile(archive) as package:
        prefix = 'CLIP Drop/'
        listed = package.namelist()
        if package.testzip() or len(set(listed)) != len(listed):
            raise ValueError('ZIP integrity error')
        for name in listed:
            path = PurePosixPath(name)
            if not name.startswith(prefix) or '..' in path.parts or '\\' in name or ':' in name:
                raise ValueError(f'Malformed ZIP entry {name}')
        manifest = prefix + 'SHA256SUMS.txt'
        sums = dict(
            line.split('  ', 1)[::-1]
            for line in package.read(manifest).decode('utf-8').splitlines()
        )
        if {prefix + item for item in sums} | {manifest} != set(listed):
            raise ValueError('Manifest file set differs from ZIP')
        required = {'CLIP Drop.exe', 'README.md', MANUAL_NAME, *(f'samples/{name}' for name in SAMPLE_NAMES)}
        if not required.issubset(sums):
            raise ValueError('Expected application files are missing')
        manual = package.read(prefix + MANUAL_NAME)
        if not manual.startswith(b'%PDF-') or b'%%EOF' not in manual[-1024:]:
            raise ValueError('Invalid manual PDF')
        for name, expected in sums.items():
            if digest(package.read(prefix + name)) != expected:
                raise ValueError(f'SHA256 mismatch for {name}')
    print(f'{len(listed)} files verified, SHA256 {digest(archive.read_bytes())}')


if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('archive', type=Path)
    parser.add_argument('--app', type=Path)
    parser.add_argument('--readme', type=Path)
    args = parser.parse_args()
    if args.app or args.readme:
        if not (args.app and args.readme):
            parser.error('--app and --readme are both required to build')
        build_zip(args.app, args.archive, args.readme)
    verify_zip(args.archive)
