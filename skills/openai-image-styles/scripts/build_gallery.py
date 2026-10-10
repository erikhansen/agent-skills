#!/usr/bin/env python3
"""Build a swipeable style-gallery site (index.html + img/) ready to publish as an Artifact.

  build_gallery.py OUT_DIR --title "Family Portrait Styles" \
      --photo "Smith family, 2024|input/family.jpg|output/family" \
      --photo "Volleyball team|input/team.jpg|output/team"

Each --photo is "Label|original image|folder of generated PNGs". Generated files named
NN-slug-1.png (as imagegen.py styles writes them) are picked up in name order, and display
names come from references/styles.json (unknown slugs are title-cased). Images are converted
to JPEG (long edge 1400) with macOS `sips` so the published gallery stays small.
Publish OUT_DIR/index.html with the Artifact tool, root=OUT_DIR, files=every img/*.jpg.
"""
import argparse
import json
import re
import subprocess
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent


def to_jpeg(src, dst, size):
    subprocess.run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", "80", "-Z", str(size), str(src),
                    "--out", str(dst)], check=True, capture_output=True)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("out_dir")
    p.add_argument("--title", required=True)
    p.add_argument("--eyebrow", default="")
    p.add_argument("--photo", action="append", required=True, help="Label|original|generated_dir")
    p.add_argument("--size", type=int, default=1400)
    args = p.parse_args()

    display = json.loads((SKILL / "references" / "styles.json").read_text())["display"]
    out = Path(args.out_dir)
    (out / "img").mkdir(parents=True, exist_ok=True)
    photos, total = [], 0
    for n, spec in enumerate(args.photo, 1):
        label, original, gen_dir = spec.split("|")
        pid = f"p{n}"
        to_jpeg(original, out / "img" / f"{pid}-00-original.jpg", args.size)
        styles = [["00-original", "Original", "the photo"]]
        for png in sorted(Path(gen_dir).glob("*-1.png")):
            slug = png.name[:-len("-1.png")]
            key = re.sub(r"^\d+-", "", slug)
            name, note = display.get(key, [key.replace("-", " ").title(), ""])
            to_jpeg(png, out / "img" / f"{pid}-{slug}.jpg", args.size)
            styles.append([slug, name, note])
            total += 1
        photos.append({"id": pid, "label": label, "styles": styles})

    eyebrow = args.eyebrow or f"{len(photos)} photo{'s' if len(photos) > 1 else ''} · {total} styled images"
    data = {"title": args.title, "eyebrow": eyebrow, "photos": photos}
    html = (SKILL / "assets" / "gallery-template.html").read_text()
    html = html.replace("__TITLE__", args.title).replace("__DATA__", json.dumps(data))
    (out / "index.html").write_text(html)
    print(f"{out / 'index.html'}  ({total} styled images, {len(photos)} photos)")


if __name__ == "__main__":
    main()
