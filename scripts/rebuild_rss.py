#!/usr/bin/env python3
"""The podcast feed: every playable dose in `published_audio/`, newest first.

The feed is where a dismissed notification stays replayable, and it is the
source for "what audio reached the learner" (`feed_items`), so the rating picker
and the podcast app agree by construction. Published values are frozen
(`existing_items`): an item's date and duration are measured once.

    python scripts/rebuild_rss.py
"""
import json
import os
import re
import subprocess
from datetime import datetime
import email.utils
from xml.sax.saxutils import escape as xml_escape

import audio_titles
from pack import (CAPTION_COLUMNS, FEED_SUMMARY, FEED_TITLE, LEARNER,
                  RAW_BASE_URL, SITE_URL, TUTOR)
# The learner's clock; RECENT_AUDIO_PATH is the picker's list, written here
# because this module writes its source.
from state_io import LOCAL_TZ, RECENT_AUDIO_PATH

BASE_URL = RAW_BASE_URL
AUDIO_DIR = "published_audio"
SCRIPTS_DIR = "content/scripts"
# Below this, a .mp3 is a stub, a truncated write, or an lfs pointer — not audio.
MIN_PLAYABLE_BYTES = 2048
CAPTIONS_DIR = "content/captions"  # follow-along sheets; the GitHub blob URL renders the md
RSS_FILE = "rss.xml"
AUTHOR = xml_escape(f"{LEARNER} & {TUTOR}")

RSS_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
    xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"
    xmlns:content="http://purl.org/rss/1.0/modules/content/">
  <channel>
    <title>{feed_title}</title>
    <link>{site_url}</link>
    <language>en-us</language>
    <itunes:author>{author}</itunes:author>
    <itunes:summary>{feed_summary}</itunes:summary>
    <description>{feed_summary}</description>
    <itunes:owner>
      <itunes:name>{author}</itunes:name>
    </itunes:owner>
    <itunes:explicit>no</itunes:explicit>
    <itunes:category text="Education">
      <itunes:category text="Language Courses"/>
    </itunes:category>
    <itunes:image href="{base_url}/logo.jpg"/>
    <itunes:type>episodic</itunes:type>
    <itunes:new-feed-url>{base_url}/rss.xml</itunes:new-feed-url>
    {items}
  </channel>
</rss>
"""

ITEM_TEMPLATE = """
    <item>
      <title>{title}</title>
      <itunes:author>{author}</itunes:author>
      <itunes:summary>{summary}</itunes:summary>{caption_block}
      <enclosure url="{audio_url}" length="{size}" type="audio/mpeg"/>
      <guid>{audio_url}</guid>
      <pubDate>{pub_date}</pubDate>
      <itunes:duration>{duration}</itunes:duration>
    </item>
