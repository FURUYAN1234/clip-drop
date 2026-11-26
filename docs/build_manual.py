"""Generate the Japanese CLIP Drop manual using ReportLab on Windows."""
import json
from pathlib import Path
import os

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph
from xml.sax.saxutils import escape


ROOT = Path(__file__).resolve().parents[1]
VERSION = json.loads((ROOT / 'package.json').read_text(encoding='utf-8'))['version']
FONTS = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts'
pdfmetrics.registerFont(TTFont('BIZ', FONTS / 'BIZ-UDGothicR.ttc', subfontIndex=0))
pdfmetrics.registerFont(TTFont('BIZBold', FONTS / 'BIZ-UDGothicB.ttc', subfontIndex=0))

PAGE_W, PAGE_H = A4
MARGIN = 46
WIDTH = PAGE_W - MARGIN * 2
INK = colors.HexColor('#1D302A')
SUBTLE = colors.HexColor('#45554F')
ACCENT = colors.HexColor('#295B48')
PANEL = colors.HexColor('#EDE9E0')
PAPER = colors.HexColor('#F6F3ED')
BODY = ParagraphStyle('body', fontName='BIZ', fontSize=11.3, leading=18.5,
                      textColor=INK, wordWrap='CJK', alignment=TA_LEFT)
SMALL = ParagraphStyle('small', parent=BODY, fontSize=9, leading=14, textColor=SUBTLE)


def paragraph(pdf, text, top, style=BODY, inset=0):
    element = Paragraph(escape(text), style)
    _, height = element.wrap(WIDTH - inset * 2, PAGE_H)
    bottom = top - height
    if bottom < 57:
        raise ValueError('Text exceeds the page margin')
    element.drawOn(pdf, MARGIN + inset, bottom)
    return bottom


def section(pdf, title, text, top):
    pdf.setFont('BIZBold', 13)
    pdf.setFillColor(ACCENT)
    pdf.drawString(MARGIN, top - 13, title)
    return paragraph(pdf, text, top - 22) - 19


def header(pdf, title, page):
    pdf.setFillColor(PAPER)
    pdf.rect(0, 0, PAGE_W, PAGE_H, stroke=0, fill=1)
    pdf.setFillColor(ACCENT)
    pdf.rect(0, PAGE_H - 6, PAGE_W, 6, stroke=0, fill=1)
    pdf.setFont('BIZBold', 10)
    pdf.drawString(MARGIN, PAGE_H - 49, 'CLIP Drop   /   習作・ベータ版')
    pdf.setFont('BIZBold', 26)
    pdf.setFillColor(INK)
    pdf.drawString(MARGIN, PAGE_H - 86, title)
    pdf.setFont('BIZ', 9)
    pdf.setFillColor(SUBTLE)
    pdf.drawString(MARGIN, 31, f'CLIP Drop v{VERSION}   /   Windows x64')
    pdf.drawRightString(PAGE_W - MARGIN, 31, f'{page} / 2')
    return PAGE_H - 110


def render():
    target = ROOT / 'docs' / 'CLIP-Drop-manual.pdf'
    pdf = canvas.Canvas(str(target), pagesize=A4, invariant=True)
    pdf.setTitle(f'CLIP Drop v{VERSION} 操作マニュアル')
    pdf.setAuthor('FURU')
    y = header(pdf, 'CLIP Drop 操作マニュアル', 1)
    y = paragraph(pdf, 'クリスタが入っていないWindows PCで .clip を受け取ったときに使えるかもしれない変換ツールです。元データは残し、SVG・PSD・PNGと変換メモを読み書き可能な別フォルダーに保存します。', y) - 23
    y = section(pdf, '1  ZIPを展開する',
                'Windows 64ビット用の配布ZIPを保存し、右クリックから「すべて展開」を選びます。展開したCLIP Dropフォルダー内の「CLIP Drop.exe」を開きます。ZIPの中から直接実行せず、同梱の部品を同じフォルダーに置いてください。', y)
    y = section(pdf, '2  原稿をドロップする',
                'エクスプローラーから .clip ファイルをアプリの枠内へドロップすると、変換が始まります。「ファイルを選ぶ…」から操作することもできます。複数のファイルを渡した場合は順番に変換します。', y)
    y = section(pdf, '3  結果フォルダーを開く',
                '完了したら「結果フォルダーを開く」を押します。元の原稿と同じ場所に「ファイル名 - 変換結果」フォルダーができます。同名のフォルダーがあれば連番が付き、前の結果は残ります。複数の変換では最後に成功したフォルダーが開きます。', y)
    y = section(pdf, '検証原稿で試す',
                '配布ZIP内の samples に、vector.clip、raster.clip、mixed.clip が入っています。混在原稿で試すなら mixed.clip をドロップしてください。結果フォルダーには変換メモも入ります。', y)
    y = section(pdf, 'ファイルを入れても変換できないとき',
                '「エラーの詳細」を開き、対象ファイルと理由を確認します。原稿の場所に保存できない場合は、書き込み可能な場所へ原稿のコピーを置いて試してください。画面上部の「マニュアル取得」からこのPDFを開けます。', y)
    pdf.showPage()

    y = header(pdf, '出力を確認する', 2)
    y = section(pdf, 'SVG  編集できる線と輪郭',
                'ベクターレイヤーに保存された線から中心線のパスを作ります。ラスター層は画素の輪郭をトレースします。両方を含む原稿では同じSVGに収めます。Illustratorで .ai が必要な場合は、SVGを開いて「別名で保存」からAdobe Illustrator（.ai）を選びます。', y)
    y = section(pdf, 'PSD  レイヤーを分けて保存',
                '用紙や描画内容を対応するピクセルレイヤーに分けます。クリスタのベクター線もPSDではピクセルになります。空のレイヤーは省く場合があります。', y)
    y = section(pdf, 'PNGと変換メモ  見た目を照合する',
                'クリスタが保存した原寸の合成画像があれば、その画素をPNGに使います。変換メモ（TXT）には、レイヤーごとの処理と近似・代替処理が記録されます。ブラシの質感や可変線幅などはPNGと照合してください。', y)
    figure = ImageReader(str(ROOT / 'assets' / 'comparison.png'))
    image_width, image_height = figure.getSize()
    scaled_height = WIDTH * image_height / image_width
    top = y - 2
    actual_height = min(scaled_height, 204)
    actual_width = WIDTH * actual_height / scaled_height
    pdf.drawImage(figure, MARGIN, top - actual_height, width=actual_width, height=actual_height)
    y = paragraph(pdf, 'ベクター原稿とラスター原稿の比較。各段の左がクリスタ原本、中央がSVG、右がPSDです。', top - actual_height - 7, SMALL) - 16
    pdf.setFillColor(PANEL)
    pdf.roundRect(MARGIN, y - 56, WIDTH, 56, 6, stroke=0, fill=1)
    paragraph(pdf, '対応範囲はWindows x64、2,400万画素、250レイヤーまでの静止画です。クリスタ固有のブラシ、調整レイヤー、文字やマスクなどの再現には差が出ます。元の .clip は保管してください。', y - 9, SMALL, 12)
    pdf.save()


if __name__ == '__main__':
    render()
