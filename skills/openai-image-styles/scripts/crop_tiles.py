#!/usr/bin/env python3
"""Crop face / face-row reference tiles from a full-resolution photo (macOS `sips`).

Boxes are given in the coordinates of a preview image of width --ref-width (default 1200),
so you can pick them by eye from a downsized preview and still crop from the full-size original.

  crop_tiles.py photo.jpg out/prefix --box 100,160,500,430 --box 480,160,900,430
  -> out/prefix-t1.jpg, out/prefix-t2.jpg (long edge capped at --max 1400)
"""
import argparse
import subprocess
from pathlib import Path


def width(path):
    out = subprocess.check_output(["sips", "-g", "pixelWidth", str(path)], text=True)
    return int(out.split()[-1])


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("photo")
    p.add_argument("out_prefix")
    p.add_argument("--box", action="append", required=True, help="x0,y0,x1,y1 in preview coordinates")
    p.add_argument("--ref-width", type=int, default=1200)
    p.add_argument("--max", type=int, default=1400)
    args = p.parse_args()

    k = width(args.photo) / args.ref_width
    prefix = Path(args.out_prefix)
    prefix.parent.mkdir(parents=True, exist_ok=True)
    for i, box in enumerate(args.box, 1):
        x0, y0, x1, y1 = (int(v) for v in box.split(","))
        out = prefix.with_name(f"{prefix.name}-t{i}.jpg")
        subprocess.run(["sips", "-s", "format", "jpeg", "-c", str(int((y1 - y0) * k)), str(int((x1 - x0) * k)),
                        "--cropOffset", str(int(y0 * k)), str(int(x0 * k)), args.photo, "--out", str(out)],
                       check=True, capture_output=True)
        subprocess.run(["sips", "-Z", str(args.max), str(out)], check=True, capture_output=True)
        print(out)


if __name__ == "__main__":
    main()
