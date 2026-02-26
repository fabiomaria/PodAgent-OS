# Module Spec: Audio Processing & Mixing

> **Status**: Draft
> **Last Updated**: 2026-02-25
> **Author**: Spec Writer Agent
> **Position in Pipeline**: Module 3 of 4 — receives EDL from Editing, produces mixed audio for Mastering

---

## 1. Module Overview

The Audio Processing & Mixing module takes the EDL from Module 2 and the raw source audio tracks, then produces a single mixed-down WAV file. It executes the edit decisions (cuts, rearrangements), applies per-track audio processing (noise reduction, compression, de-essing), and handles multi-track mixing (ducking, crossfades, music beds).

This module **faithfully executes the EDL** — it does not make editorial decisions. If the EDL says keep a segment, it stays. If the EDL says cut, it goes. Audio processing decisions (noise reduction level, compression) are configurable but do not change what content is included.

This module does not perform final loudness normalization — that's Module 4's job. The mixed output should be clean, well-balanced audio at native levels.

---

## 2. Inputs

### 2.1 Required Inputs

#### Raw Audio Tracks (`tracks/`)

The original source audio files. These are the same files ingested in Module 1 — never modified.

| Field | Requirement |
|-------|------------|
| Format | WAV or FLAC (MP3 accepted but not recommended — lossy source degrades quality) |
| Sample rate | 44.1kHz or 48kHz (must match across tracks, or alignment map specifies resampling) |
| Channels | Mono (one speaker per track) |

#### Edit Decision List (`artifacts/editing/edit-list.json`)

The JSON sidecar from Module 2. Contains all edit decisions with source timestamps, track references, transition types, and ordering.

> [ASSUMPTION] The module reads the JSON sidecar (not the CMX 3600 EDL) for internal processing, since the JSON carries richer metadata (confidence, rationale, per-segment references). The CMX 3600 EDL is for DAW export only.

#### Alignment Map (`artifacts/ingestion/alignment.json`)

Track offsets and timing information from Module 1. Used to correctly position multi-track audio on the shared timeline.

### 2.2 Optional Inputs

#### Mixing Config (`config.mixing` in manifest)

Audio processing parameters. See Section 5 for all options.

#### Music Beds

Intro/outro music files for insertion.

```yaml
# In manifest or config/overrides.yaml
music:
  intro:
    path: "assets/intro-music.wav"
    duration_seconds: 15.0          # fade in/out within this duration
    duck_under_speech: true
  outro:
    path: "assets/outro-music.wav"
    duration_seconds: 20.0
    duck_under_speech: false         # plays at full level after speech ends
```

---

## 3. Outputs

All outputs are written to `artifacts/mixing/`.

### 3.1 Mixed Audio (`mixed.wav`)

Single stereo WAV file with all edits applied and tracks mixed down.

| Property | Value |
|----------|-------|
| Format | WAV (PCM) |
| Sample rate | 48kHz |
| Bit depth | 24-bit |
| Channels | Stereo (speakers panned center, or slight L/R if configured) |
| Loudness | Native levels (not normalized — Module 4 handles that) |

### 3.2 Mixing Log (`mixing-log.json`)

Complete record of every processing step applied.

```json
{
  "version": "1.0",
  "episode_id": "my-podcast-ep42",
  "output_file": "artifacts/mixing/mixed.wav",
  "output_duration_seconds": 3210.8,
  "output_sample_rate": 48000,
  "output_bit_depth": 24,
  "processing_chain": [
    {
      "track": "tracks/alice.wav",
      "steps": [
        {
          "step": "noise_reduction",
          "provider": "ffmpeg",
          "filter": "afftdn=nf=-25",
          "parameters": { "noise_floor_db": -25 }
        },
        {
          "step": "compression",
          "filter": "acompressor=threshold=-20dB:ratio=3:attack=10:release=200",
          "parameters": {
            "threshold_db": -20,
            "ratio": "3:1",
            "attack_ms": 10,
            "release_ms": 200
          }
        },
        {
          "step": "de_essing",
          "enabled": false
        }
      ]
    }
  ],
  "edl_events_applied": 24,
  "crossfades_applied": 23,
  "ducking_regions": 45,
  "music_beds_inserted": { "intro": true, "outro": true },
  "processing_time_seconds": 142.5
}
```

