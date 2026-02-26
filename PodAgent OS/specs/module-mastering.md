# Module Spec: Mastering & Publishing Delivery

> **Status**: Draft
> **Last Updated**: 2026-02-25
> **Author**: Spec Writer Agent
> **Position in Pipeline**: Module 4 of 4 — receives mixed audio from Mixing, produces distribution-ready deliverables

---

## 1. Module Overview

The Mastering & Publishing Delivery module takes the mixed WAV from Module 3 and produces final, distribution-ready files. It performs loudness normalization (EBU R128), true-peak limiting, encoding to target formats (MP3, WAV), metadata embedding (ID3 tags, cover art, chapter markers), and assembles a complete publishing package.

This module does not re-edit or re-mix. It applies the final "polish" to a finished mix and packages it for the world.

---

## 2. Inputs

### 2.1 Required Inputs

#### Mixed Audio (`artifacts/mixing/mixed.wav`)

The stereo mix-down from Module 3.

| Property | Expected |
|----------|----------|
| Format | WAV (PCM) |
| Sample rate | 48kHz |
| Bit depth | 24-bit |
| Channels | Stereo |

#### Content Summary (`artifacts/editing/summary.md`)

Episode summary, chapter markers, key quotes, and links from Module 2. Used for show notes and metadata.

#### Episode Metadata (from `manifest.yaml`)

```yaml
project:
  name: "Tech Talk Weekly"     # → ID3 Album
  episode_number: 42            # → ID3 Track Number
  title: "AI Audio Processing"  # → ID3 Title
  recording_date: "2026-02-20"  # → ID3 Year
  participants:
    - name: "Alice"
      role: host                # → ID3 Artist (host name)
    - name: "Bob"
      role: guest
```

### 2.2 Optional Inputs

#### Mastering Config (`config.mastering` in manifest)

Loudness targets, format options, and metadata overrides. See Section 5.

#### Cover Art

```yaml
# In manifest or config/overrides.yaml
cover_art:
  path: "assets/cover-art.jpg"    # JPEG or PNG
  # Recommended: 3000x3000 px (Apple Podcasts requirement)
  # Minimum: 1400x1400 px
  # Maximum file size: 512 KB (will be resized/compressed if larger)
```

---

## 3. Outputs

All outputs are written to `artifacts/mastering/`.

### 3.1 Mastered Audio — Broadcast (`episode.mp3`)

Distribution-ready MP3 for podcast feeds.

| Property | Value |
|----------|-------|
| Format | MP3 (LAME encoder) |
| Bitrate | 192 kbps CBR (configurable) |
| Sample rate | 44.1 kHz |
| Channels | Stereo (or mono if configured) |
| Loudness | -16 LUFS integrated |
| True peak | ≤ -1 dBTP |
| Metadata | Full ID3v2.4 tags embedded |
| Chapter markers | ID3 CHAP frames (if supported) |
| Cover art | Embedded APIC frame |

### 3.2 Mastered Audio — Archive (`episode.wav`)

Lossless archive master.

| Property | Value |
|----------|-------|
| Format | WAV (PCM) |
| Sample rate | 48 kHz |
| Bit depth | 24-bit |
| Channels | Stereo |
| Loudness | -16 LUFS integrated |
| True peak | ≤ -1 dBTP |

### 3.3 Show Notes (`show-notes.md` + `show-notes.html`)

Formatted episode show notes for publishing platforms.

**Markdown** (`show-notes.md`):
```markdown
# Episode 42: AI Audio Processing

Alice and Bob discuss the state of AI-powered audio processing, focusing on
Whisper for transcription and new approaches to automated podcast editing.

## Timestamps
- 00:00 — Introduction
- 00:45 — What is Whisper?
- 12:30 — Word-level timestamps and accuracy
...

## Links
- [OpenAI Whisper](https://github.com/openai/whisper)
- [Auphonic](https://auphonic.com)
```

