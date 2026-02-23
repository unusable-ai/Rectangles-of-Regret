#!/usr/bin/env python3
"""
Animated rectangle-matrix SVG generator (v5: synchronized sweep + minimum full rotations + configurable timing).

Option C ("synchronized sweep"):
- During each transition, there is a single global sweep angle.
- Pixels start moving when sweep reaches their start angle.
- Pixels stop when sweep reaches their end angle.
- All moving pixels share the exact same angle at any instant.

Clockwise-only + minimum rotations:
- Clockwise-only enforced by unwrapping angles upward using +180° steps (rectangles are 180° symmetric).
- Additionally, each pixel's rotation between frames is forced to be at least:
    min_full_rotations * 360°
  by adding +360° multiples to the target angle as needed.

Timing:
- transition_s: seconds spent sweeping/rotating between images
- hold_s: seconds holding the final state for that image
- loops forever

Mapping:
- dark -> thin + vertical
- light -> thick + horizontal
(angle and thickness increase with brightness)

Dependencies:
  pip install pillow numpy

Usage:
  python animated_rect_matrix_generator_v5_syncsweep_minrot_timing.py out.svg img1.jpg img2.jpg img3.png

Example:
  python animated_rect_matrix_generator_v5_syncsweep_minrot_timing.py out.svg a.jpg b.jpg --transition_s 1.5 --hold_s 2.5 --min_full_rotations 2
"""

import argparse
from pathlib import Path

import numpy as np
from PIL import Image


def center_crop_to_aspect(img: Image.Image, aspect: float) -> Image.Image:
    W, H = img.size
    cur = W / H
    if cur > aspect:
        new_W = int(H * aspect)
        left = (W - new_W) // 2
        return img.crop((left, 0, left + new_W, H))
    else:
        new_H = int(W / aspect)
        top = (H - new_H) // 2
        return img.crop((0, top, W, top + new_H))


def img_to_brightness(img: Image.Image, cols: int, rows: int, gamma: float) -> np.ndarray:
    g = img.convert("L").resize((cols, rows), Image.Resampling.LANCZOS)
    arr = np.asarray(g, dtype=np.float32) / 255.0  # 1=white
    if gamma != 1.0:
        arr = np.clip(arr, 0, 1) ** gamma
    return arr