### 3.3 Waveform Preview (`waveform.png`)

Visual overview of the mixed audio for Gate 3 review.

Generated via:
```bash
ffmpeg -i mixed.wav -filter_complex \
  "showwavespic=s=1920x400:colors=0x4a9eff" \
  -frames:v 1 waveform.png
```

---

## 4. Processing Steps

### Step 1: Parse EDL and Build Edit Timeline

Read the JSON sidecar and construct an in-memory timeline of keep/cut regions.

```python
def build_timeline(edl_sidecar: dict, alignment: dict) -> list:
    """
    Build an ordered list of audio regions to include in the mix.
    Each region references a source track, start/end times, and transitions.
    """
    timeline = []
    for edit in edl_sidecar["edits"]:
        if edit["type"] != "keep":
            continue

        track_path = edit["source_track"]
        offset_ms = get_track_offset(alignment, track_path)

        region = {
            "track": track_path,
            "source_start": edit["source_start"],
            "source_end": edit["source_end"],
            "record_start": edit["record_start"],
            "record_end": edit["record_end"],
            "speaker": edit["speaker"],
            "offset_ms": offset_ms
        }
        timeline.append(region)

    # Sort by record_start (output timeline order)
    timeline.sort(key=lambda r: r["record_start"])
    return timeline
```

### Step 2: Extract Audio Regions from Source Tracks

For each keep region in the timeline, extract the corresponding audio from the source track.

```python
import subprocess

def extract_region(track_path: str, start: float, end: float,
                   output_path: str):
    """Extract a region from a source track using FFmpeg."""
    duration = end - start
    subprocess.run([
        "ffmpeg", "-y",
        "-ss", str(start),
        "-i", track_path,
        "-t", str(duration),
        "-c:a", "pcm_s24le",    # 24-bit PCM
        "-ar", "48000",          # ensure consistent sample rate
        "-ac", "1",              # mono (per-track)
        output_path
    ], check=True, capture_output=True)
```

Extracted regions are written to a temp directory: `artifacts/mixing/tmp/region-001.wav`, etc.

### Step 3: Per-Track Audio Processing

Apply audio processing to each extracted region via a configurable filter chain.

#### 3a. Noise Reduction

```python
# Provider: FFmpeg (default)
def apply_noise_reduction_ffmpeg(input_path: str, output_path: str,
                                  noise_floor_db: int = -25):
    """
    Apply FFmpeg's afftdn (adaptive FFT denoiser).
    noise_floor_db: estimated noise floor. -25 is moderate, -20 is aggressive.
    """
    subprocess.run([
        "ffmpeg", "-y", "-i", input_path,
        "-af", f"afftdn=nf={noise_floor_db}",
        "-c:a", "pcm_s24le",
        output_path
    ], check=True, capture_output=True)

# Provider: Auphonic API (premium)
def apply_noise_reduction_auphonic(input_path: str, output_path: str,
                                     api_key: str):
    """Send audio to Auphonic for processing. Returns processed file."""
    # 1. Create production via POST /api/simple/productions.json
    # 2. Upload audio file
    # 3. Start production
    # 4. Poll for completion
    # 5. Download result
    ...

# Provider: Dolby.io (premium)
def apply_noise_reduction_dolby(input_path: str, output_path: str,
                                  api_key: str):
    """Send audio to Dolby.io Media API for noise reduction."""
    # POST https://api.dolby.com/media/enhance
    ...
```

**Provider interface:**
```python
class NoiseReductionProvider:
    def process(self, input_path: str, output_path: str, **kwargs) -> None:
        raise NotImplementedError

class FFmpegNoiseReduction(NoiseReductionProvider):
    def process(self, input_path, output_path, noise_floor_db=-25):
        apply_noise_reduction_ffmpeg(input_path, output_path, noise_floor_db)

class AuphonicNoiseReduction(NoiseReductionProvider):
    def process(self, input_path, output_path, api_key=None):
        apply_noise_reduction_auphonic(input_path, output_path, api_key)
```