**HTML** (`show-notes.html`): Same content rendered as HTML for platforms that accept HTML descriptions.

### 3.4 Episode Metadata File (`metadata.json`)

Complete metadata record for the episode, including all ID3 fields, for reference and automation.

```json
{
  "version": "1.0",
  "id3": {
    "title": "AI Audio Processing",
    "artist": "Alice",
    "album": "Tech Talk Weekly",
    "track_number": 42,
    "year": 2026,
    "genre": "Podcast",
    "comment": "Alice and Bob discuss AI-powered audio processing.",
    "album_artist": "Tech Talk Weekly",
    "publisher": null,
    "url": null,
    "cover_art": "assets/cover-art.jpg",
    "chapters": [
      { "title": "Introduction", "start_ms": 0, "end_ms": 45200 },
      { "title": "What is Whisper?", "start_ms": 45200, "end_ms": 750000 }
    ]
  },
  "loudness": {
    "integrated_lufs": -16.0,
    "true_peak_dbtp": -1.2,
    "loudness_range_lu": 5.8
  },
  "file_info": {
    "mp3_path": "artifacts/mastering/episode.mp3",
    "mp3_size_bytes": 76500000,
    "mp3_duration_seconds": 3210.8,
    "wav_path": "artifacts/mastering/episode.wav",
    "wav_size_bytes": 553000000
  }
}
```

### 3.5 Publishing Package (directory)

All deliverables assembled in a single directory, ready for upload.

```
artifacts/mastering/
├── episode.mp3           # Distribution MP3
├── episode.wav           # Archive WAV
├── show-notes.md         # Markdown show notes
├── show-notes.html       # HTML show notes
├── metadata.json         # Episode metadata
├── cover-art.jpg         # Cover art (resized copy)
└── chapters.txt          # Chapter markers in simple format
```

---

## 4. Processing Steps

### Step 1: Validate Input and Measure Source Loudness

```python
import subprocess
import json
import re

def measure_loudness(input_path: str) -> dict:
    """
    FFmpeg two-pass loudness measurement (Pass 1).
    Returns measured loudness parameters for Pass 2.
    """
    result = subprocess.run([
        "ffmpeg", "-i", input_path,
        "-af", "loudnorm=I=-16:TP=-1:LRA=11:print_format=json",
        "-f", "null", "-"
    ], capture_output=True, text=True)

    # Parse JSON from stderr
    stderr = result.stderr
    json_match = re.search(r'\{[^}]+\}', stderr, re.DOTALL)
    if not json_match:
        raise RuntimeError("Failed to parse loudnorm output")

    measurements = json.loads(json_match.group())
    return measurements
```

**Validate input:**
```
1. Verify mixed.wav exists
2. Probe with FFprobe: confirm WAV format, 48kHz, 24-bit, stereo
3. Measure duration — compare against expected duration from manifest
4. Run loudnorm Pass 1 to measure current loudness
5. Log: "Source loudness: -18.1 LUFS, true peak: -0.3 dBTP, LRA: 6.2 LU"
```

### Step 2: Loudness Normalization (Two-Pass Linear)

Apply EBU R128 loudness normalization to target -16 LUFS.

```python
def normalize_loudness(input_path: str, output_path: str,
                        measurements: dict,
                        target_i: float = -16.0,
                        target_tp: float = -1.0,
                        target_lra: float = 11.0) -> None:
    """
    FFmpeg two-pass linear loudness normalization (Pass 2).
    Uses measurements from Pass 1 for linear gain application.
    """
    subprocess.run([
        "ffmpeg", "-y", "-i", input_path,
        "-af", (
            f"loudnorm=I={target_i}:TP={target_tp}:LRA={target_lra}"
            f":measured_I={measurements['input_i']}"
            f":measured_TP={measurements['input_tp']}"
            f":measured_LRA={measurements['input_lra']}"
            f":measured_thresh={measurements['input_thresh']}"
            f":offset={measurements['target_offset']}"
            f":linear=true"
        ),
        "-c:a", "pcm_s24le",
        "-ar", "48000",
        output_path
    ], check=True, capture_output=True)
```

