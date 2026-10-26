"""Minimal XMLTV guide parsing."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import io
import xml.etree.ElementTree as ET

# Placeholder programme titles some guide generators emit for empty lanes.
IDLE_TITLES = ("idle", "stand by", "standby", "off air", "no event")


@dataclass(frozen=True)
class Programme:
    """One guide entry."""

    channel_id: str
    start: datetime
    stop: datetime
    title: str
    description: str | None = None
    categories: tuple[str, ...] = field(default_factory=tuple)
    live: bool = False

    @property
    def is_idle(self) -> bool:
        return self.title.strip().lower().startswith(IDLE_TITLES)


def _parse_time(value: str) -> datetime:
    """Parse XMLTV times like '20261024163000 +0000'."""
    value = value.strip()
    if " " in value:
        return datetime.strptime(value, "%Y%m%d%H%M%S %z")
    return datetime.strptime(value + " +0000", "%Y%m%d%H%M%S %z")


def parse_xmltv(data: bytes) -> dict[str, list[Programme]]:
    """Return programmes grouped by channel id, sorted by start time."""
    guide: dict[str, list[Programme]] = {}
    for _, elem in ET.iterparse(io.BytesIO(data), events=("end",)):
        if elem.tag != "programme":
            continue
        try:
            prog = Programme(
                channel_id=elem.get("channel", ""),
                start=_parse_time(elem.get("start", "")),
                stop=_parse_time(elem.get("stop", "")),
                title=(elem.findtext("title") or "").strip(),
                description=(elem.findtext("desc") or None),
                categories=tuple(c.text.strip() for c in elem.findall("category") if c.text),
                live=elem.find("live") is not None,
            )
        except ValueError:
            continue
        finally:
            elem.clear()
        guide.setdefault(prog.channel_id, []).append(prog)
    for progs in guide.values():
        progs.sort(key=lambda p: p.start)
    return guide


def programme_at(progs: list[Programme] | None, when: datetime) -> Programme | None:
    """The programme airing at `when`, or None."""
    for prog in progs or ():
        if prog.start <= when < prog.stop:
            return prog
        if prog.start > when:
            break
    return None
