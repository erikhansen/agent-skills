---
name: openai-image-styles
description: Restyle photos into art styles (Rembrandt, Renaissance, Sargent Gilded Age, Victorian tintype, Norman Rockwell, caricature, and 25+ more), generate or edit images with OpenAI's image models (gpt-image-2.5-sunburst), keep real people's faces recognizable, and publish the results as a swipeable Artifact gallery. Use whenever the user wants a photo "in different art styles", a family/team/class photo turned into paintings or cartoons, caricatures of a photo, image generation or editing with OpenAI / ChatGPT images / gpt-image, or a gallery of image variations. Includes secure API-key onboarding (macOS Keychain) and per-run OpenAI cost reporting.
---

# OpenAI image styles

Turn photos into art-style variations with OpenAI's Images API and publish them as a swipeable gallery.
Everything lives in this skill folder (`SKILL_DIR` below = the directory containing this file):

| File | Purpose |
|---|---|
| `scripts/setup_key.sh` | One-time key onboarding. **The user runs it in their own terminal.** |
| `scripts/imagegen.py` | `generate`, `edit`, `styles` (batch restyle), `cost`, `check-key`. Stdlib only. |
| `scripts/make_prompts.py` | Builds a `{slug: prompt}` JSON from the style library + scene description. |
| `scripts/crop_tiles.py` | Crops face close-ups / face-row tiles from full-res originals (macOS `sips`). |
| `scripts/build_gallery.py` | Builds `index.html` + `img/` for the Artifact gallery. |
| `references/styles.json` | 33 tested style prompts, the **default set**, display names, and the likeness/modesty clauses. |

## Step 0 — API key onboarding (always first)

Run `python3 SKILL_DIR/scripts/imagegen.py check-key`.

- **Prints `OK: key ending ...xxxx`** → continue.
- **Says no key found** → stop and onboard the user. Tell them, in these words or close:
  > I need an OpenAI API key, but please **don't paste it into this chat**: chat transcripts are stored, so a pasted key should be treated as leaked. Open a separate terminal window and run:
  > `~/.claude/skills/openai-image-styles/scripts/setup_key.sh`
  > It saves the key to your macOS Keychain with hidden input (on Linux, to a `chmod 600` file in `~/.config/openai-image-styles/`). Tell me when it's done.

  Then re-run `check-key`. Don't try to run `setup_key.sh` yourself: it needs an interactive terminal, and running it through Claude would route the key through the session.
- **If the user pastes a key into chat anyway**: do not use it or write it anywhere. Tell them to revoke it at https://platform.openai.com/api-keys, create a new one, and run `setup_key.sh`.
- Optional: `setup_key.sh --admin` stores an admin key (`api.usage.read`) so `imagegen.py cost` can show exact billed spend.
- Never print, echo, `cat`, or log the key. `imagegen.py` reads it from env → Keychain → 600-mode file on its own.

## Step 1 — Look at the photos

- Copy originals into a working folder (e.g. `input/`). Check sizes with `sips -g pixelWidth -g pixelHeight`.
- Make ~1200px-wide previews in the scratchpad and **view every one**. Note who is in it (count, rough ages, poses, notable features like glasses or braids) and the setting. This becomes the `--scene` text.
- Name files explicitly (`p1.jpg`, `p2.jpg`, ...) and keep a written mapping. Python's `sorted()` and zsh globbing order names differently (`2024 ...` vs `2_...`), which once swapped two photos' crops.

## Step 2 — Face references (this is what keeps people recognizable)

Without close-ups the model draws generic faces. Pick boxes on the 1200px preview and crop from the **full-resolution original**:

- **≤ 5 people**: one close-up per face (~head and shoulders), e.g. `crop_tiles.py photo.jpg input/faces/p1 --box x0,y0,x1,y1 --box ...`
- **Larger groups**: 1–3 overlapping tiles covering the rows of faces.
- **View every crop** before using it. Boxes are often off on the first try; re-crop as needed.

## Step 3 — Prompts

