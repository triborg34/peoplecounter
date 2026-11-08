"""Creates the sample video used to test the system without a camera.

    python -m app.tools.sample_data

It downloads a photo with people, cuts one person out of it and renders a
short video in which that person walks across the scene and back.  The result
can be used as a "video file" camera source.
"""
from __future__ import annotations

import argparse
import logging
import urllib.request
from pathlib import Path

import cv2
import numpy as np

log = logging.getLogger(__name__)

PHOTO_URL = "https://ultralytics.com/images/bus.jpg"


def download_photo(target: Path) -> Path:
    if target.exists():
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    log.info("Downloading the sample photo from %s", PHOTO_URL)
    urllib.request.urlretrieve(PHOTO_URL, target)
    return target


def cut_person(photo_path: Path) -> np.ndarray:
    """Return a cut out of the photo that the detector recognises as a person."""
    image = cv2.imread(str(photo_path))
    if image is None:
        raise RuntimeError("Could not read " + str(photo_path))
    height, width = image.shape[:2]
    # the sample photo contains three people, pick the left one
    crop = image[int(height * 0.38) : int(height * 0.80), int(width * 0.26) : int(width * 0.44)]
    if crop.size == 0:
        raise RuntimeError("Could not cut a person out of the sample photo")
    return crop


def render_video(person: np.ndarray, output: Path, width: int = 640, height: int = 480,
                 fps: int = 8, seconds: int = 12) -> Path:
    """Render a video in which the person walks across the frame and back."""
    output.parent.mkdir(parents=True, exist_ok=True)
    target_height = int(height * 0.62)
    scale = target_height / person.shape[0]
    person = cv2.resize(person, (max(1, int(person.shape[1] * scale)), target_height))

    writer = cv2.VideoWriter(
        str(output), cv2.VideoWriter_fourcc(*"mp4v"), float(fps), (width, height)
    )
    total = fps * seconds
    for index in range(total):
        phase = index / max(1, total - 1)
        # walk left to right, then right to left
        travel = phase * 2.0
        position = travel if travel <= 1.0 else 2.0 - travel
        frame = np.full((height, width, 3), 205, dtype=np.uint8)
        cv2.rectangle(frame, (0, height - 40), (width, height), (150, 150, 150), -1)
        x = int(position * (width - person.shape[1]))
        y = height - 40 - person.shape[0]
        frame[y : y + person.shape[0], x : x + person.shape[1]] = person
        writer.write(frame)
    writer.release()
    log.info("Sample video written to %s", output)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Create the sample video for testing")
    parser.add_argument("--data-dir", default=None)
    args = parser.parse_args()

    from ..config import get_settings

    settings = get_settings()
    data_dir = Path(args.data_dir or settings.data_dir)
    photo = download_photo(data_dir / "sample" / "bus.jpg")
    person = cut_person(photo)
    video = render_video(person, data_dir / "sample" / "sample_walk.mp4")
    print("Sample video: " + str(video))


if __name__ == "__main__":
    main()
