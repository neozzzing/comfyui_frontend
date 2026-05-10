#!/usr/bin/env python3
"""
PNG Metadata Parser - Extract ComfyUI workflow metadata from PNG files
"""

import json
import sys
from PIL import Image


def parse_png_metadata(filepath):
    """Parse and display all metadata from a ComfyUI-generated PNG file."""
    img = Image.open(filepath)

    if not hasattr(img, 'text') or not img.text:
        print(f"No text metadata found in {filepath}")
        return

    print(f"=== Metadata from: {filepath} ===\n")

    for key, value in img.text.items():
        print(f"--- {key} ---")
        try:
            data = json.loads(value)
            print(json.dumps(data, indent=2))
        except (json.JSONDecodeError, TypeError):
            print(value)
        print()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python png_metadata.py <image.png> [image2.png ...]")
        sys.exit(1)

    for path in sys.argv[1:]:
        parse_png_metadata(path)