#### 3b. Dynamic Range Compression

Even out volume differences within a speaker's track.

```bash
ffmpeg -i input.wav \
  -af "acompressor=threshold=-20dB:ratio=3:attack=10:release=200:makeup=2dB" \
  output.wav
```

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `threshold` | -20 dB | -40 to 0 | Level above which compression kicks in |
| `ratio` | 3:1 | 1.5:1 to 10:1 | Compression ratio |
| `attack` | 10 ms | 1–100 | How fast compression engages |
| `release` | 200 ms | 50–1000 | How fast compression releases |
| `makeup` | 2 dB | 0–12 | Gain added after compression |

#### 3c. De-essing (Optional)

Reduce sibilance ("s" and "sh" harshness). Disabled by default.

```bash
ffmpeg -i input.wav \
  -af "equalizer=f=7000:t=q:w=2:g=-6" \
  output.wav
```

> [ASSUMPTION] FFmpeg's EQ-based de-essing is a rough approximation. For production-quality de-essing, a dedicated sidechain compressor targeting 4–8kHz is needed. This may require `sox` or a custom DSP implementation. For MVP, the EQ approach is acceptable.

### Step 4: Multi-Track Mixing

Combine processed per-track regions into a single stereo mix.

#### 4a. Auto-Ducking

When the primary speaker (host) is talking, reduce the volume of other tracks.

```python
def generate_ducking_automation(timeline: list, primary_speaker: str,
                                 ducking_db: float = -6.0) -> list:
    """
    Generate volume automation for auto-ducking.
    Returns list of (track, start, end, gain_db) tuples.
    """
    automation = []
    for region in timeline:
        if region["speaker"] == primary_speaker:
            # Duck all other tracks during this region
            for other_region in timeline:
                if (other_region["speaker"] != primary_speaker
                    and regions_overlap(region, other_region)):
                    automation.append({
                        "track": other_region["track"],
                        "start": max(region["record_start"],
                                     other_region["record_start"]),
                        "end": min(region["record_end"],
                                   other_region["record_end"]),
                        "gain_db": ducking_db,
                        "fade_in_ms": 50,
                        "fade_out_ms": 150
                    })
    return automation
```

**Ducking implementation via FFmpeg's `sidechaincompress` or volume automation:**

```bash
# Simple approach: apply volume envelope to secondary track
ffmpeg -i bob_processed.wav \
  -af "volume='if(between(t,10.5,15.2),-6dB,0dB)':eval=frame" \
  bob_ducked.wav
```

For complex ducking with many regions, generate a volume automation filter string dynamically.

#### 4b. Crossfade at Edit Points

Apply crossfades at every edit boundary to avoid clicks/pops.

```python
def apply_crossfade(region_a_path: str, region_b_path: str,
                     output_path: str, crossfade_ms: int = 50):
    """Crossfade between two consecutive audio regions."""
    crossfade_seconds = crossfade_ms / 1000.0
    subprocess.run([
        "ffmpeg", "-y",
        "-i", region_a_path,
        "-i", region_b_path,
        "-filter_complex",
        f"acrossfade=d={crossfade_seconds}:c1=tri:c2=tri",
        output_path
    ], check=True, capture_output=True)
```

**Crossfade curve**: Triangular (linear) by default. Configurable to equal-power (`c1=exp:c2=exp`) for smoother transitions.

#### 4c. Music Bed Insertion

If intro/outro music is configured, mix it under/after speech.

