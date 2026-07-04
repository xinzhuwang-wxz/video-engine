from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class TimelineSegment:
    seq: int
    start: float
    end: float
    subtitle: str
    source_file: str
    rationale: str | None = None

    @property
    def duration(self) -> float:
        return self.end - self.start

    @property
    def midpoint(self) -> float:
        return self.start + self.duration / 2


def load_cutlist(path: str | Path) -> dict[str, Any]:
    cutlist_path = Path(path)
    with cutlist_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data.get("segments"), list):
        raise ValueError(f"{cutlist_path} does not contain a segments array")
    return data


def timeline_from_cutlist(cutlist: dict[str, Any]) -> list[TimelineSegment]:
    cursor = 0.0
    timeline: list[TimelineSegment] = []
    for index, segment in enumerate(cutlist["segments"], 1):
        main = segment["main"]
        speed = float(main.get("speed", 1.0))
        if speed <= 0:
            raise ValueError(f"segment {index} has invalid speed {speed}")
        duration = (float(main["out"]) - float(main["in"])) / speed
        if duration <= 0:
            raise ValueError(f"segment {index} has non-positive duration {duration}")
        timeline.append(
            TimelineSegment(
                seq=int(segment.get("seq", index)),
                start=cursor,
                end=cursor + duration,
                subtitle=(segment.get("subtitle") or "").strip(),
                source_file=str(main["file"]),
                rationale=segment.get("rationale"),
            )
        )
        cursor += duration
    return timeline


def timeline_duration(timeline: list[TimelineSegment]) -> float:
    return timeline[-1].end if timeline else 0.0

