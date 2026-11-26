"""Turn CLIP artwork into an editable SVG and raster deliverables."""
from copy import deepcopy
from dataclasses import dataclass
from io import BytesIO
from itertools import count
from pathlib import Path
from tempfile import TemporaryDirectory
import sqlite3
import xml.etree.ElementTree as ET

from PIL import Image
import clipparse
import psdparse
import resvg_py
import vtracer

from clip_vectors import ClipFormatError, fmt, read_vectors


SVG = 'http://www.w3.org/2000/svg'
PSD_BLEND = {
    0: 'norm', 1: 'dark', 2: 'mul ', 3: 'idiv', 4: 'lbrn', 5: 'fsub',
    6: 'dkCl', 7: 'lite', 8: 'scrn', 9: 'div ', 10: 'div ', 11: 'lddg',
    12: 'lddg', 13: 'lgCl', 14: 'over', 15: 'sLit', 16: 'hLit',
    17: 'vLit', 18: 'lLit', 19: 'pLit', 20: 'hMix', 21: 'diff',
    22: 'smud', 23: 'hue ', 24: 'sat ', 25: 'colr', 26: 'lum ',
    30: 'pass', 36: 'fdiv',
}


class ConversionError(Exception):
    pass


@dataclass(frozen=True)
class ConversionResult:
    directory: Path
    routes: tuple
    warnings: tuple


def svg_document(size):
    width, height = size
    return ET.Element('svg', {
        'xmlns': SVG, 'version': '1.1', 'width': str(width),
        'height': str(height), 'viewBox': f'0 0 {width} {height}',
    })


def to_bgra(image):
    return image.convert('RGBA').tobytes('raw', 'BGRA')


def trace(image, parent, left, top):
    box = image.getchannel('A').getbbox()
    if not box:
        return 0
    image = image.crop(box)
    alpha = image.getchannel('A')
    if alpha.getextrema() == (0, 255):
        # Trace the mid-point of anti-aliased opaque edges.
        image.putalpha(alpha.point(lambda value: 255 if value >= 128 else 0))
    # Keep a transparent border so an outline which touches the crop remains closed.
    padded = Image.new('RGBA', (image.width + 2, image.height + 2))
    padded.paste(image, (1, 1))
    data = BytesIO()
    padded.save(data, format='PNG')
    output = ET.fromstring(vtracer.convert_raw_image_to_svg(
        data.getvalue(), 'png', colormode='color', hierarchical='cutout',
        mode='spline', filter_speckle=1, color_precision=6, path_precision=4,
    ))
    parent.set('transform', f'translate({left + box[0] - 1} {top + box[1] - 1})')
    paths = output.findall(f'{{{SVG}}}path')
    for path in paths:
        ET.SubElement(parent, 'path', {
            key: value for key, value in path.attrib.items()
            if key in {'d', 'fill', 'transform', 'fill-rule'}
        })
    return len(paths)