**Key parameters:**

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `I=-16` | -16 LUFS | Standard for podcast distribution (Apple, Spotify, EBU R128) |
| `TP=-1` | -1 dBTP | True-peak ceiling. ITU-R BS.1770 compliant (inter-sample peaks). |
| `LRA=11` | 11 LU | Set high to avoid unwanted compression. Typical speech LRA is 5-8 LU. |
| `linear=true` | — | Apply single linear gain offset. Preserves original dynamics. |

### Step 3: Encode to MP3

Encode the normalized WAV to MP3 using LAME.

```python
def encode_mp3(input_path: str, output_path: str,
                bitrate: int = 192, sample_rate: int = 44100,
                mono: bool = False) -> None:
    """Encode WAV to MP3 using libmp3lame."""
    channels = ["-ac", "1"] if mono else []
    subprocess.run([
        "ffmpeg", "-y", "-i", input_path,
        "-c:a", "libmp3lame",
        "-b:a", f"{bitrate}k",
        "-ar", str(sample_rate),
        *channels,
        "-id3v2_version", "4",     # Use ID3v2.4
        "-write_xing", "1",        # Write Xing/LAME header for accurate seeking
        output_path
    ], check=True, capture_output=True)
```

**Format decisions:**

| Decision | Choice | Rationale |
|----------|--------|-----------|
| CBR vs VBR | CBR | More reliable seeking in podcast players. File size is predictable. |
| Bitrate | 192 kbps | Generous for speech. 128 kbps is acceptable for mono speech. |
| Sample rate | 44.1 kHz | Standard for MP3 distribution. Down from 48kHz source. |
| ID3 version | v2.4 | Most modern players support it. v2.3 as fallback if needed. |

### Step 4: Produce Archive WAV

The archive master is the normalized WAV at original quality.

```python
def produce_archive_wav(normalized_wav_path: str, output_path: str) -> None:
    """
    Copy the normalized WAV as the archive master.
    No format conversion needed — just copy if already at target specs.
    """
    # If the normalized WAV is already 48kHz/24-bit, just copy
    shutil.copy2(normalized_wav_path, output_path)
```

### Step 5: Embed Metadata and Cover Art

Write ID3v2 tags, cover art, and chapter markers to the MP3.

```python
from mutagen.mp3 import MP3
from mutagen.id3 import (
    ID3, TIT2, TPE1, TALB, TRCK, TDRC, TCON,
    COMM, APIC, CHAP, CTOC, TIT2 as ChapterTitle
)

def embed_metadata(mp3_path: str, metadata: dict, cover_art_path: str = None,
                    chapters: list = None) -> None:
    """Embed ID3v2 tags, cover art, and chapter markers."""
    audio = MP3(mp3_path, ID3=ID3)

    # Create ID3 tag if it doesn't exist
    try:
        audio.add_tags()
    except Exception:
        pass  # Tags already exist

    tags = audio.tags

    # Basic metadata
    tags.add(TIT2(encoding=3, text=[metadata["title"]]))
    tags.add(TPE1(encoding=3, text=[metadata["artist"]]))
    tags.add(TALB(encoding=3, text=[metadata["album"]]))
    tags.add(TRCK(encoding=3, text=[str(metadata["track_number"])]))
    tags.add(TDRC(encoding=3, text=[str(metadata["year"])]))
    tags.add(TCON(encoding=3, text=["Podcast"]))
    tags.add(COMM(encoding=3, lang="eng", desc="",
                   text=[metadata.get("comment", "")]))

    # Cover art
    if cover_art_path:
        cover_art = prepare_cover_art(cover_art_path)
        mime = "image/jpeg" if cover_art_path.endswith(".jpg") else "image/png"
        tags.add(APIC(
            encoding=3,
            mime=mime,
            type=3,            # Front cover
            desc="Cover",
            data=cover_art
        ))

    # Chapter markers (ID3v2 CHAP frames)
    if chapters:
        # Table of contents
        child_ids = [f"chap{i}" for i in range(len(chapters))]
        tags.add(CTOC(
            element_id="toc",
            flags=3,  # Top-level, ordered
            child_element_ids=child_ids,
            sub_frames=[]
        ))

        duration_ms = int(metadata["duration_seconds"] * 1000)
        for i, chapter in enumerate(chapters):
            start_ms = int(chapter["time"] * 1000)
            # End time = next chapter start, or episode end
            end_ms = (int(chapters[i + 1]["time"] * 1000)
                      if i + 1 < len(chapters) else duration_ms)
            tags.add(CHAP(
                element_id=f"chap{i}",
                start_time=start_ms,
                end_time=end_ms,
                start_offset=0xFFFFFFFF,   # Not used
                end_offset=0xFFFFFFFF,     # Not used
                sub_frames=[TIT2(encoding=3, text=[chapter["title"]])]
            ))

    audio.save()
```