def segment_keypoints(
    seg_start: float,
    transition_s: float,
    hold_s: float,
    a0: float,
    a1: float,
    th0: float,
    th1: float,
    phi_min: float,
    phi_max: float,
):
    """
    Keypoints for one segment (transition + hold), absolute seconds:
      (t, angle, thickness)

    Sweep during transition:
      phi(t) = phi_min + (phi_max-phi_min) * ((t-seg_start)/transition_s)
    Pixel holds a0 until phi==a0, then follows phi until phi==a1, then holds.
    Thickness morphs only while moving (join..leave), otherwise holds.
    """
    trans_start = seg_start
    trans_end = seg_start + transition_s
    seg_end = trans_end + hold_s

    denom = (phi_max - phi_min)
    if transition_s <= 0 or abs(denom) < 1e-9:
        join = trans_start
        leave = trans_start
    else:
        join = trans_start + transition_s * ((a0 - phi_min) / denom)
        leave = trans_start + transition_s * ((a1 - phi_min) / denom)
        join = max(trans_start, min(trans_end, join))
        leave = max(trans_start, min(trans_end, leave))

    pts = [
        (trans_start, a0, th0),
        (join,        a0, th0),
        (leave,       a1, th1),
        (trans_end,   a1, th1),
        (seg_end,     a1, th1),
    ]

    # squash identical timestamps
    cleaned = []
    for t, a, th in pts:
        if cleaned and abs(t - cleaned[-1][0]) < 1e-9:
            cleaned[-1] = (t, a, th)
        else:
            cleaned.append((t, a, th))
    return cleaned


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("output_svg")
    ap.add_argument("images", nargs="+")
    ap.add_argument("--cols", type=int, default=80)
    ap.add_argument("--rows", type=int, default=45)
    ap.add_argument("--cell", type=float, default=1.0)
    ap.add_argument("--gap_ratio", type=float, default=0.5)
    ap.add_argument("--bar_len_ratio", type=float, default=0.90)
    ap.add_argument("--min_th", type=float, default=0.06)
    ap.add_argument("--max_th", type=float, default=0.95)
    ap.add_argument("--gamma", type=float, default=1.15)
    ap.add_argument("--render_w", type=int, default=1280)
    ap.add_argument("--render_h", type=int, default=720)
    ap.add_argument("--fill", type=str, default="white")

    ap.add_argument("--transition_s", type=float, default=2.0, help="Seconds spent rotating/morphing between images.")
    ap.add_argument("--hold_s", type=float, default=2.0, help="Seconds holding each image state after the transition.")

    ap.add_argument("--min_full_rotations", type=int, default=1,
                    help="Minimum full 360° rotations per transition (clockwise). Default 1.")
    args = ap.parse_args()

    if args.transition_s < 0 or args.hold_s < 0:
        raise SystemExit("transition_s and hold_s must be >= 0")

    cols, rows = args.cols, args.rows
    cell = args.cell
    gap = args.gap_ratio * cell
    pitch = cell + gap

    vb_w = cols * pitch - gap
    vb_h = rows * pitch - gap
    target_aspect = vb_w / vb_h

    bar_len = args.bar_len_ratio * cell
    min_th = args.min_th * cell
    max_th = args.max_th * cell

    frames_b = []
    for p in args.images:
        img = Image.open(p).convert("RGB")
        crop = center_crop_to_aspect(img, target_aspect)
        frames_b.append(img_to_brightness(crop, cols, rows, gamma=args.gamma))

    N = len(frames_b)
    seg_len = args.transition_s + args.hold_s
    total_dur = seg_len * N if N > 0 else 0.0

    angles_base = [b * 90.0 for b in frames_b]                    # degrees
    th_base = [min_th + b * (max_th - min_th) for b in frames_b]  # units

    # Build realized frame angles sequentially so boundaries match (no jumps).
    min_delta = 360.0 * float(max(0, args.min_full_rotations))
    angles_real = [angles_base[0].copy()]

    for i in range(1, N):
        prev = angles_real[i - 1]
        tgt = angles_base[i].copy()

        # clockwise-only (+180° where needed)
        while True:
            mask = tgt < prev
            if not mask.any():
                break
            tgt[mask] += 180.0

        # minimum rotations (+360° multiples)
        if min_delta > 0:
            need = (prev + min_delta) - tgt
            mask = need > 0
            if mask.any():
                tgt[mask] += 360.0 * np.ceil(need[mask] / 360.0)

        angles_real.append(tgt)

    # Loop-back target (frame0) adjusted relative to last realized frame
    prev = angles_real[-1]
    loop_tgt = angles_base[0].copy()

    while True:
        mask = loop_tgt < prev
        if not mask.any():
            break
        loop_tgt[mask] += 180.0

    if min_delta > 0:
        need = (prev + min_delta) - loop_tgt
        mask = need > 0
        if mask.any():
            loop_tgt[mask] += 360.0 * np.ceil(need[mask] / 360.0)

    # Segment sweep bounds
    seg_phi = []
    for i in range(N):
        a0 = angles_real[i]
        a1 = angles_real[i + 1] if i < N - 1 else loop_tgt
        seg_phi.append((float(a0.min()), float(a1.max())))

    svg = []
    svg.append('<?xml version="1.0" encoding="UTF-8"?>')
    svg.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{args.render_w}" height="{args.render_h}" '
        f'viewBox="0 0 {vb_w:.4f} {vb_h:.4f}">'
    )
    svg.append(f'<g fill="{args.fill}">')

    for y in range(rows):
        for x in range(cols):
            cx = x * pitch + cell / 2.0
            cy = y * pitch + cell / 2.0
            ry = cy - bar_len / 2.0

            pts_all = []
            for i in range(N):
                seg_start = seg_len * i
                a0 = float(angles_real[i][y, x])
                th0 = float(th_base[i][y, x])

                if i < N - 1:
                    a1 = float(angles_real[i + 1][y, x])
                    th1 = float(th_base[i + 1][y, x])
                else:
                    a1 = float(loop_tgt[y, x])
                    th1 = float(th_base[0][y, x])

                phi_min, phi_max = seg_phi[i]
                seg_pts = segment_keypoints(
                    seg_start,
                    args.transition_s,
                    args.hold_s,
                    a0,
                    a1,
                    th0,
                    th1,
                    phi_min,
                    phi_max,
                )

                if i == 0:
                    pts_all.extend(seg_pts)
                else:
                    pts_all.extend(seg_pts[1:])

            times = [t for (t, _, _) in pts_all]
            keyTimes = [t / total_dur for t in times] if total_dur > 0 else [0.0 for _ in times]
            kt = ";".join([f"{k:.6f}" for k in keyTimes])

            rot_vals = ";".join([f"{a:.4f} {cx:.4f} {cy:.4f}" for (_, a, _) in pts_all])
            w_vals = ";".join([f"{th:.4f}" for (_, _, th) in pts_all])
            x_vals = ";".join([f"{(cx - th/2.0):.4f}" for (_, _, th) in pts_all])

            init_a = pts_all[0][1]
            init_th = pts_all[0][2]
            init_x = cx - init_th / 2.0

            svg.append(
                f'<rect x="{init_x:.4f}" y="{ry:.4f}" width="{init_th:.4f}" height="{bar_len:.4f}" '
                f'transform="rotate({init_a:.4f} {cx:.4f} {cy:.4f})">'
            )
            svg.append(
                f'  <animateTransform attributeName="transform" type="rotate" dur="{total_dur}s" repeatCount="indefinite" '
                f'values="{rot_vals}" keyTimes="{kt}" calcMode="linear" />'
            )
            svg.append(
                f'  <animate attributeName="width" dur="{total_dur}s" repeatCount="indefinite" '
                f'values="{w_vals}" keyTimes="{kt}" calcMode="linear" />'
            )
            svg.append(
                f'  <animate attributeName="x" dur="{total_dur}s" repeatCount="indefinite" '
                f'values="{x_vals}" keyTimes="{kt}" calcMode="linear" />'
            )
            svg.append("</rect>")

    svg.append("</g></svg>")
    Path(args.output_svg).write_text("\n".join(svg), encoding="utf-8")
    print(
        f"Wrote: {args.output_svg}  frames={N} duration={total_dur:.3f}s "
        f"rects={cols*rows} transition_s={args.transition_s} hold_s={args.hold_s} "
        f"min_full_rotations={args.min_full_rotations}"
    )


if __name__ == "__main__":
    main()
