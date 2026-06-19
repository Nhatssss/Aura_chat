"""Generate PWA icons from SVG using Pillow."""
import subprocess, sys, os

# Option 1: Use inkscape (if installed)
# Option 2: Use cairosvg
# Option 3: Manual - just copy the SVG and reference it directly

try:
    import cairosvg
    sizes = [192, 512]
    svg_path = os.path.join(os.path.dirname(__file__), 'icon.svg')
    for s in sizes:
        out = os.path.join(os.path.dirname(__file__), f'icon-{s}.png')
        cairosvg.svg2png(url=svg_path, write_to=out, output_width=s, output_height=s)
        print(f"Created {out}")
except ImportError:
    print("cairosvg not installed - install with: pip install cairosvg")
    print("Or use SVG directly in manifest (browsers support SVG icons now)")
    print("Create PNG files another way or leave SVG-only for now.")
