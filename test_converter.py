from hashlib import sha256
from io import BytesIO
from pathlib import Path
from shutil import copy2
import sys
from tempfile import TemporaryDirectory
from unittest import TestCase, main
from xml.etree import ElementTree as ET

from PIL import Image, ImageChops

sys.path.insert(0, str(Path(__file__).resolve().parent / 'deps'))
import clipparse
import psdparse
import resvg_py

from conversion import convert, ConversionError

SAMPLES = Path(__file__).parent / 'samples'
SVG = '{http://www.w3.org/2000/svg}'


class ConversionTests(TestCase):
    def test_csp_originals_take_distinct_routes_and_keep_their_appearance(self):
        cases = {
            'vector': ('native',),
            'raster': ('trace',),
            'mixed': ('trace', 'native'),
        }
        with TemporaryDirectory() as folder:
            for stem, expected in cases.items():
                with self.subTest(stem=stem):
                    source = Path(folder) / f'{stem}.clip'
                    copy2(SAMPLES / source.name, source)
                    digest = sha256(source.read_bytes()).digest()
                    result = convert(source)
                    self.assertEqual(sha256(source.read_bytes()).digest(), digest)
                    self.assertEqual(result.routes, expected)
                    svg = result.directory / f'{stem}.svg'
                    root = ET.parse(svg)
                    self.assertTrue(root.findall(f'.//{SVG}path'))
                    self.assertEqual(
                        tuple(group.get('data-route') for group in root.findall(f'.//{SVG}g')
                              if group.get('data-route')),
                        expected,
                    )
                    doc = clipparse.ClipFile()
                    self.assertTrue(doc.load(str(source)))
                    original = Image.open(BytesIO(doc.preview_png()[0])).convert('RGBA')
                    del doc
                    png = Image.open(result.directory / f'{stem}.png').convert('RGBA')
                    self.assertEqual(png.size, (1600, 1200))
                    self.assertEqual(png.tobytes(), original.tobytes())
                    self.assertLess(png.convert('L').getextrema()[0], 50)

                    psd = psdparse.PSDFile()
                    self.assertTrue(psd.load_bytes((result.directory / f'{stem}.psd').read_bytes()))
                    self.assertEqual(len(psd.layers), len(expected) + 1)
                    composite, _ = psd.composite()
                    if stem == 'raster':
                        self.assertEqual(composite, original.tobytes('raw', 'BGRA'))
                    with Image.open(BytesIO(resvg_py.svg_to_bytes(svg_string=svg.read_text(encoding='utf-8')))) as rendered:
                        ref = original.convert('L').point(lambda x: 255 if x < 128 else 0)
                        actual = rendered.convert('L').point(lambda x: 255 if x < 128 else 0)
                        intersection = ImageChops.darker(ref, actual).histogram()[255]
                        union = ImageChops.lighter(ref, actual).histogram()[255]
                        self.assertGreater(intersection / union, 0.91)

    def test_repeated_conversion_does_not_replace_prior_outputs(self):
        with TemporaryDirectory() as folder:
            source = Path(folder) / '日本語 ファイル.clip'
            copy2(SAMPLES / 'vector.clip', source)
            first = convert(source).directory
            second = convert(source).directory
            self.assertNotEqual(first, second)
            self.assertTrue((first / f'{source.stem}.png').is_file())
            self.assertTrue((second / f'{source.stem}.png').is_file())

    def test_invalid_clip_produces_no_output(self):
        with TemporaryDirectory() as folder:
            source = Path(folder) / 'invalid.clip'
            source.write_bytes(b'not a CLIP')
            with self.assertRaises(ConversionError):
                convert(source)
            self.assertEqual(list(Path(folder).iterdir()), [source])


if __name__ == '__main__':
    main()
