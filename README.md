# Rectangles-of-Regret

A tiny tool that turns your images into an animated 16:9 matrix of rotating rectangles in SVG.
Because nothing says “art” like 3,600 little bars spinning in synchronized misery.

## What it does

- Samples each input image into a grid (default 80×45, roughly 16:9).
- Each sample becomes a white rectangle bar inside a spaced cell.
- Dark → thin + vertical, Light → thick + horizontal.
- Animates between images using a synchronized sweep:
  - During the transition, all moving pixels share the same angle at any instant.
  - Pixels start when the sweep reaches their start angle, and stop when it reaches the target angle.
- Rotation is clockwise-only, and each transition can be forced to do at least N full rotations.

Output is a single `out.svg` that loops forever.

## Preview

If you commit `out.svg` to the repo root, this should show a preview:

![out.svg preview](out.svg)

### GitHub reality check

GitHub often renders SVGs in README as static previews. SMIL animation support in GitHub’s renderer is inconsistent.
If it looks frozen, that’s GitHub being GitHub. Open `out.svg` locally in a browser to see the animation.

## Requirements

- Python 3.x
- Pillow
- numpy

## Install dependencies

Windows / PC:

```bash
py -m pip install pillow numpy
```

macOS / Linux:

```bash
python3 -m pip install pillow numpy
```

## Usage

Generator script:
`animated_rect_matrix_generator_v5_syncsweep_minrot_timing.py`

### Windows / PC (Python)

```bash
py animated_rect_matrix_generator_v5_syncsweep_minrot_timing.py out.svg img1.jpg img2.jpg img3.png
```

### macOS / Linux (python3)

```bash
python3 animated_rect_matrix_generator_v5_syncsweep_minrot_timing.py out.svg img1.jpg img2.jpg img3.png
```

## Common settings

- `--transition_s`  
  Seconds spent rotating/morphing between images (default: 2.0)

- `--hold_s`  
  Seconds resting on each image (default: 2.0)

- `--min_full_rotations`  
  Minimum full clockwise rotations per transition (default: 1)

Example (faster transitions, longer rest, extra spin):

```bash
python3 animated_rect_matrix_generator_v5_syncsweep_minrot_timing.py out.svg a.jpg b.jpg c.jpg \
  --transition_s 1.2 --hold_s 3.0 --min_full_rotations 2
```

Other knobs (for people who enjoy tweaking endlessly):

- `--cols`, `--rows` (default: 80 45)
- `--render_w`, `--render_h` (default: 1280 720)
- `--gap_ratio` (default: 0.5)
- `--gamma` (default: 1.15)
- `--fill` (default: white)

## Viewing locally

If your SVG doesn’t animate in your viewer, open it in a modern browser.

You can also serve the folder locally:

```bash
python3 -m http.server 8000
```

Then open:
`http://localhost:8000/out.svg`

## Output

- `out.svg` (transparent background, white bars)

If you want a black background inside the SVG, add a black `<rect>` behind everything.
Or just use HTML/CSS like a civilized person.

## License

Do whatever you want. If it breaks, you keep both pieces.
