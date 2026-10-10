#!/usr/bin/env python3
"""OpenAI image generation / editing CLI (stdlib only).

The API key is never read from chat or a project file. Lookup order:
  1. OPENAI_API_KEY environment variable (e.g. injected by a secrets manager)
  2. macOS Keychain item, service "openai-image-styles", account "api-key"
  3. ~/.config/openai-image-styles/api_key (must be chmod 600)
Store it with scripts/setup_key.sh, run in your own terminal.
OPENAI_IMAGE_MODEL overrides the default model (gpt-image-2.5-sunburst).

Examples:
  # Generate 3 variations from a prompt
  ./imagegen.py generate "a lighthouse at dusk, oil painting" -n 3 -o output/lighthouse

  # Edit / restyle using one or more reference photos
  ./imagegen.py edit "Redraw this as a watercolor" -i input/photo.png -n 2 -o output/photo-watercolor

  # Batch restyle one image into many styles (JSON file: {"slug": "prompt", ...})
  ./imagegen.py styles input/photo.png styles.json -o output/styles -j 4
"""
import argparse
import base64
import json
import mimetypes
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent
API_BASE = "https://api.openai.com/v1"
CONFIG_DIR = Path(os.environ.get("OPENAI_IMAGE_STYLES_HOME", Path.home() / ".config" / "openai-image-styles"))
LEDGER = CONFIG_DIR / "usage-ledger.jsonl"
KEYCHAIN_SERVICE = "openai-image-styles"
DEFAULT_MODEL = "gpt-image-2.5-sunburst"
_ledger_lock = threading.Lock()

# USD per 1M tokens, from https://developers.openai.com/api/docs/models/gpt-image-2.5-sunburst
# (text input, image input, image output). Used only for local estimates.
PRICES = {"default": (5.00, 8.00, 30.00)}


def _secret(account, env_var):
    """Return a secret from env, macOS Keychain, or a 600-mode file; never prints it."""
    if os.environ.get(env_var):
        return os.environ[env_var]
    if sys.platform == "darwin":
        r = subprocess.run(["security", "find-generic-password", "-s", KEYCHAIN_SERVICE, "-a", account, "-w"],
                           capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    f = CONFIG_DIR / account.replace("-", "_")
    if f.exists():
        if f.stat().st_mode & 0o077:
            sys.exit(f"{f} is readable by other users; run: chmod 600 {f}")
        return f.read_text().strip()
    return None


def load_env():
    key = _secret("api-key", "OPENAI_API_KEY")
    if not key:
        sys.exit("No OpenAI API key found. Run the onboarding in your own terminal (not in chat):\n"
                 f"  {ROOT / 'setup_key.sh'}")
    os.environ["OPENAI_API_KEY"] = key
    admin = _secret("admin-key", "OPENAI_ADMIN_KEY")
    if admin:
        os.environ["OPENAI_ADMIN_KEY"] = admin
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def check_key(model):
    """Confirm the stored key works and can see the model, without revealing it."""
    key = os.environ["OPENAI_API_KEY"]
    req = urllib.request.Request(f"{API_BASE}/models/{model}", headers={"Authorization": f"Bearer {key}"})
    try:
        with urllib.request.urlopen(req, timeout=30):
            pass
        print(f"OK: key ending ...{key[-4:]} can use {model}")
    except urllib.error.HTTPError as e:
        sys.exit(f"Key check failed for {model}: HTTP {e.code} {e.read().decode(errors='replace')[:300]}")


def _request(url, body, content_type, retries=3):
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}",
        "Content-Type": content_type,
    })
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=600) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")
            if e.code in (429, 500, 502, 503) and attempt < retries - 1:
                time.sleep(5 * (attempt + 1))
                continue
            raise RuntimeError(f"HTTP {e.code}: {detail}") from None


def _multipart(fields, files):
    boundary = uuid.uuid4().hex
    parts = []
    for name, value in fields.items():
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
    for name, path in files:
        mime = mimetypes.guess_type(path)[0] or "application/octet-stream"
        parts.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; filename="{Path(path).name}"\r\n'
            f"Content-Type: {mime}\r\n\r\n".encode() + Path(path).read_bytes() + b"\r\n"
        )
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def _save(result, out_prefix):
    out_prefix = Path(out_prefix)
    out_prefix.parent.mkdir(parents=True, exist_ok=True)
    paths = []
    for i, item in enumerate(result.get("data", []), 1):
        path = out_prefix.with_name(f"{out_prefix.name}-{i}.png")
        if item.get("b64_json"):
            path.write_bytes(base64.b64decode(item["b64_json"]))
        elif item.get("url"):
            urllib.request.urlretrieve(item["url"], path)
        paths.append(path)
        print(f"saved {path}")
    return paths


def _record(usage, kind, prompt, model):
    """Append token usage + estimated USD cost to the ledger and return the cost."""
    usage = usage or {}
    details = usage.get("input_tokens_details") or {}
    text_in = details.get("text_tokens", usage.get("input_tokens", 0) if not details else 0)
    image_in = details.get("image_tokens", 0)
    out = usage.get("output_tokens", 0)
    p_text, p_img, p_out = PRICES.get(model, PRICES["default"])
    cost = (text_in * p_text + image_in * p_img + out * p_out) / 1_000_000
    entry = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "kind": kind, "model": model,
             "prompt": prompt[:120], "usage": usage, "est_usd": round(cost, 4)}
    with _ledger_lock:
        with LEDGER.open("a") as f:
            f.write(json.dumps(entry) + "\n")
    print(f"est. cost ${cost:.4f} ({text_in} text in, {image_in} image in, {out} out tokens)")
    return cost


