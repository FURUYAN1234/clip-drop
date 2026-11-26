# CLIP Drop · Beta / 習作・ベータ版

Drop a Clip Studio Paint project to export an editable SVG, a layered PSD, and a PNG on Windows. / クリスタの原稿をドロップすると、編集用SVGとPSD、照合用PNGを書き出すWindowsアプリです。

**Experimental beta.** This may help when you receive a .clip file on a Windows computer without Clip Studio Paint. Converter tests cover three line-art samples. / **習作・ベータ版です。** クリスタのないWindows PCで .clip を受け取ったとき、中身の確認や別アプリでの作業に使えるかもしれません。変換は線画３原稿で検証しました。

## Get started / 使い方

1. Download and extract the [Windows x64 release ZIP](https://github.com/FURUYAN1234/clip-drop/releases/tag/v0.1.0). / [Windows x64用配布ZIP](https://github.com/FURUYAN1234/clip-drop/releases/tag/v0.1.0)をダウンロードして、すべて展開します。
2. Run **CLIP Drop.exe** and drop one or more .clip files in the window. You can also use the file picker. / **CLIP Drop.exe** を起動し、.clipを枠へドロップします。ファイル選択にも対応しています。
3. Open the result folder next to the original. The app adds a number when the output name already exists. / 元原稿の隣にできる結果フォルダーを開きます。同名の結果がある場合は連番を付けます。

The converter runs locally. It reads your source project and puts the exported files in a separate folder. / 変換はローカルで行います。原稿を読み取り、書き出しは別フォルダーに保存します。

## Output / 出力

| File / 形式 | What you get / 内容 |
| --- | --- |
| SVG | Centerline paths from CLIP vector strokes and outline paths traced from raster layers. / ベクター層から作る中心線と、ラスター層からトレースする輪郭パス。 |
| PSD | Separate pixel layers for paper and artwork, with layer names, visibility and supported groups. Vector strokes are redrawn as pixels. / 用紙と絵を別々の画像レイヤーにし、レイヤー名・表示状態・対応するグループを引き継ぎます。ベクター線はピクセルとして描画します。 |
| PNG | The full-sized composite stored by Clip Studio Paint when available. / クリスタが保存した原寸合成画像があれば、その画素を使用します。 |
| TXT | Layer processing, fallbacks and approximation warnings. / 層ごとの処理と、代替処理・近似の記録。 |

## Conversion / 変換の仕組み

A cubic segment uses start and end positions $P_0,P_1$ and control points $C_0,C_1$. Stored cubic controls are used when available. For Clip Studio spline records the tangents are approximated from neighboring positions. / ３次ベジェ区間は端点 $P_0,P_1$ と制御点 $C_0,C_1$ で表します。３次ベジェレコードにある制御点はその座標を使い、クリスタのスプラインでは前後の点から接線を近似します。

$$
B(t)=(1-t)^3P_0+3(1-t)^2tC_0+3(1-t)t^2C_1+t^3P_1,\quad 0\le t\le1
$$

For a stroke with a stored radius $r$ and per-point width factors $w_i$, the prototype exports one SVG stroke width $W=2r\,\sum_i w_i/n$. Pressure-shaped width and brush texture can look different. / 保存された半径を $r$、各点の幅係数を $w_i$ とし、SVGの線幅を $W=2r\,\sum_i w_i/n$ とします。可変線幅やブラシの質感には差が出ます。

For raster layers whose alpha spans 0–255, tracing uses the binary silhouette $M(x,y)=\mathbf{1}[\alpha(x,y)\ge128]$. VTracer fits closed vector paths to the pixel boundaries and color regions. / 透明度が0〜255のラスター層では $M(x,y)=\mathbf{1}[\alpha(x,y)\ge128]$ の輪郭を使います。VTracerでピクセルの境界と色の領域を閉じたパスに近似します。

## Verification / 検証

These are results for three 1,600 × 1,200 CLIP files authored in CLIP STUDIO PAINT EX 4.1.4. The pair has the same artwork. The mixed file adds vector shapes over the raster drawing. / クリスタEX 4.1.4で作った1,600 × 1,200原稿３件の結果です。ベクター版とラスター版は同じ絵で、混在版にはベクターの図形を追加しました。

We rendered the SVG at the original dimensions. Ink pixels were defined as grayscale values below 128. For input ink set $A$ and output ink set $B$, the overlap is $|A\cap B|/|A\cup B|$. / SVGを原寸に描画し、グレースケール値128未満を線として、入力の領域 $A$ と出力の領域 $B$ の重なり $|A\cap B|/|A\cup B|$ を測りました。

| Sample / 原稿 | SVG ink IoU / 線の重なり | PNG composite mismatch / 異なる画素 |
| --- | ---: | ---: |
| Vector / ベクター | 92.2% | 0 |
| Raster / ラスター | 94.5% | 0 |
| Mixed / 混在 | 94.1% | 0 |

Photoshop 2026 opened the PSD exported from the vector sample with separate paper and artwork layers. CLIP STUDIO PAINT displayed editable points for both routes in the re-imported mixed SVG. / ベクター原稿のPSDをPhotoshop 2026で開き、用紙と線画を別レイヤーで確認しました。混在SVGをクリスタに読み戻し、両経路で制御点を選択できました。

In the mixed sample the PSD retained the paper, raster line art and rendered vector art as separate pixel layers. The empty source layer was omitted. / 混在原稿では元の用紙、ラスター線画、ベクター線画がPSDの別画像レイヤーとして残り、空レイヤー１枚は省かれました。

## Limits / 制約

This first release focuses on still artwork within 24 million pixels and 250 layers. CLIP-specific brush texture, live effects, masks, text, frame borders, and animation have limited interchange. / 初版は2,400万画素・250レイヤー以内の静止画が対象です。クリスタ固有のブラシ、効果、マスク、テキスト、コマ枠、アニメーションの編集互換には制限があります。

Illustrator can open the SVG. You can save as AI in Illustrator after opening the SVG. This version exports SVG, PSD and PNG. / SVGをIllustratorで開いたあと、Illustratorから .ai として保存できます。この版はSVG・PSD・PNGを書き出します。

## Credits / 参照

The CLIP vector layout follows the documented [clipfile-rs](https://github.com/Aodaruma/clipfile-rs) work. Layers and PSD output use [clipparse](https://github.com/wamsoft/clipparse) and [psdparse](https://github.com/wamsoft/psdparse). / CLIPのベクター形式はclipfile-rsの公開資料を参照し、画素読込とPSD出力にclipparseとpsdparseを使っています。

## Related apps and workflows / 関連アプリ・ワークフロー

| Name / 名称 | Source / ソース | Article / 紹介記事 |
| --- | --- | --- |
| Super FURU AI 4-koma System | [GitHub](https://github.com/FURUYAN1234/nano-banana-pro) | [note](https://note.com/happy_duck780/n/ndf063558c1f5) |
| AI Story Maker | [GitHub](https://github.com/FURUYAN1234/story-maker) | [note](https://note.com/happy_duck780/n/nd3d972922868) |
| AI Character Sheet Maker | [GitHub](https://github.com/FURUYAN1234/character-sheet-maker) | [note](https://note.com/happy_duck780/n/neccbebd7d957) |
| AI漫画翻訳ツール | [GitHub](https://github.com/FURUYAN1234/comic-translation) | [note](https://note.com/happy_duck780/n/ne462dfc55ec8) |
| PanoForge | [GitHub](https://github.com/FURUYAN1234/panoforge) | [note](https://note.com/happy_duck780/n/nb53b121fef88) |
| AI Voice Comic Maker | [GitHub](https://github.com/FURUYAN1234/ai-voice-comic-maker) | [note](https://note.com/happy_duck780/n/ndc6533c1512f) |
| 物語バズメーカー | [GitHub](https://github.com/FURUYAN1234/viral-radar) | [note](https://note.com/happy_duck780/n/ncc593101d77f) |
| ナレーション動画メーカー | [GitHub](https://github.com/FURUYAN1234/gemini-narration-studio) | [note](https://note.com/happy_duck780/n/n97d49c1c98b1) |
| AI Image Bridge | [GitHub](https://github.com/FURUYAN1234/ai-image-bridge) | [note](https://note.com/happy_duck780/n/n6747a089fce7) |
| AIトレーサー なぞり君 | [GitHub](https://github.com/FURUYAN1234/ai-tracer-nazori-kun) | [note](https://note.com/happy_duck780/n/n75301de9493a) |
| MiniMax H3 Video | [GitHub](https://github.com/FURUYAN1234/comfyui-h3-workflows) | [note](https://note.com/happy_duck780/n/n15e732b3147b) |
| MiniMax H3 MV | [GitHub](https://github.com/FURUYAN1234/comfyui-h3-workflows) | [note](https://note.com/happy_duck780/n/ne8a84cb6db37) |
| KomaOrbit | [GitHub](https://github.com/FURUYAN1234/comfyui-h3-workflows) | [note](https://note.com/happy_duck780/n/n3f68482d5edd) |
| 長尺動画AnimeSharpアップスケーラー | [GitHub](https://github.com/FURUYAN1234/comfyui-long-video-upscaler) | [note](https://note.com/happy_duck780/n/n0f190160e307) |
| 日本語おまかせ作曲 | [GitHub](https://github.com/FURUYAN1234/ComfyUI-YuE2-Japanese) | [note](https://note.com/happy_duck780/n/n57df44cf7fd2) |
| 日本語おまかせナレーション | [GitHub](https://github.com/FURUYAN1234/ComfyUI-Local-Narration-Japanese) | [note](https://note.com/happy_duck780/n/nda7ed302d544) |
| MangaScreen JP | [GitHub](https://github.com/FURUYAN1234/ComfyUI-MangaScreen-JP) | [note](https://note.com/happy_duck780/n/n5c89a250fb82) |
| Local Handoff MCP | [GitHub](https://github.com/FURUYAN1234/local-handoff-mcp) | [note](https://note.com/happy_duck780/n/n806c7bc6de94) |
| Codex Usage / Codex 残量 | [GitHub](https://github.com/FURUYAN1234/codex-usage-overlay) | [note](https://note.com/happy_duck780/n/n98e53f17d74a) |

[Suite overview / アプリ・ワークフロー総合案内](https://note.com/happy_duck780/n/nbdf826604ce7)