"""

# Show notes for an episode with a caption sheet: <link> and an anchor in
# <description>; podcast apps render one or the other.
CAPTION_BLOCK = """
      <link>{caption_url}</link>
      <description><![CDATA[\U0001F4D6 <a href="{caption_url}">Captions — follow along ({caption_columns})</a>]]></description>"""


def caption_block_for(script_md_name: str) -> str:
    """The show-notes block iff a caption sheet exists for this script name."""
    if not os.path.exists(os.path.join(CAPTIONS_DIR, script_md_name)):
        return ""
    return CAPTION_BLOCK.format(
        caption_url=f"{SITE_URL}/blob/main/{CAPTIONS_DIR}/{script_md_name}",
        caption_columns=xml_escape(CAPTION_COLUMNS))


def clean_title(raw_title: str, filename: str) -> str:
    """A script title → a clean episode title.

        "Tier 2 Mission 15: The Overheard Argument", "tier2_mission15_intercept.mp3"
        → "Ep 15 — The Overheard Argument · Intercept"

    A recorded name wins for every audio lane (`audio_titles.lane_title`); the
    dated contract lines are the fallback. No minute figure in a title:
    `<itunes:duration>` carries the measured length, and a second copy can only drift."""
    if named := audio_titles.lane_title(filename):
        return named

    drill = re.match(r"drill_(\d{4}-\d{2}-\d{2})", filename)
    if drill:
        return f"Drill — {drill.group(1)} · say it out loud"

    soak = re.match(r"soak_(\d{4}-\d{2}-\d{2})", filename)
    if soak:
        return f"Soak — {soak.group(1)} · nothing to do but listen"

    rotation = re.match(r"rotation_([a-z]+)_(\d{4}-\d{2}-\d{2})", filename)
    if rotation:
        return (f"Rotation — {rotation.group(1)} · {rotation.group(2)} "
                f"· press once, nothing asked")

    ep_type = None
    if re.search(r"_intercept", filename, re.IGNORECASE):
        ep_type = "Intercept"
    elif re.search(r"_breakdown", filename, re.IGNORECASE):
        ep_type = "Breakdown"

    match = re.match(
        r"Tier\s+(\d+),?\s+Mission\s+(\d+)\s*[:—-]\s*(.+)", raw_title, re.IGNORECASE
    )
    if match:
        mission = match.group(2)
        subtitle = match.group(3).strip()
        subtitle = re.sub(r"\s*\(.*?\)\s*$", "", subtitle).strip()
        base = f"Ep {mission} — {subtitle}"
        return f"{base} · {ep_type}" if ep_type else base

    if filename.startswith("special_") and raw_title and raw_title != filename:
        return raw_title

    return filename.replace(".mp3", "").replace("_", " ").title()


# Every mp3 the tutor pushes lands in `published_audio/knocks/`:
#   knock_<ts>          — morning_knock.py, the ambient dose
#   queued_q<id>_<ts>   — push_queue.py, a scheduled dose rendered at fire time
#   reply_<ts>          — knock_reply.py, a lock-screen reply answered aloud
#   payoff_<ts>         — render_payoff.py, a heard tape re-cut with its meaning;
#                         it carries the KNOCK's timestamp, which pairs the two
KNOCK_AUDIO_RE = re.compile(
    r"^(knock|queued|reply|payoff)_(?:q\d+_)?(\d{4})-(\d{2})-(\d{2})(?:T(\d{2})-(\d{2}))?")

KNOCK_KIND = {"knock": "Knock", "queued": "Scheduled", "reply": "Reply",
              "payoff": "Payoff"}


def knock_meta():
    """mp3 STEM -> (move, modality) from the knock log. Reads `mp3`, `audio_url`
    or `reply_audio_url` (lanes record one or the other; both end in the same
    basename), plus a payoff's own `payoff_mp3`. The modality is the only record
    of what kind of dose it was: durations overlap and cannot say."""
    try:
        with open("progress/knock_log.json", encoding="utf-8") as f:
            entries = json.load(f)
    except Exception:
        return {}
    meta = {}
    for e in entries:
        pair = (e.get("move") or "", e.get("modality") or "")
        ref = e.get("mp3") or e.get("audio_url") or e.get("reply_audio_url") or ""
        if ".mp3" in ref:
            meta[os.path.basename(ref).removesuffix(".mp3")] = pair
        pay = e.get("payoff_mp3") or ""
        if ".mp3" in pay:
            meta[os.path.basename(pay).removesuffix(".mp3")] = pair
    return meta


def knock_title(filename: str, meta: dict) -> str:
    """"knocks/knock_2026-07-05T22-58.mp3" -> "Knock — 2026-07-05 22:58 · <move>".
    A payoff is named for the tape it explains, not stamped like a second copy
    of it: the player has already downloaded both."""
    base = os.path.basename(filename)
    m = KNOCK_AUDIO_RE.match(base)
    when = base.replace(".mp3", "")
    kind = "Knock"
    if m:
        kind = KNOCK_KIND.get(m.group(1), "Knock")
        when = f"{m.group(2)}-{m.group(3)}-{m.group(4)}"
        if m.group(5):
            when += f" {m.group(5)}:{m.group(6)}"
    move = meta.get(base.removesuffix(".mp3"), ("", ""))[0]
    if m and m.group(1) == "payoff":
        tape = f"the {m.group(3)}-{m.group(4)} tape, explained"
        return f"{kind} — {move} · {tape}" if move else f"{kind} — {tape}"
    return f"{kind} — {when} · {move}" if move else f"{kind} — {when}"


def superseded(episodes: list) -> list:
    """Drop a tape the feed has a payoff for: one dose, one row. Keyed on the
    ARTIFACT, never a flag — a payoff stamped and never rendered must not evict
    its tape. Runs after the playability floor. The mp3 is not deleted."""
    paid = {f.removeprefix("knocks/payoff_") for f in episodes
            if f.startswith("knocks/payoff_")}
    return [f for f in episodes
            if not (f.startswith("knocks/knock_")
                    and f.removeprefix("knocks/knock_") in paid)]


def md_name(filename: str) -> str:
    """The BASE markdown name for an mp3: an intercept, breakdown or `_vN` cut
    resolves to the script it was cut from."""
    base = re.sub(r"_(intercept|breakdown|v\d+)\.mp3$", ".md", filename, flags=re.IGNORECASE)
    return base if base.endswith(".md") else filename.replace(".mp3", ".md")


def script_for(filename: str) -> str:
    """The script an mp3 was made from: its own, else the base cut's."""
    specific = os.path.join(SCRIPTS_DIR, filename.replace(".mp3", ".md"))
    return specific if os.path.exists(specific) else os.path.join(SCRIPTS_DIR, md_name(filename))


