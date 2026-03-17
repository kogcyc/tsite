#!/usr/bin/env python3
"""
favgen.py — SVG → favicon set

Usage:
    python favgen.py input.svg /target/dir

Output:
    /target/dir/favicon/
"""

from pathlib import Path
import sys
import shutil

import cairosvg
from PIL import Image


# ------------------------------------------------------------
# Configuration
# ------------------------------------------------------------

# Standard favicon sizes
SIZES = [16, 32, 48, 64, 128, 180, 192, 256, 512]

OUTPUT_SUBDIR = "favicon"


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

def ensure_dir(path: Path):
    """Create directory if it does not exist."""
    path.mkdir(parents=True, exist_ok=True)


def render_png(svg_path: Path, png_path: Path, size: int):
    """Render a PNG of given size from SVG."""
    cairosvg.svg2png(
        url=str(svg_path),
        write_to=str(png_path),
        output_width=size,
        output_height=size
    )


def build_ico(png_32: Path, png_16: Path, ico_path: Path):
    """Build favicon.ico from 16px and 32px PNGs."""
    img32 = Image.open(png_32)
    img16 = Image.open(png_16)

    img32.save(
        ico_path,
        format="ICO",
        sizes=[(16, 16), (32, 32)]
    )


def copy_alias(png_paths: dict, favicon_dir: Path, name: str, size: int):
    """
    Copy a PNG to a standard alias name.
    Skips if source and destination are identical.
    """
    src = png_paths[size]
    dst = favicon_dir / name

    if src.resolve() == dst.resolve():
        return

    shutil.copy(src, dst)
    print(f"  ✓ {name}")


# ------------------------------------------------------------
# Main generation
# ------------------------------------------------------------

def generate(svg_file: Path, target_dir: Path):
    favicon_dir = target_dir / OUTPUT_SUBDIR
    ensure_dir(favicon_dir)

    print(f"→ Writing to: {favicon_dir}")

    png_paths = {}

    # --------------------------------------------------------
    # Generate PNGs
    # --------------------------------------------------------
    for size in SIZES:
        out = favicon_dir / f"favicon-{size}x{size}.png"
        render_png(svg_file, out, size)
        png_paths[size] = out
        print(f"  ✓ {out.name}")

    # --------------------------------------------------------
    # Aliases (only when names differ)
    # --------------------------------------------------------
    copy_alias(png_paths, favicon_dir, "apple-touch-icon.png", 180)
    copy_alias(png_paths, favicon_dir, "android-chrome-192x192.png", 192)
    copy_alias(png_paths, favicon_dir, "android-chrome-512x512.png", 512)

    # --------------------------------------------------------
    # ICO file
    # --------------------------------------------------------
    ico_path = favicon_dir / "favicon.ico"
    build_ico(png_paths[32], png_paths[16], ico_path)
    print("  ✓ favicon.ico")

    # --------------------------------------------------------
    # Web manifest
    # --------------------------------------------------------
    manifest_path = favicon_dir / "site.webmanifest"
    manifest_path.write_text("""{
  "name": "",
  "short_name": "",
  "icons": [
    {
      "src": "/favicon/android-chrome-192x192.png",
      "sizes": "192x192",
      "type": "image/png"
    },
    {
      "src": "/favicon/android-chrome-512x512.png",
      "sizes": "512x512",
      "type": "image/png"
    }
  ],
  "theme_color": "#ffffff",
  "background_color": "#ffffff",
  "display": "standalone"
}
""")
    print("  ✓ site.webmanifest")

    # --------------------------------------------------------
    # HTML snippet
    # --------------------------------------------------------
    print("\n--- <head> snippet ---\n")

    print("""<link rel="icon" type="image/png" sizes="32x32" href="/favicon/favicon-32x32.png">
<link rel="icon" type="image/png" sizes="16x16" href="/favicon/favicon-16x16.png">
<link rel="shortcut icon" href="/favicon/favicon.ico">
<link rel="apple-touch-icon" sizes="180x180" href="/favicon/apple-touch-icon.png">
<link rel="manifest" href="/favicon/site.webmanifest">""")

    print("\nDone.")


# ------------------------------------------------------------
# CLI
# ------------------------------------------------------------

def main():
    if len(sys.argv) != 3:
        print("Usage: python favgen.py input.svg /target/dir")
        sys.exit(1)

    svg = Path(sys.argv[1])
    target = Path(sys.argv[2])

    if not svg.exists():
        print(f"Error: SVG not found: {svg}")
        sys.exit(1)

    generate(svg, target)


if __name__ == "__main__":
    main()