from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MediaProfile:
    name: str
    width: int
    height: int
    fps: int
    video_codec: str = "libx264"
    audio_codec: str = "aac"
    crf: int = 18
    pixel_format: str = "yuv420p"
    audio_bitrate: str = "192k"
    notes: str = ""


DOUYIN_VERTICAL = MediaProfile(
    name="douyin_vertical",
    width=1080,
    height=1920,
    fps=30,
    crf=18,
    notes="Vertical 9:16 delivery profile for Douyin/TikTok-style short video.",
)

PREVIEW_VERTICAL = MediaProfile(
    name="preview_vertical",
    width=540,
    height=960,
    fps=30,
    crf=30,
    audio_bitrate="128k",
    notes="Fast low-resolution review render.",
)

PROFILES = {
    DOUYIN_VERTICAL.name: DOUYIN_VERTICAL,
    PREVIEW_VERTICAL.name: PREVIEW_VERTICAL,
}


def get_profile(name: str) -> MediaProfile:
    try:
        return PROFILES[name]
    except KeyError as exc:
        available = ", ".join(sorted(PROFILES))
        raise ValueError(f"Unknown media profile {name!r}. Available: {available}") from exc
