"""Read ordinary CLIP strokes using the documented clipfile-rs layouts."""
from contextlib import closing
from dataclasses import dataclass
from math import isfinite
from pathlib import Path
from struct import unpack, unpack_from
from tempfile import TemporaryDirectory
import sqlite3
import xml.etree.ElementTree as ET


class ClipFormatError(ValueError):
    pass


@dataclass
class VectorData:
    layer_types: dict
    strokes: dict
    warnings: list


def read_vectors(source):
    with source.open('rb') as stream:
        header = stream.read(24)
        size = source.stat().st_size
        if len(header) != 24 or unpack('>8sQQ', header) != (b'CSFCHUNK', size, 24):
            raise ClipFormatError('CLIP STUDIO PAINT のファイルとして読み込めません。')
        objects = {}
        database = None
        offset = 24
        while offset < size:
            stream.seek(offset)
            chunk = stream.read(16)
            if len(chunk) != 16:
                raise ClipFormatError('CLIP のチャンクが途中で切れています。')
            kind, length = unpack('>8sQ', chunk)
            end = offset + 16 + length
            if end > size:
                raise ClipFormatError('CLIP のチャンク長が不正です。')
            if kind == b'CHNKSQLi':
                if database is not None or length > 128 * 1024**2:
                    raise ClipFormatError('CLIP のレイヤー情報を読み込めません。')
                database = stream.read(length)
            elif kind == b'CHNKExta' and length >= 16:
                name_size, = unpack('>Q', stream.read(8))
                if 0 < name_size <= 256 and 16 + name_size <= length:
                    name = stream.read(name_size)
                    data_size, = unpack('>Q', stream.read(8))
                    if stream.tell() + data_size <= end:
                        objects[name] = (stream.tell(), data_size)
            offset = end
        if not database or not database.startswith(b'SQLite format 3\0'):
            raise ClipFormatError('CLIP にレイヤー情報がありません。')

        with TemporaryDirectory(prefix='clip-drop-') as temp:
            index = Path(temp) / 'layers.sqlite'
            index.write_bytes(database)
            with closing(sqlite3.connect(index.as_uri() + '?mode=ro', uri=True)) as conn:
                conn.execute('PRAGMA trusted_schema=OFF')
                columns = {row[1] for row in conn.execute('PRAGMA table_info(Layer)')}
                select = ['MainId', 'LayerType']
                select.append('VectorNormalStrokeIndex' if 'VectorNormalStrokeIndex' in columns else 'NULL')
                layers = {mid: (kind, bool(stroke)) for mid, kind, stroke in conn.execute(
                    'SELECT ' + ', '.join(select) + ' FROM Layer'
                )}
                vector_cols = {row[1] for row in conn.execute('PRAGMA table_info(VectorObjectList)')}
                rows = (conn.execute('SELECT LayerId, VectorData FROM VectorObjectList ORDER BY MainId').fetchall()
                        if {'MainId', 'LayerId', 'VectorData'} <= vector_cols else [])

        strokes, warnings = {}, []
        for layer_id, name in rows:
            if not name:
                continue
            if isinstance(name, str):
                name = name.encode('ascii')
            block = objects.get(name)
            if not block or block[1] > 64 * 1024**2:
                warnings.append(f'レイヤー {layer_id} のストロークデータを読み込めません。')
                continue
            start, length = block
            stream.seek(start)
            paths, issues = read_strokes(stream.read(length))
            strokes.setdefault(layer_id, []).extend(paths)
            warnings.extend(f'レイヤー {layer_id}：{issue}' for issue in issues)
        return VectorData(layers, strokes, warnings)


def fmt(value):
    return f'{value:.5f}'.rstrip('0').rstrip('.') if value else '0'


def pair(point):
    return f'{fmt(point[0])} {fmt(point[1])}'


def smooth_controls(a, b, c, d):
    first = tuple(b[i] + (c[i] - a[i]) / 6 for i in range(2))
    second = tuple(c[i] - (d[i] - b[i]) / 6 for i in range(2))
    return first, second