def ledger_total():
    if not LEDGER.exists():
        return 0.0, 0
    rows = [json.loads(l) for l in LEDGER.read_text().splitlines() if l.strip()]
    return sum(r["est_usd"] for r in rows), len(rows)


def billed_costs(days=30):
    """Actual OpenAI spend via the org Costs API; needs OPENAI_ADMIN_KEY (api.usage.read)."""
    key = os.environ.get("OPENAI_ADMIN_KEY")
    if not key:
        return None
    start = int(time.time()) - days * 86400
    total, page = 0.0, None
    while True:
        url = f"{API_BASE}/organization/costs?start_time={start}&limit=180" + (f"&page={page}" if page else "")
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {key}"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
        for bucket in data.get("data", []):
            for r in bucket.get("results", []):
                total += float(r.get("amount", {}).get("value", 0))
        if not data.get("has_more"):
            return total
        page = data.get("next_page")


def print_cost_summary():
    est, calls = ledger_total()
    print(f"\nLedger total: ${est:.2f} estimated across {calls} logged API calls ({LEDGER.name})")
    try:
        billed = billed_costs()
    except Exception as exc:
        billed = None
        print(f"Billed cost lookup failed: {exc}")
    if billed is not None:
        print(f"OpenAI billed cost, last 30 days (whole org, all models): ${billed:.2f}")
    else:
        print("Exact billed cost: store an admin key with api.usage.read via setup_key.sh --admin to enable.")


def _opts(args):
    opts = {"model": args.model or os.environ.get("OPENAI_IMAGE_MODEL", DEFAULT_MODEL), "n": args.n}
    for key in ("size", "quality", "background"):
        if getattr(args, key, None):
            opts[key] = getattr(args, key)
    return opts


def generate(prompt, args, out_prefix):
    body = {"prompt": prompt, **_opts(args), "output_format": "png"}
    result = _request(f"{API_BASE}/images/generations", json.dumps(body).encode(), "application/json")
    _record(result.get("usage"), "generate", prompt, body["model"])
    return _save(result, out_prefix)


def edit(prompt, images, args, out_prefix, mask=None):
    fields = {"prompt": prompt, **_opts(args)}
    if getattr(args, "input_fidelity", None):
        fields["input_fidelity"] = args.input_fidelity
    files = [("image[]", p) for p in images]
    if mask:
        files.append(("mask", mask))
    body, ctype = _multipart(fields, files)
    result = _request(f"{API_BASE}/images/edits", body, ctype)
    _record(result.get("usage"), "edit", prompt, fields["model"])
    return _save(result, out_prefix)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp):
        sp.add_argument("--model", help="override OPENAI_IMAGE_MODEL for this run")
        sp.add_argument("-n", type=int, default=1, help="number of variations")
        sp.add_argument("-o", "--out", default="output/image", help="output path prefix (or dir for styles)")
        sp.add_argument("--size", help="e.g. 1024x1024, 1024x1536, 1536x1024, auto")
        sp.add_argument("--quality", help="low | medium | high | auto")
        sp.add_argument("--background", help="transparent | opaque | auto")

    g = sub.add_parser("generate", help="text-to-image")
    g.add_argument("prompt")
    common(g)

    e = sub.add_parser("edit", help="edit/restyle using reference image(s)")
    e.add_argument("prompt")
    e.add_argument("-i", "--image", action="append", required=True, help="reference image (repeatable)")
    e.add_argument("--mask", help="optional PNG mask (transparent = area to edit)")
    e.add_argument("--input-fidelity", help="low | high")
    common(e)

    s = sub.add_parser("styles", help="restyle one image into many styles from a JSON file")
    s.add_argument("image")
    s.add_argument("styles_json", help='{"slug": "prompt", ...}')
    s.add_argument("-r", "--ref", action="append", default=[], help="extra reference image (repeatable), e.g. face close-ups")
    s.add_argument("-j", "--jobs", type=int, default=4, help="parallel requests")
    s.add_argument("--input-fidelity", help="low | high")
    common(s)

    sub.add_parser("cost", help="show estimated ledger total and (with admin key) billed cost")
    ck = sub.add_parser("check-key", help="verify the stored API key works (never prints it)")
    ck.add_argument("--model", help="model to check access to")

    args = p.parse_args()
    load_env()

    if args.cmd == "check-key":
        check_key(args.model or os.environ.get("OPENAI_IMAGE_MODEL", DEFAULT_MODEL))
    elif args.cmd == "cost":
        print_cost_summary()
    elif args.cmd == "generate":
        generate(args.prompt, args, args.out)
        print_cost_summary()
    elif args.cmd == "edit":
        edit(args.prompt, args.image, args, args.out, args.mask)
        print_cost_summary()
    else:
        styles = json.loads(Path(args.styles_json).read_text())
        out_dir = Path(args.out)
        failures = 0
        with ThreadPoolExecutor(max_workers=args.jobs) as pool:
            futures = {pool.submit(edit, prompt, [args.image, *args.ref], args, out_dir / slug): slug
                       for slug, prompt in styles.items()}
            for f in as_completed(futures):
                try:
                    f.result()
                except Exception as exc:
                    failures += 1
                    print(f"FAILED {futures[f]}: {exc}", file=sys.stderr)
        print_cost_summary()
        sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
