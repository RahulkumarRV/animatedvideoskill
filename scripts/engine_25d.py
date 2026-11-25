"""
Historical Map Animation 2.5D Physical Compositing Engine
Creator & Credits: rahulkumar
Project: animatedvideoskill
"""

import math
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont

W, H = 720, 1280
OV_W, OV_H = 900, 1600
FPS = 30
SR = 44100


def smoothstep(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def smootherstep(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * t * (t * (t * 6.0 - 15.0) + 10.0)


def spring_pop(t: float, dur: float = 0.38) -> float:
    if t <= 0.0:
        return 0.0
    u = t / dur
    if u >= 1.0:
        return 1.0
    if u < 0.55:
        return 1.16 * smoothstep(u / 0.55)
    elif u < 0.82:
        return 1.16 - 0.20 * smoothstep((u - 0.55) / 0.27)
    return 0.96 + 0.04 * smoothstep((u - 0.82) / 0.18)


def parabolic_hop(t: float, t0: float, t1: float, p0: tuple, p1: tuple, hop_height: float = 48.0):
    if t <= t0:
        return p0[0], p0[1], 0.0, 0.0
    if t >= t1:
        return p1[0], p1[1], 0.0, 0.0
    u = smootherstep((t - t0) / max(1e-4, t1 - t0))
    x = p0[0] + (p1[0] - p0[0]) * u
    y_linear = p0[1] + (p1[1] - p0[1]) * u
    lift = math.sin(u * math.pi) * hop_height
    tilt = math.sin(u * math.pi * 2.0) * 8.5
    return x, y_linear - lift, lift, tilt


def extract_green_screen_sprite(img_path: str, out_png_path: str, target_max_dim: int = 420) -> Image.Image:
    bgr = cv2.imread(img_path)
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    green_mask = cv2.inRange(hsv, np.array([32, 65, 65]), np.array([90, 255, 255]))
    fg_mask = cv2.bitwise_not(green_mask)
    fg_mask[:8, :] = fg_mask[-8:, :] = fg_mask[:, :8] = fg_mask[:, -8:] = 0

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel, iterations=1)
    fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    fg_mask = cv2.erode(fg_mask, np.ones((3, 3), np.uint8), iterations=1)
    alpha = cv2.GaussianBlur(fg_mask, (3, 3), 0)

    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB).astype(np.float32)
    r, g, b = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]
    spill = np.maximum(0.0, g - np.maximum(r, b))
    rgb[:, :, 1] = g - spill * 0.80
    rgba = np.dstack([np.clip(rgb, 0, 255).astype(np.uint8), alpha])

    ys, xs = np.where(alpha > 20)
    if len(xs) > 0 and len(ys) > 0:
        h, w = fg_mask.shape
        rgba = rgba[max(0, int(ys.min()) - 4):min(h, int(ys.max()) + 5),
                    max(0, int(xs.min()) - 4):min(w, int(xs.max()) + 5)]

    pil_sp = Image.fromarray(rgba, mode="RGBA")
    if max(pil_sp.size) > target_max_dim:
        sc = target_max_dim / float(max(pil_sp.size))
        pil_sp = pil_sp.resize((max(8, int(pil_sp.size[0] * sc)), max(8, int(pil_sp.size[1] * sc))), Image.Resampling.LANCZOS)
    pil_sp.save(out_png_path)
    return pil_sp


def draw_flame_cluster(canvas_pil: Image.Image, cx: float, cy: float, t: float, intensity: float = 1.0, seed: int = 0):
    """Alpha-composited soft fire glow + animated tongues + rising embers (never overwrites canvas alpha)."""
    if intensity <= 0.02:
        return
    s = intensity
    pad = int(max(90, 115 * s))
    patch = Image.new("RGBA", (pad * 2, pad * 2), (0, 0, 0, 0))
    pd = ImageDraw.Draw(patch, "RGBA")
    pc = pad
    for mult, alpha_v in [(1.0, 26), (0.72, 42), (0.45, 65)]:
        gr = int(76 * s * mult * (0.94 + 0.06 * math.sin(t * 13.0 + seed)))
        pd.ellipse([pc - gr, pc - gr, pc + gr, pc + gr], fill=(255, 110, 20, int(alpha_v * min(1.0, s))))
    for k in range(5):
        ph = t * (10.0 + k * 2.1) + seed * 1.7 + k * 1.3
        ox = (k - 2) * 14 * s + math.sin(ph) * 5 * s
        fh = (44 + (k % 3) * 18) * s * (0.85 + 0.22 * abs(math.sin(ph)))
        fw = (15 + (k % 2) * 5) * s
        pd.polygon([
            (pc + ox - fw, pc + 8 * s),
            (pc + ox - fw * 0.6, pc - fh * 0.45),
            (pc + ox + math.sin(ph * 1.3) * 7 * s, pc - fh),
            (pc + ox + fw * 0.6, pc - fh * 0.45),
            (pc + ox + fw, pc + 8 * s),
        ], fill=(242, 82, 18, int(225 * min(1.0, s))))
        pd.polygon([
            (pc + ox - fw * 0.48, pc + 5 * s),
            (pc + ox + math.sin(ph * 1.3) * 4 * s, pc - fh * 0.62),
            (pc + ox + fw * 0.48, pc + 5 * s),
        ], fill=(255, 226, 92, int(240 * min(1.0, s))))
    for e in range(5):
        ep = (t * 1.1 + seed * 0.23 + e * 0.21) % 1.0
        ex = pc + math.sin(ep * 6.0 + e * 2.0 + seed) * 28 * s - ep * 20 * s
        ey = pc - 18 * s - ep * (pad - 12)
        er = max(2, int((1.0 - ep) * 4.5 * s))
        pd.ellipse([ex - er, ey - er, ex + er, ey + er], fill=(255, 210, 85, int((1.0 - ep) * 230)))
    canvas_pil.alpha_composite(patch, (int(cx - pad), int(cy - pad)))
