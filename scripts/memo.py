#!/usr/bin/env python3
"""The voice-memo renderer — a script in, an mp3 out, for any lane that speaks.

Every speaking lane uses it: the knock, a scheduled voice dose rendered by the
queue at fire time, and a reply answered aloud. It composes `render_audio`'s TTS
primitives into a memo (one voice, paragraph breaths, flat concatenation, no cast
and no script structure), which is a different job from rendering an episode.

Imports `render_audio` and the pack, no lane, so every lane may import it.
"""
import os
import sys
import tempfile
from pathlib import Path

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE / "scripts"))
from pack import TUTOR_VOICE
from render_audio import (SILENCE_FRAME, clean_memo_for_tts, generate_segment,
                          get_raw_mp3_frames)


async def render_memo(memo_script: str, out_path: Path, voice: str = TUTOR_VOICE):
    """Speak a memo script to one mp3: one TTS segment per paragraph, joined by
    a breath, on the configured provider."""
    segment = generate_segment
    paras = [p.strip() for p in memo_script.split("\n\n") if p.strip()]
    audio = bytearray()
    tmp = tempfile.mkdtemp()
    for i, para in enumerate(paras):
        seg = await segment(clean_memo_for_tts(para), voice, i, tmp)
        audio.extend(get_raw_mp3_frames(seg))
        audio.extend(SILENCE_FRAME * 25)  # ~0.6s breath between paragraphs
        os.remove(seg)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(audio)
    print(f"   rendered -> {out_path} ({len(audio)/1024:.0f} KB)")