def get_title_from_md(md_path):
    if not os.path.exists(md_path):
        return None
    with open(md_path, 'r', encoding='utf-8') as f:
        first_line = f.readline().strip()
        if first_line.startswith('#'):
            return first_line.lstrip('#').strip()
    return os.path.basename(md_path)


def audio_format(stem: str) -> str:
    """Which production lane made this feed item, so ratings can compare formats."""
    for prefix, name in (("soak_", "soak"), ("drill_", "drill"),
                         ("rotation_", "rotation"), ("special_", "special")):
        if stem.startswith(prefix):
            return name
    return "mission" if stem.startswith("tier") else "episode"


# Knock doses the rating picker will NOT offer. A denylist: an allowlist's
# failure is a new modality silently missing. A fielding prompt is one line;
# spoken replies (by stem) are the learner's own half of an exchange.
UNRATEABLE_FORMATS = {"knock/fielding"}


def feed_items():
    """Everything in the feed, newest by pubDate first — `[{id, title, format,
    minutes, date}]`. Knock doses are offered as `knock/<modality>` (and payoffs
    as `payoff`), because comparing formats is what the rating ledger is for. An
    unlogged knock is OFFERED as `knock/dose`, never dropped."""
    import xml.etree.ElementTree as ET
    if not os.path.exists(RSS_FILE):
        return []
    try:
        root = ET.parse(RSS_FILE).getroot()
    except ET.ParseError:
        print("  ⚠ rss.xml did not parse — no feed items to offer")
        return []
    meta = knock_meta()
    out = []
    for item in root.findall("./channel/item"):
        enc = item.find("enclosure")
        url = (enc.get("url") if enc is not None else "") or ""
        stem = url.rsplit("/", 1)[-1].removesuffix(".mp3")
        fmt = audio_format(stem)
        if "/knocks/" in url:
            fmt = "knock/" + (meta.get(stem, ("", ""))[1] or "dose")
            if stem.startswith("payoff_"):
                fmt = "payoff"
            if stem.startswith("reply_") or fmt in UNRATEABLE_FORMATS:
                continue
        title = (item.findtext("title") or "").strip()
        if not stem or not title:
            continue
        try:
            when = email.utils.parsedate_to_datetime(item.findtext("pubDate") or "")
        except (TypeError, ValueError):
            continue
        dur = (item.findtext("{http://www.itunes.com/dtds/podcast-1.0.dtd}duration")
               or "").strip()
        out.append({"id": stem, "title": title, "format": fmt, "at": when,
                    "minutes": _hhmmss_min(dur), "date": when.date().isoformat()})
    out.sort(key=lambda d: d["at"], reverse=True)
    for d in out:
        d.pop("at")
    return out


def _hhmmss_min(raw: str) -> float:
    """`HH:MM:SS` -> minutes; unparseable is 0.0, never a guess."""
    parts = (raw or "").split(":")
    if not all(p.strip().isdigit() for p in parts) or not 2 <= len(parts) <= 3:
        return 0.0
    h, m, sec = ([0] + [int(p) for p in parts])[-3:]
    return h * 60 + m + sec / 60


def write_recent_audio(n: int = 6):
    """Publish the rating picker's list — the last n feed titles, newest first.
    Written by the feed's own owner, in the same function, so it can never lag its
    source. Flat strings in plain text: a phone shortcut reads it as a list."""
    RECENT_AUDIO_PATH.write_text(
        "\n".join(d["title"] for d in feed_items()[:n]) + "\n",
        encoding="utf-8", newline="\n")