```python
def mix_music_bed(speech_path: str, music_path: str, output_path: str,
                   music_start: float, music_duration: float,
                   music_volume_db: float = -12.0,
                   duck_under_speech: bool = True):
    """
    Mix a music bed under or after speech audio.
    If duck_under_speech, the music fades down when speech is present.
    """
    if duck_under_speech:
        # Use sidechaincompress: speech triggers music ducking
        filter_complex = (
            f"[1:a]atrim=0:{music_duration},volume={music_volume_db}dB[music];"
            f"[music][0:a]sidechaincompress=threshold=-30dB:ratio=6:attack=50:release=500[ducked];"
            f"[0:a][ducked]amix=inputs=2:duration=first"
        )
    else:
        # Simple concat: speech then music
        filter_complex = (
            f"[0:a][1:a]concat=n=2:v=0:a=1"
        )

    subprocess.run([
        "ffmpeg", "-y",
        "-i", speech_path,
        "-i", music_path,
        "-filter_complex", filter_complex,
        output_path
    ], check=True, capture_output=True)
```

### Step 5: Mix-Down to Stereo

Combine all processed tracks into a single stereo file.

```python
def mixdown(track_paths: list, output_path: str,
            pan_positions: dict = None):
    """
    Mix multiple mono tracks into a single stereo WAV.
    pan_positions: {"alice": 0.0, "bob": 0.0}  # 0.0 = center
    """
    inputs = []
    filter_parts = []

    for i, path in enumerate(track_paths):
        inputs.extend(["-i", path])
        pan = pan_positions.get(path, 0.0) if pan_positions else 0.0
        # Pan: 0.0 = center, -1.0 = full left, 1.0 = full right
        filter_parts.append(f"[{i}:a]stereotools=mpan={pan}[t{i}]")

    # Mix all tracks
    mix_inputs = "".join(f"[t{i}]" for i in range(len(track_paths)))
    filter_parts.append(
        f"{mix_inputs}amix=inputs={len(track_paths)}:duration=longest:normalize=0"
    )

    filter_complex = ";".join(filter_parts)

    cmd = ["ffmpeg", "-y"] + inputs + [
        "-filter_complex", filter_complex,
        "-c:a", "pcm_s24le",
        "-ar", "48000",
        output_path
    ]
    subprocess.run(cmd, check=True, capture_output=True)
```

> [ASSUMPTION] For most podcast use cases, both speakers are panned center (mono-summed to stereo). Optional slight panning (host at -0.1, guest at +0.1) can add subtle spatial separation.

### Step 6: Generate Waveform Preview and Write Outputs

```python
# Generate waveform image
subprocess.run([
    "ffmpeg", "-y", "-i", "artifacts/mixing/mixed.wav",
    "-filter_complex", "showwavespic=s=1920x400:colors=0x4a9eff",
    "-frames:v", "1",
    "artifacts/mixing/waveform.png"
], check=True, capture_output=True)

# Write mixing log
write_atomic("artifacts/mixing/mixing-log.json", mixing_log)

# Clean up temp files
shutil.rmtree("artifacts/mixing/tmp/")

# Update manifest
manifest["pipeline"]["stages"]["mixing"]["status"] = "completed"
manifest["pipeline"]["stages"]["mixing"]["completed_at"] = now_iso()
write_atomic("manifest.yaml", manifest)
```

---

## 5. Configuration Options

All options live under `config.mixing` in the manifest.