#### Cover Art Preparation

```python
from PIL import Image
import io

def prepare_cover_art(path: str, max_size_px: int = 3000,
                       min_size_px: int = 1400,
                       max_file_kb: int = 512) -> bytes:
    """
    Resize and compress cover art to meet podcast platform requirements.
    Apple Podcasts: 1400x1400 minimum, 3000x3000 maximum.
    """
    img = Image.open(path)

    # Ensure square
    if img.width != img.height:
        size = min(img.width, img.height)
        img = img.crop((0, 0, size, size))

    # Resize if needed
    if img.width > max_size_px:
        img = img.resize((max_size_px, max_size_px), Image.LANCZOS)
    elif img.width < min_size_px:
        # Upscale with warning
        img = img.resize((min_size_px, min_size_px), Image.LANCZOS)

    # Compress to JPEG under max file size
    quality = 95
    while quality >= 50:
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=quality)
        if buffer.tell() <= max_file_kb * 1024:
            return buffer.getvalue()
        quality -= 5

    # If still too large at quality 50, return it anyway with a warning
    return buffer.getvalue()
```

### Step 6: Generate Show Notes

Convert the content summary from Module 2 into final show notes.

```python
import markdown

def generate_show_notes(summary_md_path: str, chapters: list,
                         metadata: dict) -> tuple[str, str]:
    """
    Finalize show notes as Markdown and HTML.
    Add episode header, chapter timestamps, and footer.
    """
    with open(summary_md_path) as f:
        summary = f.read()

    # The summary from Module 2 already has most content.
    # Add a standard header and footer.
    final_md = f"""# {metadata['title']}

**{metadata['album']}** — Episode {metadata['track_number']}
**Date**: {metadata.get('recording_date', 'N/A')}
**Hosts**: {metadata['artist']}

---

{summary}

---

*Produced with PodAgent OS*
"""

    # Convert to HTML
    final_html = markdown.markdown(final_md, extensions=['tables', 'fenced_code'])

    return final_md, final_html
```

### Step 7: Verify Output Quality

Post-mastering quality gate — measure the final output to confirm compliance.

```python
def verify_output(mp3_path: str, wav_path: str,
                   target_lufs: float = -16.0,
                   target_tp: float = -1.0) -> dict:
    """
    Measure the mastered output and verify it meets targets.
    Returns verification results.
    """
    # Measure MP3
    result = subprocess.run([
        "ffmpeg", "-i", mp3_path,
        "-af", "ebur128=peak=true",
        "-f", "null", "-"
    ], capture_output=True, text=True)

    # Parse the summary from stderr
    measurements = parse_ebur128_summary(result.stderr)

    verification = {
        "integrated_lufs": measurements["I"],
        "true_peak_dbtp": measurements["peak"],
        "loudness_range_lu": measurements["LRA"],
        "lufs_on_target": abs(measurements["I"] - target_lufs) <= 0.5,
        "tp_within_ceiling": measurements["peak"] <= target_tp,
        "passed": True
    }

    if not verification["lufs_on_target"]:
        verification["passed"] = False
        verification["warning"] = (
            f"Integrated loudness {measurements['I']:.1f} LUFS "
            f"deviates from target {target_lufs} by more than 0.5 LU"
        )

    if not verification["tp_within_ceiling"]:
        verification["passed"] = False
        verification["warning"] = (
            f"True peak {measurements['peak']:.1f} dBTP "
            f"exceeds ceiling of {target_tp} dBTP"
        )

    return verification
```

