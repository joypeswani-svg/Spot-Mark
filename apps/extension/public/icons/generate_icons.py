#!/usr/bin/env python3
"""
generate_icons.py — Generate TruthLens PNG icons from SVG using cairosvg.
Run once after installing: pip install cairosvg
Outputs: icon-16.png, icon-32.png, icon-48.png, icon-128.png
"""

SVG_CONTENT = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">
  <!-- Background -->
  <rect width="128" height="128" rx="24" fill="#0F172A"/>
  <!-- Outer ring -->
  <circle cx="56" cy="56" r="30" fill="none" stroke="#6366F1" stroke-width="8"/>
  <!-- Magnifying handle -->
  <line x1="79" y1="79" x2="104" y2="104" stroke="#6366F1" stroke-width="10" stroke-linecap="round"/>
  <!-- Checkmark inside lens -->
  <polyline points="43,56 52,65 70,47" fill="none" stroke="#22C55E" stroke-width="7" stroke-linecap="round" stroke-linejoin="round"/>
</svg>'''

import sys

try:
    import cairosvg
    SIZES = [16, 32, 48, 128]
    for size in SIZES:
        output = f"icon-{size}.png"
        cairosvg.svg2png(bytestring=SVG_CONTENT.encode(), write_to=output, output_width=size, output_height=size)
        print(f"Generated {output}")
    print("All icons generated successfully.")
except ImportError:
    print("cairosvg not installed. Saving SVG source for manual conversion.", file=sys.stderr)
    with open("icon.svg", "w") as f:
        f.write(SVG_CONTENT)
    print("Saved icon.svg — convert with: npx sharp-cli -i icon.svg -o icon-128.png resize 128 128")