class Artwork:
    def __init__(self, source, vector_data):
        self.doc = clipparse.ClipFile()
        if not self.doc.load(str(source)):
            raise ConversionError('CLIP を開けません。' + str(self.doc.error))
        self.size = self.doc.width, self.doc.height
        if not all(0 < n <= 16000 for n in self.size) or self.size[0] * self.size[1] > 24_000_000:
            raise ConversionError('試作版で扱える画像サイズを超えています（2,400万画素まで）。')
        self.layers = self.doc.layers
        if len(self.layers) > 250:
            raise ConversionError('試作版で扱えるレイヤー数を超えています（250枚まで）。')

        self.vector = vector_data
        self.notes, self.routes = [], []
        self.warnings = list(vector_data.warnings)
        self.root = svg_document(self.size)
        self.psd = psdparse.PSDFile()
        self.psd.create_blank(*self.size)

    def get_layer_image(self, layer):
        if layer.width <= 0 or layer.height <= 0:
            return None, 0, 0
        # Decode only the part intersecting the canvas.
        left, top = max(0, layer.left), max(0, layer.top)
        right, bottom = min(self.size[0], layer.right), min(self.size[1], layer.bottom)
        if right <= left or bottom <= top:
            return None, 0, 0
        size = right - left, bottom - top
        content = self.doc.layer_region(
            layer.index, left - layer.left, top - layer.top, *size, 'masked',
        )
        if not content:
            return None, left, top
        return Image.frombytes('RGBA', size, content, 'raw', 'BGRA'), left, top

    def add_pixels(self, layer, image, left, top, blend):
        if image is None or image.getchannel('A').getbbox() is None:
            return
        index = self.psd.add_layer(
            layer.name_unicode or 'レイヤー', left, top, to_bgra(image),
            *image.size, blend, layer.opacity,
        )
        self.psd.layers[index].visible = layer.visible

    def add_tree(self, indices, parent, depth=0):
        if depth > 30:
            raise ConversionError('レイヤーの入れ子が深すぎます。')
        for index in indices:
            layer = self.layers[index]
            name = layer.name_unicode or 'レイヤー'
            blend = PSD_BLEND.get(layer.composite_raw, 'norm')
            svg_group = ET.Element('g', {
                'id': f'layer-{layer.main_id}', 'opacity': fmt(layer.opacity / 255),
            })
            ET.SubElement(svg_group, 'title').text = name
            if not layer.visible:
                svg_group.set('display', 'none')

            if layer.is_group:
                start = len(self.psd.layers)
                self.add_tree(self.doc.children(index), svg_group, depth + 1)
                children = len(self.psd.layers) - start
                if children:
                    idx = self.psd.add_folder(name, start, children, False, blend, layer.opacity)
                    self.psd.layers[idx].visible = layer.visible
                if len(svg_group) > 1:
                    parent.append(svg_group)
                continue

            if layer.is_filter:
                self.warnings.append(f'{name}：調整レイヤーは PNG の見た目に含まれます。')
                continue
            if layer.has_mask:
                self.warnings.append(f'{name}：マスクは PSD のピクセルに反映します。ベクター線には適用しません。')
            if layer.clipping or layer.composite_raw not in (0, 30):
                self.warnings.append(f'{name}：クリッピング・合成モードの見た目は PNG で確認してください。')
            if layer.is_text:
                self.warnings.append(f'{name}：テキストは画像として扱います。')

            layer_type, is_vector = self.vector.layer_types.get(layer.main_id, (None, False))
            paths = self.vector.strokes.get(layer.main_id, ())
            if paths:
                svg_group.set('data-route', 'native')
                svg_group.extend(paths)
                parent.append(svg_group)
                self.routes.append('native')
                self.notes.append(f'{name}：元のストロークから図形 {len(paths)} 個')
                draft = svg_document(self.size)
                draft.extend(deepcopy(paths))
                pixels = resvg_py.svg_to_bytes(svg_string=ET.tostring(draft, encoding='unicode'))
                with Image.open(BytesIO(pixels)) as rendered:
                    raw = rendered.convert('RGBA')
                if layer.has_mask:
                    from PIL import ImageChops
                    mask = self.doc.layer_region(index, -layer.left, -layer.top, *self.size, 'mask')
                    if len(mask) == self.size[0] * self.size[1] * 4:
                        alpha = Image.frombytes('RGBA', self.size, mask, 'raw', 'BGRA').getchannel('A')
                        raw.putalpha(ImageChops.multiply(raw.getchannel('A'), alpha))
                box = raw.getchannel('A').getbbox()
                if box:
                    self.add_pixels(layer, raw.crop(box), box[0], box[1], blend)
                continue

            pixels, left, top = self.get_layer_image(layer)
            if pixels is None or pixels.getchannel('A').getbbox() is None:
                if is_vector:
                    self.warnings.append(f'{name}：パスとピクセルを取り出せませんでした。')
                continue
            self.add_pixels(layer, pixels, left, top, blend)
            # The paper layer is a background, and remains a clean rectangle in the SVG.
            if layer_type == 1584 and pixels.getbbox() == (0, 0, *pixels.size):
                rgba = pixels.getpixel((0, 0))
                if all(lo == hi for lo, hi in pixels.getextrema()) and rgba[3] == 255:
                    color = '#%02x%02x%02x' % rgba[:3]
                    ET.SubElement(svg_group, 'rect', {
                        'x': str(left), 'y': str(top), 'width': str(pixels.width),
                        'height': str(pixels.height), 'fill': color,
                    })
                    parent.append(svg_group)
                    continue
            traced = trace(pixels, svg_group, left, top)
            if traced:
                svg_group.set('data-route', 'trace')
                parent.append(svg_group)
                self.routes.append('trace')
                self.notes.append(f'{name}：画像から輪郭をトレースしてパス {traced} 個')
            else:
                self.warnings.append(f'{name}：画像から輪郭を取り出せませんでした。')

    def save(self, stage, stem):
        self.add_tree(self.doc.roots, self.root)
        if not self.routes:
            self.warnings.append('この原稿には変換できるパスがありませんでした。')
        preview, _, _ = self.doc.preview_png()
        if preview:
            with Image.open(BytesIO(preview)) as saved:
                image = saved.convert('RGBA')
        else:
            image = Image.new('RGBA', (1, 1))
        if image.size != self.size:
            data, _ = self.psd.composite()
            image = Image.frombytes('RGBA', self.size, data, 'raw', 'BGRA')
            self.warnings.append('原寸の合成画像が保存されていないため、PNG はレイヤーから再合成しました。')
        dpi = self.doc.resolution
        image.save(stage / f'{stem}.png', dpi=(dpi, dpi) if dpi > 0 else None)
        self.psd.set_merged_image(to_bgra(image))
        if not self.psd.save(str(stage / f'{stem}.psd')):
            raise ConversionError('PSD の保存に失敗しました。')
        if 'native' in self.routes:
            self.warnings.append('PSD のベクター線は描画し直した画像です。元のブラシの形状・質感は PNG で確認できます。')
        svg = stage / f'{stem}.svg'
        ET.ElementTree(self.root).write(svg, encoding='utf-8', xml_declaration=True)


def convert(source):
    source = Path(source)
    if source.suffix.lower() != '.clip' or not source.is_file():
        raise ConversionError('クリスタの .clip ファイルを選んでください。')
    try:
        artwork = Artwork(source, read_vectors(source))
        with TemporaryDirectory(prefix='.clip-drop-', dir=source.parent) as temp:
            stage = Path(temp)
            artwork.save(stage, source.stem)
            lines = [source.name, f'{artwork.size[0]} × {artwork.size[1]} px', '', *artwork.notes]
            if artwork.warnings:
                lines.extend(['', '変換時の補足', *dict.fromkeys(artwork.warnings)])
            (stage / f'{source.stem}.txt').write_text('\n'.join(lines) + '\n', encoding='utf-8-sig')
            for version in count(1):
                postfix = '' if version == 1 else f' ({version})'
                output = source.parent / f'{source.stem} - 変換結果{postfix}'
                if output.exists():
                    continue
                try:
                    stage.rename(output)
                except FileExistsError:
                    continue
                break
    except (ClipFormatError, sqlite3.DatabaseError, ET.ParseError, OSError, ValueError, RuntimeError) as error:
        raise ConversionError(str(error)) from error
    return ConversionResult(output, tuple(artwork.routes), tuple(dict.fromkeys(artwork.warnings)))