def existing_items():
    """{guid_url: {"pubDate", "duration"}} from the current rss.xml, so a rebuild
    republishes what was published. MEASURE ONCE, THEN FREEZE: re-deriving a date
    falls through to checkout mtime, and a duration to whatever tool the host has.
    Preservation must not depend on well-formed XML, so a tolerant text scan backs
    up the strict parse."""
    if not os.path.exists(RSS_FILE):
        return {}
    with open(RSS_FILE, encoding="utf-8") as f:
        raw = f.read()

    import xml.etree.ElementTree as ET
    try:
        root = ET.fromstring(raw)
        result = {}
        for item in root.iter("item"):
            guid = item.findtext("guid")
            pub_date = item.findtext("pubDate")
            if guid and pub_date:
                dur = item.findtext("{http://www.itunes.com/dtds/podcast-1.0.dtd}duration")
                result[guid.strip()] = {"pubDate": pub_date.strip(),
                                        "duration": (dur or "").strip()}
        if result:
            return result
    except ET.ParseError as e:
        print(f"⚠️  rss.xml is not well-formed ({e}); recovering published values via text scan.")

    result = {}
    for block in re.findall(r"<item>(.*?)</item>", raw, re.S):
        g = re.search(r"<guid>(.*?)</guid>", block, re.S)
        p = re.search(r"<pubDate>(.*?)</pubDate>", block, re.S)
        d = re.search(r"<itunes:duration>(.*?)</itunes:duration>", block, re.S)
        if g and p:
            result[g.group(1).strip()] = {"pubDate": p.group(1).strip(),
                                          "duration": d.group(1).strip() if d else ""}
    return result


# MPEG audio frame tables, Layer III only (everything here is TTS mp3).
_BITRATES = {  # kb/s, indexed by the header's 4-bit bitrate index
    1: [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320],  # MPEG 1
    2: [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160],      # MPEG 2 / 2.5
}
_RATES = {3: [44100, 48000, 32000], 2: [22050, 24000, 16000], 0: [11025, 12000, 8000]}


def mp3_duration(path):
    """Seconds by summing every frame header; None if the file won't parse. These
    files are raw frame concatenations with no VBR header, so a first-frame
    bitrate estimate runs long; each header states its own rate."""
    with open(path, "rb") as f:
        data = f.read()

    i = 0
    if data[:3] == b"ID3":  # skip the tag: its size is 4 syncsafe bytes at offset 6
        i = 10 + int.from_bytes(bytes(b & 0x7F for b in data[6:10]), "big")
        if data[5] & 0x10:  # footer present
            i += 10

    seconds = 0.0
    end = len(data)
    while i + 4 <= end:
        if data[i] != 0xFF or (data[i + 1] & 0xE0) != 0xE0:
            i += 1  # not a sync word
            continue
        h = data[i + 1:i + 4]
        version = (h[0] >> 3) & 0x03           # 3=MPEG1, 2=MPEG2, 0=MPEG2.5
        layer = (h[0] >> 1) & 0x03             # 1 = Layer III
        bitrate_idx = (h[1] >> 4) & 0x0F
        rate_idx = (h[1] >> 2) & 0x03
        if layer != 1 or version == 1 or rate_idx == 3 or bitrate_idx in (0, 15):
            i += 1
            continue
        rate = _RATES[version][rate_idx]
        bitrate = _BITRATES[1 if version == 3 else 2][bitrate_idx] * 1000
        samples = 1152 if version == 3 else 576
        length = (samples // 8) * bitrate // rate + ((h[1] >> 1) & 0x01)
        if length <= 0:
            i += 1
            continue
        seconds += samples / rate
        i += length

    return seconds or None


def ffprobe_duration(path):
    """Seconds by decoding the real stream; None if ffprobe is absent."""
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(path)],
            capture_output=True, text=True, timeout=60)
        return float(r.stdout.strip()) or None
    except Exception:
        return None


def audio_duration(path):
    """Seconds for the feed: ffprobe first, the frame scan as fallback (one bad
    header can desync a scan in either direction). Honest meters or none."""
    return ffprobe_duration(path) or mp3_duration(path)