> [ASSUMPTION] Verification tolerance is ±0.5 LU for integrated loudness. The two-pass linear normalization should hit the target exactly, but MP3 encoding can shift loudness slightly due to lossy compression. If verification fails, log a warning but do not block — the deviation is small enough to be inaudible.

### Step 8: Assemble Publishing Package and Write Outputs

```python
def assemble_package(output_dir: str = "artifacts/mastering/"):
    """Write all deliverables and update manifest."""

    # Write show notes
    write_atomic(f"{output_dir}/show-notes.md", show_notes_md)
    write_atomic(f"{output_dir}/show-notes.html", show_notes_html)

    # Write metadata
    write_atomic(f"{output_dir}/metadata.json", metadata_json)

    # Copy cover art (resized) to output
    if cover_art_path:
        with open(f"{output_dir}/cover-art.jpg", "wb") as f:
            f.write(cover_art_bytes)

    # Write simple chapter file (for platforms that don't support ID3 CHAP)
    with open(f"{output_dir}/chapters.txt", "w") as f:
        for chapter in chapters:
            time_str = format_timestamp(chapter["time"])
            f.write(f"{time_str} {chapter['title']}\n")

    # Update manifest
    manifest["pipeline"]["stages"]["mastering"]["status"] = "completed"
    manifest["pipeline"]["stages"]["mastering"]["completed_at"] = now_iso()
    manifest["pipeline"]["current_stage"] = "complete"
    write_atomic("manifest.yaml", manifest)
```

---

## 5. Configuration Options

All options live under `config.mastering` in the manifest.

| Option | Type | Default | Range | Description |
|--------|------|---------|-------|-------------|
| `target_lufs` | float | `-16.0` | -24 to -8 | Target integrated loudness (LUFS). -16 for podcasts, -14 for YouTube. |
| `true_peak_limit_dbtp` | float | `-1.0` | -3 to 0 | True-peak ceiling (dBTP). -1 is standard for podcast distribution. |
| `loudnorm_lra` | float | `11.0` | 5–20 | LRA target for loudnorm. Set high (11+) to avoid dynamic range compression. |
| `mp3_bitrate_kbps` | int | `192` | 64, 96, 128, 192, 256, 320 | MP3 encoding bitrate. 128 is fine for mono, 192 for stereo. |
| `mp3_sample_rate` | int | `44100` | 44100, 48000 | MP3 output sample rate. |
| `mp3_mono` | bool | `false` | — | Encode MP3 as mono (saves ~50% file size). |
| `output_formats` | list | `["mp3", "wav"]` | `mp3`, `wav`, `flac` | Which output formats to produce. |
| `cover_art_path` | string | `null` | File path or `null` | Path to cover art image. |
| `cover_art_max_px` | int | `3000` | 1400–3000 | Maximum cover art dimension (pixels). |
| `embed_chapters` | bool | `true` | — | Embed chapter markers in MP3 (ID3 CHAP frames). |
| `generate_html_notes` | bool | `true` | — | Generate HTML version of show notes. |
| `id3_genre` | string | `"Podcast"` | Any string | ID3 genre tag. |
| `id3_publisher` | string | `null` | Any string or `null` | ID3 publisher tag. |
| `id3_url` | string | `null` | URL or `null` | ID3 URL tag (link to podcast website). |
| `verify_output` | bool | `true` | — | Run post-mastering loudness verification. |

