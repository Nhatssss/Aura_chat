"""Generate PWA icons directly with Pillow (no SVG dependency)."""
from PIL import Image, ImageDraw, ImageFont
import os

def make_icon(size, outpath):
    img = Image.new('RGBA', (size, size), (3, 11, 24, 255))
    draw = ImageDraw.Draw(img)
    cx, cy = size // 2, size // 2
    r = size * 0.38

    # Outer hexagon
    pts = []
    for i in range(6):
        angle = 3.14159 / 180 * (60 * i - 30)
        pts.append((cx + r * 2 * 0.9 * (1 if i in (0,2,3,5) else 0.7), 0))  # just skip - easier to calc properly
    # Proper hexagon
    pts = []
    for i in range(6):
        angle = 3.14159 / 180 * (60 * i - 30)  # pointy top
        pts.append((cx + r * 2 * 0.82 * (1 if i in (0,1,2,3) else 0.88), 0))
    # Actually, let me just do it properly
    pts = []
    for i in range(6):
        angle = 3.14159 / 180 * (60 * i - 30)  # flat top
        pts.append((cx + r * 2 * 0.85, 0))

    # Just draw a proper flat-top hexagon
    pts = []
    for i in range(6):
        angle_deg = 60 * i
        angle_rad = 3.14159 / 180 * angle_deg
        px = cx + r * 1.7 * 0.85 * __import__('math').cos(angle_rad)
        py = cy + r * 1.7 * 0.85 * __import__('math').sin(angle_rad)
        pts.append((px, py))

    # Actually simplify - use pointy-top hexagon look
    # Draw a simpler design
  
    # Background rounded rect  
    draw.rounded_rectangle([2, 2, size-3, size-3], radius=size//8, outline=(0, 229, 255, 180), width=max(2, size//40))
    
    # Hexagon shape
    hex_pts = []
    for i in range(6):
        angle_deg = 60 * i - 30
        angle_rad = 3.14159 / 180 * angle_deg
        px = cx + r * 1.8 * __import__('math').cos(angle_rad)
        py = cy + r * 1.8 * __import__('math').sin(angle_rad)
        hex_pts.append((px, py))
    
    # Outer hexagon
    draw.polygon(hex_pts, outline=(0, 229, 255, 220), width=max(3, size//20))
    
    # Inner hexagon (slightly smaller)
    hex_inner = []
    for i in range(6):
        angle_deg = 60 * i - 30
        angle_rad = 3.14159 / 180 * angle_deg
        px = cx + r * 1.3 * __import__('math').cos(angle_rad)
        py = cy + r * 1.3 * __import__('math').sin(angle_rad)
        hex_inner.append((px, py))
    draw.polygon(hex_inner, outline=(124, 58, 237, 180), width=max(2, size//30))
    
    # Letter A
    font_size = int(size * 0.4)
    try:
        # Try to find a font
        font_paths = [
            'C:/Windows/Fonts/segoeui.ttf',
            'C:/Windows/Fonts/arial.ttf',
        ]
        font = None
        for fp in font_paths:
            if os.path.exists(fp):
                font = ImageFont.truetype(fp, font_size)
                break
        if not font:
            font = ImageFont.load_default()
    except:
        font = ImageFont.load_default()
    
    # Draw "A" letter
    bbox = draw.textbbox((0, 0), "A", font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    tx = cx - tw // 2
    ty = cy - th // 2 + size // 12
    draw.text((tx, ty), "A", fill=(0, 229, 255, 255), font=font)
    
    img.save(outpath, 'PNG')
    print(f"  -> {outpath} ({size}x{size})")

os.makedirs(os.path.dirname(__file__), exist_ok=True)
make_icon(192, os.path.join(os.path.dirname(__file__), 'icon-192.png'))
make_icon(512, os.path.join(os.path.dirname(__file__), 'icon-512.png'))
print("\nDone!")