def duration_hms(path, fallback):
    """"HH:MM:SS" for the feed."""
    try:
        total = int(audio_duration(path))
    except Exception:
        return fallback
    return f"{total // 3600:02d}:{(total % 3600) // 60:02d}:{total % 60:02d}"


def generate_rss():
    published = existing_items()
    items = []
    if not os.path.exists(AUDIO_DIR):
        print(f"❌ {AUDIO_DIR} not found!")
        return

    audio_files = [f for f in os.listdir(AUDIO_DIR) if f.endswith('.mp3')]
    episodes = [f for f in audio_files
                if f.startswith(('tier', 'drill_', 'soak_', 'rotation_', 'special_'))
                and not f.endswith('_intercept.mp3')]

    knocks_dir = os.path.join(AUDIO_DIR, "knocks")
    if os.path.isdir(knocks_dir):
        episodes += [f"knocks/{f}" for f in os.listdir(knocks_dir) if f.endswith('.mp3')]

    # Only what a player can actually PLAY: an unplayable item is a dead entry.
    playable, skipped = [], []
    for f in episodes:
        p = os.path.join(AUDIO_DIR, f)
        if os.path.isfile(p) and os.path.getsize(p) >= MIN_PLAYABLE_BYTES:
            playable.append(f)
        else:
            skipped.append(f)
    if skipped:
        print(f"⚠ skipping {len(skipped)} unplayable file(s): {', '.join(skipped[:5])}")
    episodes = superseded(playable)
    knock_metadata = knock_meta()

    # Missions by number; dated tracks one band, chronological; pushed doses one
    # band; specials on top. A prefix missing here sorts silently at the bottom —
    # add it here and to the filter above together.
    def sort_key(filename):
        match = re.search(r"tier(\d+)_mission(\d+)", filename)
        if match:
            return (int(match.group(1)), int(match.group(2)))
        match = re.search(r"(?:drill|soak|rotation_[a-z]+)_(\d{4})-(\d{2})-(\d{2})(?:_(\d{4}))?",
                          filename)
        if match:
            return (9, int("".join(g or "0" for g in match.groups())))
        match = KNOCK_AUDIO_RE.match(os.path.basename(filename))
        if match:
            return (8, int("".join(g or "0" for g in match.groups()[1:])))
        if filename.startswith("special_"):
            return (10, 0)
        return (0, 0)

    # Filename breaks ties so the order is a function of the library, not the host.
    episodes.sort(key=lambda f: (sort_key(f), f), reverse=True)

    # Titles are resolved as a SET: distinctness is a property of the pair.
    titles = {f: (knock_title(f, knock_metadata) if f.startswith("knocks/")
                  else clean_title(get_title_from_md(script_for(f)) or f, f))
              for f in episodes}
    titles = audio_titles.distinct(titles)

    for filename in episodes:
        audio_path = os.path.join(AUDIO_DIR, filename)
        title = titles[filename]
        size = os.path.getsize(audio_path)
        audio_url = f"{BASE_URL}/{AUDIO_DIR}/{filename}"
        # Published values are never restamped; a new item is dated on the
        # learner's clock, never the host's.
        prior = published.get(audio_url, {})
        pub_date = prior.get("pubDate") or email.utils.format_datetime(
            datetime.fromtimestamp(os.path.getmtime(audio_path), LOCAL_TZ)
        )
        duration = prior.get("duration") or duration_hms(audio_path, "00:05:00")

        # Titles carry target script and arbitrary punctuation: escape them.
        items.append(ITEM_TEMPLATE.format(
            title=xml_escape(title),
            author=AUTHOR,
            summary=xml_escape(title),
            caption_block=caption_block_for(md_name(filename)),
            audio_url=audio_url,
            size=size,
            pub_date=pub_date,
            duration=duration
        ))

    rss_content = RSS_TEMPLATE.format(
        base_url=BASE_URL,
        site_url=SITE_URL,
        author=AUTHOR,
        feed_title=xml_escape(FEED_TITLE),
        feed_summary=xml_escape(FEED_SUMMARY),
        items="".join(items)
    )

    with open(RSS_FILE, 'w', encoding='utf-8') as f:
        f.write(rss_content)
    print(f"✅ Generated {RSS_FILE} with {len(items)} episodes.")
    write_recent_audio()


if __name__ == "__main__":
    generate_rss()