| Option | Type | Default | Range | Description |
|--------|------|---------|-------|-------------|
| `noise_reduction_provider` | string | `"ffmpeg"` | `ffmpeg`, `auphonic`, `dolby`, `none` | Which provider to use for noise reduction. |
| `noise_floor_db` | int | `-25` | -40 to -10 | Noise floor estimate for FFmpeg denoiser. Lower = more aggressive. |
| `compression_enabled` | bool | `true` | — | Apply dynamic range compression per track. |
| `compression_threshold_db` | int | `-20` | -40 to 0 | Compressor threshold. |
| `compression_ratio` | float | `3.0` | 1.5–10.0 | Compression ratio. |
| `compression_attack_ms` | int | `10` | 1–100 | Compressor attack time. |
| `compression_release_ms` | int | `200` | 50–1000 | Compressor release time. |
| `de_essing_enabled` | bool | `false` | — | Apply de-essing filter. |
| `crossfade_duration_ms` | int | `50` | 0–500 | Crossfade duration at edit points. 0 = hard cut. |
| `crossfade_curve` | string | `"tri"` | `tri`, `exp`, `log` | Crossfade curve shape. |
| `ducking_enabled` | bool | `true` | — | Auto-duck secondary tracks when primary speaks. |
| `ducking_threshold_db` | float | `-6.0` | -20 to 0 | How much to reduce ducked tracks (dB). |
| `ducking_fade_in_ms` | int | `50` | 10–500 | Ducking fade-in time. |
| `ducking_fade_out_ms` | int | `150` | 50–1000 | Ducking fade-out time. |
| `primary_speaker` | string | `null` | Speaker name or `null` | Who is the primary speaker for ducking. `null` = auto-detect (host role). |
| `output_sample_rate` | int | `48000` | 44100, 48000 | Output sample rate. |
| `output_bit_depth` | int | `24` | 16, 24, 32 | Output bit depth. |
| `pan_enabled` | bool | `false` | — | Apply slight stereo panning per speaker. |
| `pan_spread` | float | `0.1` | 0.0–0.5 | Panning amount (0.0 = center, 0.5 = hard L/R). |
| `music_intro_path` | string | `null` | File path or `null` | Path to intro music file. |
| `music_outro_path` | string | `null` | File path or `null` | Path to outro music file. |
| `music_volume_db` | float | `-12.0` | -30 to 0 | Music bed volume relative to speech. |

---

## 6. External Dependencies

| Dependency | Type | Purpose | Required | Fallback |
|-----------|------|---------|----------|----------|
| `ffmpeg` | System binary | All audio processing, filtering, mixing, encoding | Yes | None — hard dependency |
| `numpy` | Python package | Volume automation calculation | Yes | Could be avoided with pure Python |
| `Pillow` or `ffmpeg` | Python/System | Waveform image generation | Optional | Skip waveform preview |
| `auphonic` client | HTTP API | Premium noise reduction | Optional | FFmpeg `afftdn` |
| `dolby.io` client | HTTP API | Premium noise reduction | Optional | FFmpeg `afftdn` |

**FFmpeg must be compiled with:**
- `--enable-libmp3lame` (for MP3 in Module 4)
- Filters: `afftdn`, `acompressor`, `acrossfade`, `sidechaincompress`, `amix`, `showwavespic`

Standard FFmpeg packages (Homebrew, apt) include all of these.

---

## 7. Error Handling

| Error | Detection | Recovery | User Impact |
|-------|-----------|----------|-------------|
| **Source audio file missing** | File existence check | Abort with clear error | Re-run ingestion or fix file paths |
| **EDL sidecar missing** | File existence check | Abort | Re-run editing module |
| **EDL references non-existent track** | Path validation | Abort with error listing the bad reference | Fix EDL or manifest |
| **FFmpeg processing fails** | Non-zero exit code | Log stderr, retry once. If still fails, skip that processing step (e.g., skip noise reduction, apply others). | Slightly lower quality on affected track |
| **Auphonic/Dolby API error** | HTTP error | Fall back to FFmpeg local processing. Log warning. | Lower quality noise reduction but pipeline continues |
| **Auphonic/Dolby API timeout** | Timeout after 5 min | Fall back to FFmpeg. | Same as above |
| **Crossfade fails** | FFmpeg error (e.g., regions too short) | Use hard cut instead (0ms crossfade). Log warning. | Possible click at that edit point |
| **Music bed file missing** | File existence check | Skip music insertion. Log warning. | No intro/outro music |
| **Output WAV exceeds disk space** | Write failure | Abort immediately. Do not update manifest. | Free disk space, re-run |
| **Ducking produces silence** | Post-mix analysis (RMS check) | Reduce ducking amount by 50%, re-mix. | Slightly louder background tracks |
| **Mixed output is silent** | RMS of output < -60 dBFS | Abort with error. Likely an FFmpeg filter chain bug. | Investigate and fix |

---

## 8. Edge Cases

