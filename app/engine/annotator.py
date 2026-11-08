"""Draws detections, tracks, counting lines/areas and the counters on a frame."""
from __future__ import annotations

import colorsys
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from .types import AreaSpec, LineSpec, Track


def hex_to_bgr(color: str, default: Tuple[int, int, int] = (34, 197, 94)) -> Tuple[int, int, int]:
    try:
        value = color.lstrip("#")
        r, g, b = (int(value[i : i + 2], 16) for i in (0, 2, 4))
        return (b, g, r)
    except Exception:
        return default


def track_color(track_id: int) -> Tuple[int, int, int]:
    hue = (track_id * 0.618033988749895) % 1.0
    r, g, b = colorsys.hsv_to_rgb(hue, 0.85, 1.0)
    return (int(b * 255), int(g * 255), int(r * 255))


def draw_frame(
    frame: np.ndarray,
    tracks: Sequence[Track],
    lines: Sequence[LineSpec] = (),
    areas: Sequence[AreaSpec] = (),
    counters: Optional[Dict[Tuple[str, int], Dict[str, int]]] = None,
    camera_name: str = "",
    status: str = "",
    show_overlay: bool = True,
) -> np.ndarray:
    """Return an annotated copy of the frame."""
    import cv2

    canvas = frame.copy()
    height, width = canvas.shape[:2]
    if not show_overlay:
        return canvas

    # areas (filled, drawn under the lines)
    for area in areas:
        if not area.enabled or len(area.points) < 3:
            continue
        pts = np.array([[int(p[0] * width), int(p[1] * height)] for p in area.points], dtype=np.int32)
        overlay = canvas.copy()
        cv2.fillPoly(overlay, [pts], hex_to_bgr(area.color, (59, 130, 246)))
        cv2.addWeighted(overlay, 0.18, canvas, 0.82, 0, canvas)
        cv2.polylines(canvas, [pts], True, hex_to_bgr(area.color, (59, 130, 246)), 2)
        cv2.putText(
            canvas, area.name, (pts[0][0], max(16, pts[0][1] - 8)),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6, hex_to_bgr(area.color, (59, 130, 246)), 2,
        )

    # counting lines with direction arrows and A/B labels
    for line in lines:
        if not line.enabled:
            continue
        p1 = (int(line.x1 * width), int(line.y1 * height))
        p2 = (int(line.x2 * width), int(line.y2 * height))
        color = hex_to_bgr(line.color)
        cv2.line(canvas, p1, p2, color, 3)
        cv2.circle(canvas, p1, 7, color, -1)
        cv2.circle(canvas, p2, 7, color, -1)
        cv2.putText(canvas, "A", (p1[0] + 8, p1[1] - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
        cv2.putText(canvas, "B", (p2[0] + 8, p2[1] - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

        # Arrows that show which walking direction is counted.  The arrows are
        # perpendicular to the line, because people usually walk across it.
        mid = ((p1[0] + p2[0]) / 2.0, (p1[1] + p2[1]) / 2.0)
        in_start, in_end = _direction_arrow(p1, p2, +1)
        out_start, out_end = _direction_arrow(p1, p2, -1)
        if line.direction in ("A_TO_B", "BOTH"):
            cv2.arrowedLine(canvas, in_start, in_end, color, 3, tipLength=0.35)
            cv2.putText(canvas, "IN", (int(in_end[0] + 6), int(in_end[1] + 5)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
        if line.direction in ("B_TO_A", "BOTH"):
            dim = tuple(int(c * 0.65) for c in color)
            cv2.arrowedLine(canvas, out_start, out_end, dim, 2, tipLength=0.35)
            cv2.putText(canvas, "OUT", (int(out_end[0] + 6), int(out_end[1] + 5)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, dim, 2)

        label = line.name + " [" + line.direction + "]"
        cv2.putText(canvas, label, (int(mid[0] - 40), int(mid[1] - 26)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

    # detections / tracks
    for track in tracks:
        x1, y1, x2, y2 = [int(v) for v in track.bbox]
        color = track_color(track.track_id)
        cv2.rectangle(canvas, (x1, y1), (x2, y2), color, 2)
        tag = f"#{track.track_id} {track.confidence:.2f}"
        (tw, th), _ = cv2.getTextSize(tag, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        cv2.rectangle(canvas, (x1, max(0, y1 - th - 6)), (x1 + tw + 6, y1), color, -1)
        cv2.putText(canvas, tag, (x1 + 3, max(10, y1 - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)

    # header
    if camera_name:
        cv2.rectangle(canvas, (0, 0), (width, 26), (0, 0, 0), -1)
        cv2.putText(canvas, camera_name, (8, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        if status:
            cv2.putText(
                canvas, status.upper(), (width - 120, 18),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1,
            )

    # counters (bottom left)
    if counters:
        y = height - 10
        for (kind, target_id), values in sorted(counters.items(), key=lambda item: str(item[0])):
            text = f"{kind} #{target_id}  IN {values.get('in', 0)}  OUT {values.get('out', 0)}"
            cv2.putText(canvas, text, (8, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 3)
            cv2.putText(canvas, text, (8, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            y -= 18
            if y < 30:
                break
    return canvas


def _direction_arrow(p1: Tuple[int, int], p2: Tuple[int, int], sign: int,
                          length: int = 34):
    """A perpendicular arrow at the middle of the line.

    sign=+1 points into the half plane that counts as IN for an A_TO_B line,
    sign=-1 points into the opposite half plane.  The arrow shows the walking
    direction that is counted, which is what people need to see.
    """
    import math

    vx = p2[0] - p1[0]
    vy = p2[1] - p1[1]
    norm = math.hypot(vx, vy)
    if norm < 1e-6:
        return (p1, p2)
    ux, uy = vx / norm, vy / norm
    nx, ny = -uy, ux  # perpendicular, cross(v, n) > 0
    mid_x = (p1[0] + p2[0]) / 2.0
    mid_y = (p1[1] + p2[1]) / 2.0
    half = length / 2.0
    start = (int(mid_x - nx * half * sign), int(mid_y - ny * half * sign))
    end = (int(mid_x + nx * half * sign), int(mid_y + ny * half * sign))
    return (start, end)