def read_strokes(raw):
    paths, issues = [], set()
    cursor = point_total = 0
    while cursor < len(raw):
        if len(raw) - cursor < 24:
            raise ClipFormatError('ストロークのヘッダーが途中で切れています。')
        header, section, record, default, count, flags = unpack_from('>6I', raw, cursor)
        end = cursor + header + record * count
        point_total += count
        if header < 24 or record == 0 or end > len(raw) or point_total > 500_000:
            raise ClipFormatError('ストロークの境界または点数が不正です。')
        start, cursor = cursor, end
        kind, curve = flags & 0xD, flags & 0xF0
        if kind != 1 or (header, section) not in {(88, 72), (92, 76)} or default != 88:
            issues.add('未対応のストローク形式があります。')
            continue
        if record != {0x10: 88, 0x20: 104, 0x40: 120, 0x80: 88}.get(curve):
            issues.add('未対応の曲線形式があります。')
            continue
        if not count:
            continue

        rgb = ''.join(f'{raw[start + 40 + i * 4]:02x}' for i in range(3))
        opacity, = unpack_from('>d', raw, start + 64)
        radius, = unpack_from('>d', raw, start + header - 12)
        positions, factors, controls, corners = [], [], [], []
        for i in range(count):
            point = start + header + i * record
            positions.append(unpack_from('>dd', raw, point))
            corners.append(bool(unpack_from('>I', raw, point + 32)[0] & 1))
            factors.append(unpack_from('>ff', raw, point + 56))
            controls.append([unpack_from('>dd', raw, point + j) for j in range(88, record, 16)])
        geometry = [v for pts in (positions, factors, *(controls)) for xy in pts for v in xy]
        if not all(isfinite(x) and abs(x) <= 1e7 for x in [radius, opacity, *geometry]):
            raise ClipFormatError('ストロークの数値が不正です。')
        widths, alphas = zip(*factors)
        if not 0 <= radius <= 100_000 or not 0 <= opacity <= 1 or min(widths) < 0 or min(alphas) < 0 or max(alphas) > 1:
            raise ClipFormatError('ストロークの太さまたは不透明度が不正です。')
        width = 2 * radius * sum(widths) / count
        alpha = opacity * sum(alphas) / count
        if max(widths) - min(widths) > 0.0001 or max(alphas) - min(alphas) > 0.0001:
            issues.add('ストローク内の線幅・濃淡の変化は平均値に近似しました。')
        if width <= 0 or alpha <= 0:
            continue
        color = '#' + rgb
        if count == 1:
            x, y = positions[0]
            paths.append(ET.Element('circle', {
                'cx': fmt(x), 'cy': fmt(y), 'r': fmt(width / 2),
                'fill': color, 'opacity': fmt(alpha),
            }))
            continue

        closed = bool(flags & 0x100)
        pieces = ['M ' + pair(positions[0])]
        for i in range(count if closed else count - 1):
            j = (i + 1) % count
            b, c = positions[i], positions[j]
            if curve == 0x10:
                pieces.append('L ' + pair(c))
            elif curve in (0x20, 0x40):
                command = 'Q' if curve == 0x20 else 'C'
                pieces.append(command + ' ' + ' '.join(map(pair, [*controls[i], c])))
            else:
                a = positions[(i - 1) % count] if closed or i > 0 else b
                d = positions[(j + 1) % count] if closed or j + 1 < count else c
                u, v = smooth_controls(a, b, c, d)
                pieces.append('C ' + ' '.join(map(pair, [b if corners[i] else u, c if corners[j] else v, c])))
                issues.add('クリスタのスプラインを SVG のベジェ曲線に近似しました。')
        if closed:
            pieces.append('Z')
        paths.append(ET.Element('path', {
            'd': ' '.join(pieces), 'fill': 'none', 'stroke': color,
            'stroke-width': fmt(width), 'stroke-linecap': 'round',
            'stroke-linejoin': 'round', 'opacity': fmt(alpha),
        }))
    return paths, sorted(issues)