**Default set** (used when the user doesn't name styles): Rembrandt, Renaissance Oil, Sargent Gilded Age, Victorian Tintype, Norman Rockwell, Caricature: Medium, Caricature: Extreme. The first four are period-costume "dress everybody up" styles.
Van Gogh, Van Gogh Pixel Art, Pixel Art, Manga Ink and Claymation are deliberately **not** in the default set. They stay in the library, but use them only when someone asks for them by name.

```bash
python3 SKILL_DIR/scripts/make_prompts.py --list          # * marks the default set
python3 SKILL_DIR/scripts/make_prompts.py work/p1-styles.json \
  --scene "a family of four: mother, father and two young children, sitting in tall grass at sunset"
# specific styles instead:           --style rembrandt --style watercolor
# default set plus extras:           --defaults --style stained-glass
```

Lessons baked into the clauses (keep them if you write custom prompts with `--custom "slug=..."`):
- Present close-ups as **"likeness reference only"** and require faces **rendered fully in the art style**. Saying "never change facial structure" made faces look pasted-on and photographic.
- Period-costume styles (`rembrandt`, `renaissance-oil`, `sargent-gilded-age`, `victorian-tintype`) automatically get a modesty clause: high necklines, no cleavage.
- Costume prompts must demand **variety**: a different outfit per person, with men's and women's dress clearly distinct and concrete garments listed for each. A generic "17th-century costume" prompt made every man in the Rembrandt versions wear the same gown-like outfit as the women. The `rembrandt` prompt now spells out Night Watch-style menswear (ruffs, sashes, jerkins, gorgets, plumed hats) separately from womenswear.
- Name every person, their pose and expression in `--scene`. For extreme styles (caricature), the scene text plus close-ups keep each person identifiable.

## Step 4 — Generate

```bash
python3 SKILL_DIR/scripts/imagegen.py styles input/p1.jpg work/p1-styles.json \
  -r input/faces/p1-t1.jpg -r input/faces/p1-t2.jpg \
  -o output/p1 --size auto --quality high -j 3
```

- `--size auto` keeps the photo's aspect ratio. A forced 1024x1536 frame on a 3:4 or 3:2 photo squeezes faces.
- Several photos: run one `styles` process per photo in parallel from **bash** (`bash -c '...'`). zsh doesn't word-split `$R`, so building `-r` lists in a variable breaks there.
- Cost: about $0.05–0.08 per high-quality image with refs on gpt-image-2.5-sunburst. 50+ images is a few dollars; mention the estimate before large batches.
- `gpt-image-2.5-*` rejects `--input-fidelity`. An A/B test with `--model gpt-image-1.5 --input-fidelity high` dropped a person from the scene and cost about 5× as much. Stay on the default.
- An occasional `rejected by the safety system` 400 on harmless family photos is usually a false positive: retry that one style once (build a one-entry JSON). If it fails again, report it and move on.
- Other commands: `generate "prompt" -n 3 -o out/name` (text to image), `edit "prompt" -i ref.png [-i ref2.png] [--mask mask.png]` (masked edits redraw only the transparent area; good for changing one face while keeping the rest).

## Step 5 — Check before publishing

View a sample from each photo: a period-costume style, a caricature and one stylized style. Check that everyone is present, faces are recognizable **and** rendered in the style, and costumes are modest. If faces fail, adjust the crops or scene text and regenerate only those styles.

## Step 6 — Gallery Artifact

```bash
python3 SKILL_DIR/scripts/build_gallery.py work/site --title "Family Portrait Styles" \
  --photo "Family of four|input/p1.jpg|output/p1" --photo "Volleyball team|input/p2.jpg|output/p2"
```

Publish it with `capabilities: {downloads: true}`. That powers the **Download all** button, which zips every image for the photo being viewed and offers it through the viewer's save prompt. The button stays hidden in views where downloads aren't available, and keep the capability on redeploys. The gallery is always dark (gallery-wall black, in both light and dark viewer themes) so the artwork pops. Keep it that way when customizing the template. Then publish `work/site/index.html` with the Artifact tool, using `root=work/site` and `files` = every `img/*.jpg`. Follow the Artifact tool's own rules for new artifacts, such as quickstart first. The viewer has a photo picker, swipe/arrow navigation, a filmstrip, hold-to-compare with the original, a slideshow, click-to-fullscreen zoom (Esc or click to exit; full-window fallback on phones) and Download all (.zip per photo). Images always show in full (`object-fit: contain`), never cropped. To update it later, publish the same file path again. New artifacts are private; tell the user to use the Share menu if they want family to see it. Photos of other people's children (class or team photos) are a reason to suggest keeping the gallery private.

## Step 7 — Always report cost

End every generation run with the running total: `python3 SKILL_DIR/scripts/imagegen.py cost`. Every call appends token usage and an estimated USD cost to `~/.config/openai-image-styles/usage-ledger.jsonl`. It's an estimate unless an admin key is stored.