| Edge Case | Behavior |
|-----------|----------|
| **Single track (no multi-track)** | No ducking, no multi-track mixing. Process the single track and output as stereo (mono duplicated to L+R). |
| **Empty EDL (no edits)** | All source audio is "keep." Process the full tracks with noise reduction/compression and mix down. |
| **Very short regions (< 100ms)** | Skip crossfade for regions shorter than 2× crossfade duration. Use hard cut. |
| **Overlapping regions in EDL** | Two regions in the EDL overlap in record time. Mix them (sum), don't overwrite. This handles crosstalk regions. |
| **24-bit source, 16-bit source mixed** | Normalize all to 24-bit before processing. Log the bit depth conversion. |
| **Music bed longer than speech** | Trim music to match speech duration. Fade out music at speech end. |
| **Music bed shorter than intro** | Loop music or fade out early. Log warning. |
| **8 tracks** | Mix all 8. Ducking logic applies to all non-primary tracks. FFmpeg `amix` handles arbitrary input count. |
| **Track with no keep regions** | Skip entirely. Do not include in the mix. |
| **Very long episode (> 3 hours)** | Process in segments to manage memory. FFmpeg streams audio and handles this natively. |
| **Source is MP3 (lossy)** | Process as-is but log warning: "Source is lossy (MP3). Quality may be degraded. WAV or FLAC source recommended." |
| **All processing disabled** | If noise reduction, compression, de-essing, and ducking are all disabled, the module only applies EDL cuts and crossfades. Minimal processing, fast execution. |

---

## 9. Performance Targets

| Operation | Target (per minute of mixed output) | Notes |
|-----------|-------------------------------------|-------|
| EDL parsing | < 1 second total | JSON parsing |
| Region extraction | ~2 seconds | FFmpeg seek + copy |
| Noise reduction (FFmpeg) | ~3 seconds | `afftdn` processes faster than real-time |
| Noise reduction (Auphonic) | ~30-60 seconds | Depends on API queue + upload/download |
| Compression | ~1 second | `acompressor` is very fast |
| Ducking automation | < 1 second total | Calculation only |
| Crossfades | ~1 second per crossfade | Typically 20-50 crossfades |
| Mix-down | ~3 seconds | `amix` filter |
| Waveform generation | ~5 seconds total | `showwavespic` |
| **Total (FFmpeg provider)** | **~10 seconds per minute** | ~10 min for 1-hour episode |
| **Total (Auphonic provider)** | **~60 seconds per minute** | ~60 min for 1-hour episode (API-bound) |

---

## 10. Example: Sample Input → Expected Output

### Input

- `edit-list.json`: 24 edits (18 auto-applied cuts, 6 human-approved)
- Source tracks: `alice.wav` (64:02), `bob.wav` (64:00)
- Edited duration target: 53:31 (from Module 2)
- Config: FFmpeg noise reduction, compression enabled, ducking -6dB

### Processing

```
[10:20:00] Mixing started
[10:20:01] Parsed EDL: 24 edits, 18 keep regions per track
[10:20:01] Extracting audio regions (36 regions from 2 tracks)...
[10:20:15] Regions extracted to artifacts/mixing/tmp/
[10:20:15] Applying noise reduction (FFmpeg afftdn, nf=-25)...
[10:22:45] Noise reduction complete (36 regions, 150s)
[10:22:45] Applying compression (threshold=-20dB, ratio=3:1)...
[10:23:20] Compression complete
[10:23:20] Generating ducking automation (45 ducking regions)
[10:23:20] Applying crossfades (23 edit points, 50ms triangular)...
[10:23:45] Crossfades applied
[10:23:45] Inserting intro music bed (15s, ducked under speech)
[10:23:48] Inserting outro music (20s, full level)
[10:23:50] Mixing down to stereo (2 tracks → 1 stereo WAV)...
[10:24:05] Mix-down complete
[10:24:05] Generating waveform preview...
[10:24:10] Writing artifacts
[10:24:10] Mixing complete in 4m10s. Awaiting Gate 3 review.
```

### Output

- `artifacts/mixing/mixed.wav` — 53:31, 48kHz, 24-bit, stereo, 553 MB
- `artifacts/mixing/mixing-log.json` — full processing chain documented
- `artifacts/mixing/waveform.png` — 1920×400 waveform overview