---

## 6. External Dependencies

| Dependency | Type | Purpose | Required | Fallback |
|-----------|------|---------|----------|----------|
| `ffmpeg` | System binary | Loudness measurement, normalization, MP3 encoding | Yes | None — hard dependency |
| `mutagen` | Python package | ID3 tag writing, chapter marker embedding | Yes | FFmpeg `-metadata` (limited, no chapters) |
| `Pillow` | Python package | Cover art resizing and compression | Optional | Skip cover art processing; embed as-is |
| `markdown` | Python package | Markdown → HTML conversion for show notes | Optional | Skip HTML show notes |

**FFmpeg must be compiled with `--enable-libmp3lame`** for MP3 encoding. Standard packages include this.

---

## 7. Error Handling

| Error | Detection | Recovery | User Impact |
|-------|-----------|----------|-------------|
| **Mixed WAV missing** | File existence check | Abort with error | Re-run mixing module |
| **Mixed WAV is wrong format** | FFprobe check | Attempt conversion. If fails, abort. | Slight delay for conversion |
| **Loudnorm Pass 1 fails** | FFmpeg non-zero exit | Retry once. If fails, use single-pass mode (degraded). | Slightly less accurate loudness |
| **Loudnorm Pass 2 fails** | FFmpeg non-zero exit | Retry once. If fails, abort. | Mastering cannot complete |
| **MP3 encoding fails** | FFmpeg non-zero exit | Check for libmp3lame. If missing, abort with install instructions. | User needs to install FFmpeg with LAME |
| **Mutagen tag writing fails** | Exception | Fall back to FFmpeg `-metadata`. Chapters and cover art not embedded. | Missing chapters/art in MP3 |
| **Cover art missing** | File not found | Skip cover art embedding. Log warning. | MP3 has no embedded artwork |
| **Cover art too small** | PIL check (< 1400px) | Upscale with warning. | Potentially blurry artwork |
| **Verification fails (loudness off)** | Measurement check | Log warning. Proceed — deviation is <1 LU and inaudible. | No user impact |
| **Verification fails (true peak)** | Measurement check | Re-run normalization with TP=-1.5 (more conservative). | Slight additional processing time |
| **Content summary missing** | File not found | Generate minimal show notes from manifest metadata only. | Less detailed show notes |
| **Disk full** | Write failure | Abort immediately. Do not update manifest. | Free disk space |
| **FLAC encoding requested** | Config check | Encode with FFmpeg `-c:a flac`. If fails, skip FLAC, produce WAV only. | Missing FLAC output |

---

## 8. Edge Cases

| Edge Case | Behavior |
|-----------|----------|
| **Already-normalized input** | Loudnorm Pass 1 measures -16 LUFS, offset ≈ 0. Pass 2 applies near-zero gain. Output ≈ input. Correct behavior. |
| **Very quiet input (< -30 LUFS)** | Loudnorm applies large gain boost. True-peak limiter may engage frequently. Log warning about source quality. |
| **Very loud input (> -8 LUFS)** | Loudnorm applies gain reduction. May sound different from original due to significant level change. Log info. |
| **Mono input** | Process as-is. If `mp3_mono: true`, output is mono MP3. If false, output is dual-mono stereo. |
| **No cover art** | MP3 has no APIC frame. Podcast players show default artwork. |
| **Cover art is PNG** | Convert to JPEG for embedding (smaller size, wider compatibility). Keep PNG if it has transparency (rare for podcast art). |
| **No chapters** | Skip CHAP/CTOC frames. MP3 is valid without chapters. |
| **Zero chapters from Module 2** | Add a single "Episode Start" chapter at 00:00. |
| **Very long episode (> 3 hours)** | Large MP3 files (>200 MB at 192kbps). Some hosting platforms have limits. Log warning if file exceeds 200 MB. |
| **FLAC requested** | Encode with FFmpeg. FLAC is lossless but larger. Useful for archival. |
| **Content summary has broken links** | Pass through as-is. Not this module's job to validate URLs. |
| **MP3 encoding shifts loudness** | Post-encoding verification detects this. If deviation > 0.5 LU, log warning. In practice, shift is typically < 0.2 LU. |
| **Multiple output formats** | Process sequentially: WAV first (copy from normalized), MP3 second, FLAC third. Each from the normalized WAV (not from each other). |

