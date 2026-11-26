# Layer-wise CLIP conversion and a line-art evaluation

CLIP Drop v0.1.0 · Experimental beta technical paper

## Abstract

CLIP Drop reads .clip projects from Clip Studio Paint and exports SVG paths, a layered PSD, and a composite PNG. The evaluation uses a vector drawing, its rasterized counterpart, and a mixed project with vector geometry over raster line art. All three were authored in Clip Studio Paint EX 4.1.4.

## Method

The reader maps stored strokes to CLIP layer IDs. A cubic SVG centerline segment is determined by endpoints $P_0,P_1$ and controls $C_0,C_1$.

$$
B(t)=(1-t)^3P_0+3(1-t)^2tC_0+3(1-t)t^2C_1+t^3P_1,\qquad 0\le t\le1
$$

The converter uses stored cubic controls when available and approximates spline tangents from adjacent points. It reduces a radius $r$ and pointwise width factors $w_i$ to a constant SVG width $W=2r\sum_{i=1}^n w_i/n$.

For raster layers, the converter decodes the portion within the canvas. When the minimum and maximum alpha are 0 and 255, it thresholds antialiased edges using $M(x,y)=\mathbf{1}[\alpha(x,y)\ge128]$. VTracer fits closed paths to the resulting outlines and color regions. SVG layer groups record the route.

The PSD stores raster layers and rendered vector layers as pixels. When the CLIP file contains a full-size composite, that composite supplies the PNG and the merged PSD image. Otherwise the application composites the decoded PSD layers.

## Evaluation

All three projects are 1,600 × 1,200 pixels. We thresholded the reference composite and rendered SVG at luminance below 128 to obtain ink masks $A$ and $B$, then calculated $J=|A\cap B|/|A\cup B|$.

| Project | SVG conversion route | Ink IoU | Different RGBA pixels in PNG |
| --- | --- | ---: | ---: |
| Vector | Stored strokes | 92.2% | 0 |
| Raster | Outline trace | 94.5% | 0 |
| Mixed | Outline trace and stored strokes | 94.1% | 0 |

We reimported the mixed SVG into Clip Studio Paint and selected control points from both routes. We also opened the vector sample’s exported PSD in Photoshop 2026 and verified separate artwork and paper layers.

## Scope

These measurements describe three line-art fixtures. Compatibility is limited for variable width, Clip Studio brush rendering, adjustment layers, masks, and other application-specific editing features. The first release targets still projects of up to 24 million pixels and 250 layers on 64-bit Windows. It exports SVG for import into Illustrator.

## References

- [clipfile-rs](https://github.com/Aodaruma/clipfile-rs)
- [ClipParse](https://github.com/wamsoft/clipparse) and [PsdParse](https://github.com/wamsoft/psdparse)
- [VTracer](https://github.com/visioncortex/vtracer) and [resvg](https://github.com/linebender/resvg)
