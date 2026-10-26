"""Tests for the standalone XMLTV parser."""

from datetime import datetime, timezone
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Load xmltv.py directly so the tests don't need Home Assistant installed.
_spec = importlib.util.spec_from_file_location("xmltv", ROOT / "custom_components/adbtuner/xmltv.py")
xmltv = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(xmltv)

SAMPLE = (ROOT / "tests/fixtures/sample_guide.xml").read_bytes()


def test_parses_programmes_by_channel():
    guide = xmltv.parse_xmltv(SAMPLE)
    assert set(guide) == {"sportscenter01", "peacock_web06"}
    first = guide["sportscenter01"][0]
    assert first.title.startswith("2026 WSL Championship Tour")
    assert first.start == datetime(2026, 10, 20, 6, 30, tzinfo=timezone.utc)
    assert first.live is True
    assert "Surfing" in first.categories


def test_programmes_sorted_and_lookup():
    progs = xmltv.parse_xmltv(SAMPLE)["sportscenter01"]
    assert progs == sorted(progs, key=lambda p: p.start)
    mid = progs[0].start + (progs[0].stop - progs[0].start) / 2
    assert xmltv.programme_at(progs, mid) is progs[0]
    assert xmltv.programme_at(progs, progs[0].start.replace(year=2000)) is None


def test_idle_placeholders():
    data = b"""<tv><programme channel="x" start="20261020000000 +0000" stop="20261020010000 +0000">
    <title>Idle</title></programme></tv>"""
    (prog,) = xmltv.parse_xmltv(data)["x"]
    assert prog.is_idle


def test_skips_malformed_times():
    data = b"""<tv><programme channel="x" start="garbage" stop="20261020010000 +0000"><title>A</title></programme>
    <programme channel="x" start="20261020000000" stop="20261020010000"><title>B</title></programme></tv>"""
    progs = xmltv.parse_xmltv(data)["x"]
    assert [p.title for p in progs] == ["B"]
    assert progs[0].start.tzinfo is not None