---

## 9. Performance Targets

| Operation | Target | Notes |
|-----------|--------|-------|
| Input validation + FFprobe | < 2 seconds | |
| Loudnorm Pass 1 (measure) | ~1x real-time | 1-hour episode ≈ 60 seconds |
| Loudnorm Pass 2 (normalize) | ~1x real-time | 1-hour episode ≈ 60 seconds |
| MP3 encoding | ~0.3x real-time | 1-hour episode ≈ 18 seconds |
| WAV copy | < 5 seconds | Simple file copy |
| FLAC encoding | ~0.5x real-time | 1-hour episode ≈ 30 seconds |
| Metadata embedding (mutagen) | < 2 seconds | |
| Cover art processing (PIL) | < 3 seconds | Resize + JPEG compression |
| Show notes generation | < 2 seconds | Markdown/HTML formatting |
| Output verification | ~1x real-time | Re-measure with ebur128 |
| **Total — 1-hour episode** | **~3-4 minutes** | Dominated by FFmpeg passes |

---

## 10. Example: Sample Input → Expected Output

### Input

- `mixed.wav`: 53:31, 48kHz, 24-bit, stereo, 553 MB
- `summary.md`: 5 chapters, 2 key quotes, 3 links
- Cover art: `assets/cover-art.jpg`, 3000×3000 px, 280 KB
- Config: defaults (-16 LUFS, -1 dBTP, 192kbps MP3)

### Processing

```
[10:30:00] Mastering started
[10:30:01] Validated mixed.wav — 53:31, 48kHz, 24-bit, stereo
[10:30:01] Loudness measurement (Pass 1)...
[10:30:55] Source loudness: -18.1 LUFS, true peak: -0.3 dBTP, LRA: 6.2 LU
[10:30:55] Loudness normalization (Pass 2, linear mode, target: -16 LUFS)...
[10:31:50] Normalization complete
[10:31:50] Encoding MP3 (192kbps CBR, 44.1kHz)...
[10:32:08] MP3 encoded — 76.5 MB
[10:32:08] Producing archive WAV (48kHz, 24-bit)...
[10:32:09] Archive WAV produced — 553 MB
[10:32:09] Processing cover art (3000x3000 JPEG, 280 KB — within limits)
[10:32:10] Embedding metadata: ID3v2.4 tags, 5 chapters, cover art
[10:32:11] Metadata embedded
[10:32:11] Generating show notes (Markdown + HTML)
[10:32:12] Show notes generated
[10:32:12] Verifying output loudness...
[10:33:05] Verification passed: -16.0 LUFS, -1.2 dBTP, LRA 5.8 LU
[10:33:05] Assembling publishing package
[10:33:06] Mastering complete in 3m06s.
```

### Output

```
artifacts/mastering/
├── episode.mp3          76.5 MB   192kbps, 44.1kHz, -16 LUFS, ID3v2.4
├── episode.wav          553 MB    48kHz/24-bit, -16 LUFS
├── show-notes.md        2.1 KB    Markdown
├── show-notes.html      3.4 KB    HTML
├── metadata.json        1.8 KB    Full metadata record
├── cover-art.jpg        280 KB    3000x3000 JPEG
└── chapters.txt         0.2 KB    Simple chapter list
```

**Manifest updated:**
```yaml
pipeline:
  current_stage: "complete"
  stages:
    mastering:
      status: "completed"
      started_at: "2026-02-25T10:30:00Z"
      completed_at: "2026-02-25T10:33:06Z"
      gate_approved: null   # awaiting final review
```
