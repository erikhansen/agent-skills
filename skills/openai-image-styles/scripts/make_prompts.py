#!/usr/bin/env python3
"""Build a {slug: prompt} JSON for `imagegen.py styles` from the skill's style library.

  make_prompts.py out.json --scene "a family of four sitting in tall grass at sunset"            # default set
  make_prompts.py out.json --scene "..." --style rembrandt --style watercolor [--no-refs] [--extra "..."]
  make_prompts.py out.json --scene "..." --defaults --style watercolor                     # defaults + extras

With no --style/--custom, the default set from references/styles.json is used.

Slugs are numbered in the order given (01-rembrandt, 02-van-gogh, ...) so galleries keep that order.
Period-costume styles (rembrandt, renaissance-oil, sargent-gilded-age, victorian-tintype) automatically get the modesty clause.
Use --list to print the available styles.
"""
import argparse
import json
from pathlib import Path

LIB = Path(__file__).resolve().parent.parent / "references" / "styles.json"


def main():
    lib = json.loads(LIB.read_text())
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("out", nargs="?")
    p.add_argument("--scene", help="one-sentence description of who is in the photo and where")
    p.add_argument("--style", action="append", default=[])
    p.add_argument("--defaults", action="store_true", help="include the default style set (implied when no --style/--custom)")
    p.add_argument("--custom", action="append", default=[], help='custom style as "slug=prompt"')
    p.add_argument("--no-refs", action="store_true", help="no face close-ups will be passed with -r")
    p.add_argument("--extra", default="", help="extra instruction appended to every prompt")
    p.add_argument("--list", action="store_true")
    args = p.parse_args()

    if args.list:
        for slug, (name, note) in lib["display"].items():
            print(f"{'*' if slug in lib['defaults'] else ' '} {slug:22} {name} ({note})")
        print("\n* = default set")
        return
    if not (args.out and args.scene):
        p.error("out and --scene are required")
    if args.defaults or not (args.style or args.custom):
        args.style = lib["defaults"] + [s for s in args.style if s not in lib["defaults"]]

    c = lib["_clauses"]
    likeness = c["likeness_no_refs"] if args.no_refs else c["likeness"]
    styles = [(s, lib["styles"][s]) for s in args.style]
    styles += [tuple(x.split("=", 1)) for x in args.custom]
    out = {}
    for i, (slug, text) in enumerate(styles, 1):
        parts = [text]
        if slug in c["costume_styles"]:
            parts.append(c["modest"])
        parts += [likeness, c["composition"].format(scene=args.scene.rstrip("."))]
        if args.extra:
            parts.append(args.extra)
        out[f"{i:02d}-{slug}"] = " ".join(parts)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=2))
    print(f"wrote {len(out)} prompts to {args.out}")


if __name__ == "__main__":
    main()
