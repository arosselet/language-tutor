#!/usr/bin/env python3
"""
Rebuild rss.xml from published_audio/ — the podcast feed.

Feed identity (title, description, author) and the serving URLs come from
config/tutor.json → feed. Audio is served raw off the repo's main branch, so
the repo must be PUBLIC for podcast apps to fetch it (see SETUP.md → publishing
trade-offs). Episodes are tierX_missionY.mp3; drill tracks are drill_<date>.mp3.
"""
import os
import re
import sys
import email.utils
from pathlib import Path
from mutagen.mp3 import MP3

sys.path.insert(0, str(Path(__file__).parent))
from config import FEED, REPO

BASE_URL = f"https://raw.githubusercontent.com/{REPO}/main"
SITE_URL = f"https://github.com/{REPO}"
AUDIO_DIR = "published_audio"
SCRIPTS_DIR = "content/scripts"
RSS_FILE = "rss.xml"
TITLE = FEED.get("title", "Language Tutor")
DESCRIPTION = FEED.get("description", "AI-generated language lessons.")
AUTHOR = FEED.get("author", "Learner &amp; tutor")

RSS_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
    xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"
    xmlns:content="http://purl.org/rss/1.0/modules/content/">
  <channel>
    <title>{title}</title>
    <link>{site_url}</link>
    <language>en-us</language>
    <itunes:author>{author}</itunes:author>
    <itunes:summary>{description}</itunes:summary>
    <description>{description}</description>
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
      <itunes:summary>{summary}</itunes:summary>
      <enclosure url="{audio_url}" length="{size}" type="audio/mpeg"/>
      <guid>{audio_url}</guid>
      <pubDate>{pub_date}</pubDate>
      <itunes:duration>{duration}</itunes:duration>
    </item>
"""


def clean_title(raw_title: str, filename: str) -> str:
    """
    Convert a raw script title into a clean, consistent episode title.

    Input:  "Tier 2 Mission 15: The Overheard Argument", "tier2_mission15.mp3"
    Output: "Ep 15 — The Overheard Argument"
    """
    # Drill tracks (spoken production volleys) carry their date, not a mission number
    drill = re.match(r"drill_(\d{4}-\d{2}-\d{2})", filename)
    if drill:
        return f"Drill — {drill.group(1)} · say it out loud"

    # Try to extract tier, mission, and subtitle from the raw title
    match = re.match(
        r"Tier\s+(\d+),?\s+Mission\s+(\d+)[:—-]\s*(.+)", raw_title, re.IGNORECASE
    )
    if match:
        mission = match.group(2)
        subtitle = match.group(3).strip()
        # Strip parenthetical style labels like "(The Remix)"
        subtitle = re.sub(r"\s*\(.*?\)\s*$", "", subtitle).strip()
        return f"Ep {mission} — {subtitle}"

    # Fallback: use filename without extension
    return filename.replace(".mp3", "").replace("_", " ").title()


def get_title_from_md(md_path):
    if not os.path.exists(md_path):
        return None
    with open(md_path, 'r') as f:
        first_line = f.readline().strip()
        if first_line.startswith('#'):
            return first_line.lstrip('#').strip()
    return os.path.basename(md_path)


def generate_rss():
    items = []
    if not os.path.exists(AUDIO_DIR):
        print(f"❌ {AUDIO_DIR} not found!")
        return

    audio_files = [f for f in os.listdir(AUDIO_DIR) if f.endswith('.mp3')]

    # Feed = tier-based episodes + drill tracks (knocks live in knocks/ and are
    # deliberately NOT on the feed — they are lock-screen doses, not episodes).
    episodes = [f for f in audio_files if f.startswith('tier') or f.startswith('drill_')]

    # Sort by mission number descending (newest first); drills sort above by date/time
    def sort_key(filename):
        match = re.search(r"tier(\d+)_mission(\d+)", filename)
        if match:
            return (int(match.group(1)), int(match.group(2)))
        match = re.search(r"drill_(\d{4})-(\d{2})-(\d{2})(?:_(\d{4}))?", filename)
        if match:
            return (9, int("".join(g or "0" for g in match.groups())))
        return (0, 0)

    episodes.sort(key=sort_key, reverse=True)

    for filename in episodes:
        audio_path = os.path.join(AUDIO_DIR, filename)
        script_path = os.path.join(SCRIPTS_DIR, filename.replace('.mp3', '.md'))

        raw_title = get_title_from_md(script_path) or filename
        title = clean_title(raw_title, filename)
        size = os.path.getsize(audio_path)
        mtime = os.path.getmtime(audio_path)
        pub_date = email.utils.formatdate(mtime, localtime=True)
        audio_url = f"{BASE_URL}/{AUDIO_DIR}/{filename}"

        # Calculate real duration from the MP3 file
        try:
            audio = MP3(audio_path)
            total_seconds = int(audio.info.length)
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            duration = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        except Exception:
            duration = "00:05:00"  # Fallback

        items.append(ITEM_TEMPLATE.format(
            title=title,
            author=AUTHOR,
            summary=title,
            audio_url=audio_url,
            size=size,
            pub_date=pub_date,
            duration=duration
        ))

    rss_content = RSS_TEMPLATE.format(
        title=TITLE,
        description=DESCRIPTION,
        base_url=BASE_URL,
        site_url=SITE_URL,
        author=AUTHOR,
        items="".join(items)
    )

    with open(RSS_FILE, 'w') as f:
        f.write(rss_content)
    print(f"✅ Generated {RSS_FILE} with {len(items)} episodes.")


if __name__ == "__main__":
    generate_rss()
