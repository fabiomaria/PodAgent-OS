# PodAgent OS — P0 Technology Research Findings

> **Status**: Draft
> **Last Updated**: 2026-02-25
> **Author**: Researcher Agent
> **Scope**: P0 research questions — must-know before architecture is finalized

---

## 1. Whisper Capabilities

### Question
Does Whisper support word-level timestamps? Speaker diarization? What are the local vs API tradeoffs?

### Finding

**Word-level timestamps**: Yes, supported across all major implementations.
- `faster-whisper`: `word_timestamps=True` — returns per-word start/end times
- `whisper.cpp`: `--max-len 1` for token-level output
- OpenAI API: `timestamp_granularities=["word"]` with `response_format="verbose_json"`
- Accuracy: ±50–200ms depending on speech clarity. Derived from cross-attention weights aligned to ~30ms frames. `large-v3` produces noticeably better alignment than smaller models.

**Speaker diarization**: Whisper does NOT natively support diarization. Must be combined with a dedicated pipeline:

| Approach | Quality (DER) | Complexity | Cost |
|----------|--------------|------------|------|
| `pyannote.audio 3.1` + `faster-whisper` | ~3-8% (podcast) | Medium | Free (local GPU) |
| `whisperX` (integrated: whisper + pyannote + wav2vec2) | ~3-8% (podcast) | Low | Free (local GPU) |
| AssemblyAI (commercial) | ~5-10% | Very Low | $0.65/hr |

**Language support**: 99 languages. English/Spanish/French/German/Japanese WER <10%. Auto-detects language from first 30 seconds.

**Local vs API comparison**:

| Dimension | OpenAI Whisper API | faster-whisper (GPU) | whisper.cpp (Metal) |
|-----------|--------------------|---------------------|-------------------|
| Speed (1hr audio) | ~1-3 min | ~3-8 min | ~15-25 min |
| Accuracy | Very good (~5-8% WER) | Best (`large-v3`: ~3-5% WER) | Same as faster-whisper |
| Cost | $0.006/min ($0.36/hr) | Free + hardware | Free + hardware |
| GPU required | No (cloud) | Yes (CUDA) | No (Apple Metal native) |
| VRAM needed | N/A | ~5-6 GB (float16) | ~3-4 GB (quantized) |
| File size limit | 25 MB | Unlimited | Unlimited |
| Diarization | None | Via pyannote | Via pyannote |

**`large-v3-turbo`** (distilled, 4 decoder layers): ~6-8x faster than `large-v3` with only 1-3% WER degradation. Best speed/quality tradeoff for production.

### Recommendation

- **Primary**: `faster-whisper` with `large-v3-turbo` on Linux/CUDA, or `whisper.cpp` with `large-v3-turbo` on macOS/Metal
- **Diarization**: `whisperX` (integrates faster-whisper + pyannote 3.1 + wav2vec2 forced alignment)
- **Fallback**: OpenAI Whisper API when local GPU is unavailable

### Gotchas

- OpenAI API's 25 MB limit requires splitting long podcast files — split at silence points, not mid-sentence
- `faster-whisper` does NOT support Apple Silicon GPU (MPS) — use `whisper.cpp` on Mac
- `pyannote.audio` requires a HuggingFace token and license agreement acceptance
- Speaker labels are arbitrary (`SPEAKER_00`, `SPEAKER_01`) — need post-processing to map to "Host"/"Guest"
- Whisper hallucinates on silence/music segments — use VAD to skip non-speech
- Diarization adds ~0.3-0.5x real-time processing on top of transcription
- Always pass `language` parameter explicitly to avoid auto-detection errors

### Performance (1-hour podcast, complete pipeline)

| Setup | Total Time |
|-------|-----------|
| faster-whisper + pyannote (RTX 4090) | ~10-15 min |
| whisperX integrated (RTX 4090) | ~8-12 min |
| whisper.cpp + pyannote (M2 Pro) | ~25-40 min |
| OpenAI API + local diarization (M2 Pro) | ~20-30 min |

---

## 2. EDL / AAF / OMF Format Support

### Question
Which format has the best DAW compatibility? Can we programmatically generate them? What libraries exist?

### Finding

**DAW compatibility matrix**:

| DAW | CMX 3600 EDL | AAF | OMF |
|-----|:-----------:|:---:|:---:|
| Pro Tools | Import (limited) | Full native | Import (legacy) |
| Adobe Audition | Import | Import (linked media) | No |
| DaVinci Resolve | Import/Export | Import/Export (Fairlight) | No |
| Reaper | Via SWS extension | Limited via extension | No |
| Audacity | No | No | No |
| Logic Pro | No | Import (limited) | No |
| Hindenburg | No | Import (limited) | No |

**Format capabilities**:

| Capability | CMX 3600 EDL | AAF | OMF |
|-----------|:-----------:|:---:|:---:|
| Simple cuts | Yes | Yes | Yes |
| Crossfades | Yes (limited) | Yes (parametric) | Yes |
| Volume automation | No | Yes | Basic |
| Multi-track (>2) | No (workaround: 1 EDL/track) | Yes (unlimited) | Yes |
| Sample-accurate | No (frame-accurate only) | Yes | Yes |
| Metadata/comments | Minimal (* comments) | Rich, extensible | Limited |
| Human-readable | Yes (plain text) | No (binary/OLE) | No (binary) |
| Embedded media | No (references only) | Optional | Always embedded |

**CMX 3600 specific limitations**:
- Max 999 events (sufficient for podcast editing)
- 8-character reel name limit (use mapping table)
- Max 2 audio channels natively (workaround: 1 EDL per speaker track)
- Frame-accurate only: at 30fps = ~33ms resolution (masked by 50ms crossfades)
- Transition types: Cut (`C`), Dissolve (`D xxx`) only. No parametric curves.

**Programmatic generation**:

| Library | Language | EDL | AAF | Notes |
|---------|----------|:---:|:---:|-------|
| `opentimelineio` (OTIO) | Python | Read/Write | Read only | Pixar/Academy Software Foundation. Gold standard. |
| `pyaaf2` | Python | — | Read/Write | Only viable Python AAF library. |
| `python-edl` / `edl` | Python | Read/Write | — | Lightweight, focused. |
| `timecode` | Python | Helper | Helper | SMPTE timecode arithmetic. |
| `edl-genius` | Node.js | Read (partial) | — | No mature JS AAF library exists. |

**DIY EDL generation** is trivial — CMX 3600 is plain text, ~50-100 lines of code.

**OMF**: Deprecated. No maintained libraries. Do not use.

### Recommendation

**MVP (P0)**: CMX 3600 EDL + JSON sidecar (as specified in ADR-005). Use `opentimelineio` as the internal timeline model, serialize to EDL.

**V2 (P1)**: Add AAF export via `pyaaf2` for Pro Tools/Resolve users needing sample-accuracy and volume automation.

**Skip**: OMF (dead format, no tooling).

The JSON sidecar compensates for all EDL limitations — carries full filenames, edit rationale, confidence scores, multi-track mapping, volume parameters, and chapter markers.

### Gotchas

- Use 30fps non-drop frame for audio-only EDL work (~33ms resolution)
- Generate one EDL per speaker track to work around the 2-channel limit
- Test EDL import in target DAWs early — subtle formatting differences cause import failures
- `opentimelineio`'s AAF write adapter is not production-grade; use `pyaaf2` directly for AAF
- No viable Node.js path for AAF generation — another point for Python (ADR-006)

### Resolved Open Question (ADR-005)

> **Answer**: Yes, support AAF export as a P1 feature using `pyaaf2`. Do NOT support OMF. Use `opentimelineio` as the internal timeline model.

---

## 3. FFmpeg Loudness Pipeline

### Question
Can FFmpeg normalize to -16 LUFS with true-peak limiting in a single pass? What are the exact commands?

### Finding

FFmpeg provides the `loudnorm` filter (EBU R128) and `ebur128` filter for loudness measurement.

**Single-pass vs two-pass**:

| Aspect | Single-pass | Two-pass (linear=true) |
|--------|-------------|----------------------|
| Dynamics preservation | Altered (dynamic gain) | Preserved (linear gain) |
| Accuracy to target | Within ~0.5 LU | Exact |
| Artifacts | Possible pumping/breathing | None (except at TP ceiling) |
| Processing time | 1x | 2x |

**Always use two-pass for production.**

### Complete Two-Pass Pipeline

**Pass 1 — Measure:**
```bash
ffmpeg -i input.wav \
  -af "loudnorm=I=-16:TP=-1:LRA=11:print_format=json" \
  -f null - 2>&1
```

Outputs JSON to stderr:
```json
{
    "input_i": "-18.10",
    "input_tp": "-0.30",
    "input_lra": "6.20",
    "input_thresh": "-28.10",
    "target_offset": "0.00"
}
```

**Pass 2 — Normalize (linear) and encode:**
```bash
ffmpeg -i input.wav \
  -af "loudnorm=I=-16:TP=-1:LRA=11:measured_I=-18.10:measured_TP=-0.30:measured_LRA=6.20:measured_thresh=-28.10:offset=0.00:linear=true" \
  -ar 44100 \
  -c:a libmp3lame \
  -b:a 192k \
  output.mp3
```

**Verification:**
```bash
ffmpeg -i output.mp3 -af "ebur128=peak=true" -f null - 2>&1 | grep -A 20 "Summary:"
```

### Automated Shell Script

```bash
#!/usr/bin/env bash
set -euo pipefail

INPUT="$1"
OUTPUT="$2"
TARGET_I=-16
TARGET_TP=-1
TARGET_LRA=11

# Pass 1: Measure
LOUDNORM_OUTPUT=$(ffmpeg -i "$INPUT" \
  -af "loudnorm=I=${TARGET_I}:TP=${TARGET_TP}:LRA=${TARGET_LRA}:print_format=json" \
  -f null - 2>&1 | sed -n '/{/,/}/p')

INPUT_I=$(echo "$LOUDNORM_OUTPUT" | python3 -c "import sys,json; print(json.load(sys.stdin)['input_i'])")
INPUT_TP=$(echo "$LOUDNORM_OUTPUT" | python3 -c "import sys,json; print(json.load(sys.stdin)['input_tp'])")
INPUT_LRA=$(echo "$LOUDNORM_OUTPUT" | python3 -c "import sys,json; print(json.load(sys.stdin)['input_lra'])")
INPUT_THRESH=$(echo "$LOUDNORM_OUTPUT" | python3 -c "import sys,json; print(json.load(sys.stdin)['input_thresh'])")
TARGET_OFFSET=$(echo "$LOUDNORM_OUTPUT" | python3 -c "import sys,json; print(json.load(sys.stdin)['target_offset'])")

# Pass 2: Normalize and encode
ffmpeg -i "$INPUT" \
  -af "loudnorm=I=${TARGET_I}:TP=${TARGET_TP}:LRA=${TARGET_LRA}:measured_I=${INPUT_I}:measured_TP=${INPUT_TP}:measured_LRA=${INPUT_LRA}:measured_thresh=${INPUT_THRESH}:offset=${TARGET_OFFSET}:linear=true" \
  -ar 44100 -c:a libmp3lame -b:a 192k -y "$OUTPUT"
```

### True-Peak Limiting

The `loudnorm` filter's `TP` parameter implements ITU-R BS.1770 true-peak detection using 4x oversampling (inter-sample peak detection). The `-1 dBTP` ceiling complies with:
- Apple Podcasts requirements
- Spotify for Podcasters
- EBU R128

### FFmpeg `loudnorm` vs Auphonic

| Feature | FFmpeg loudnorm (two-pass) | Auphonic |
|---------|---------------------------|----------|
| Loudness normalization | EBU R128 compliant | EBU R128 compliant |
| True-peak limiting | ITU-R BS.1770 | ITU-R BS.1770 |
| Dynamics preservation | Excellent (linear mode) | Good (applies compression) |
| Noise reduction | None | Adaptive, high quality |
| Multi-speaker leveling | None | Automatic |
| Cost | Free | 2 hrs/month free, then paid |

**For pure loudness normalization, FFmpeg two-pass linear is production-quality.** Auphonic adds value through noise reduction and multi-speaker leveling, not loudness normalization itself.

### Recommendation

Use FFmpeg two-pass linear normalization as the default mastering chain. Offer Auphonic/Dolby.io as pluggable premium providers for users who need noise reduction and auto-leveling beyond what FFmpeg provides.

### Gotchas

- `linear=true` is silently ignored without `measured_*` parameters — falls back to dynamic mode
- Set `LRA=11` to avoid unwanted dynamic range compression on speech (typical speech LRA is 5-8 LU)
- The `offset` parameter from Pass 1 must be passed to Pass 2 for exact accuracy
- Filter chains must be identical between passes (except `measured_*` params)
- Both filters write to stderr, not stdout — capture with `2>&1`
- Mono podcasts: add `-ac 1` — mono at 96k CBR ≈ stereo at 192k quality

---

## 4. Multi-Track Alignment

### Question
What algorithms/libraries exist for aligning two audio tracks by waveform similarity?

### Finding

**Core algorithm: Cross-correlation**

Cross-correlation is the standard signal processing approach for finding the time offset between two recordings of the same event. It computes the similarity between two signals at all possible offsets; the offset with the highest correlation is the alignment point.

**Python implementation using scipy:**

```python
import numpy as np
from scipy import signal
import soundfile as sf

def align_tracks(reference_path: str, target_path: str,
                 window_seconds: int = 30) -> tuple[float, float]:
    """
    Align target track to reference track.
    Returns (offset_ms, confidence).
    Positive offset means target starts after reference.
    """
    # Load only the first N seconds for speed
    ref, sr_ref = sf.read(reference_path, stop=window_seconds * 48000)
    target, sr_target = sf.read(target_path, stop=window_seconds * 48000)

    # Ensure mono
    if ref.ndim > 1:
        ref = ref[:, 0]
    if target.ndim > 1:
        target = target[:, 0]

    # Resample if needed
    if sr_ref != sr_target:
        from scipy.signal import resample
        target = resample(target, int(len(target) * sr_ref / sr_target))

    # Cross-correlation
    correlation = signal.correlate(ref, target, mode="full")
    lag_samples = np.argmax(np.abs(correlation)) - (len(target) - 1)

    # Convert to milliseconds
    offset_ms = (lag_samples / sr_ref) * 1000.0

    # Confidence: normalized peak correlation (0.0 to 1.0)
    confidence = float(np.max(np.abs(correlation)) / np.sqrt(
        np.sum(ref**2) * np.sum(target**2)
    ))

    return offset_ms, confidence
```

**Speed optimization: downsample first**

For 1-hour tracks, full cross-correlation at 48kHz is expensive. Downsample to 8kHz first:

```python
from scipy.signal import resample_poly

# Downsample 48kHz → 8kHz (factor of 6)
ref_ds = resample_poly(ref, up=1, down=6)
target_ds = resample_poly(target, up=1, down=6)

# Cross-correlate at low sample rate (36x fewer operations)
correlation = signal.correlate(ref_ds, target_ds, mode="full")
lag_samples_ds = np.argmax(np.abs(correlation)) - (len(target_ds) - 1)

# Convert back to high-res sample offset
offset_ms = (lag_samples_ds / 8000) * 1000.0

# Refine: re-run at full sample rate in a ±100ms window around the coarse offset
```

**Dedicated libraries:**

| Library | Description | Maintained | Notes |
|---------|-------------|:----------:|-------|
| `audalign` | Python, dedicated audio alignment | Limited | Cross-correlation + fingerprinting. `pip install audalign`. |
| `sync_audio_tracks` | Python CLI tool | Minimal | Uses cross-correlation. Basic but functional. |
| `librosa` | General audio analysis | Active | Has `librosa.sequence.dtw` for Dynamic Time Warping. |
| `praat-parselmouth` | Phonetics toolkit | Active | Can align by pitch contour. Overkill for this use case. |
| `numpy` + `scipy` | Core scientific computing | Active | All you need for cross-correlation. No audio-specific library required. |

**Alternative approaches:**

1. **Audio fingerprinting** (Chromaprint/Dejavu): More robust to quality differences between tracks, but slower and more complex. Best when tracks were recorded with very different equipment.
2. **Onset detection**: Align by matching transient/onset patterns. Works well for music, less reliable for speech.
3. **Dynamic Time Warping (DTW)**: Handles tracks that may have drift (different clock rates). More expensive computationally. Use if simple correlation produces poor results.

**Accuracy**: Cross-correlation at 48kHz gives sample-level precision: ±0.02ms. In practice, limited by acoustic differences between recording environments. Effective accuracy is ±1-5ms for clean podcast recordings, which is more than sufficient.

### Recommendation

Use `scipy.signal.correlate` with the following strategy:
1. Load first 30 seconds of each track
2. Downsample to 8kHz for coarse alignment
3. Refine at full sample rate in a narrow window
4. Report offset and confidence score
5. If confidence < 0.3, warn the user and skip alignment

No dedicated library needed — `numpy`/`scipy` plus 30-50 lines of code is the right approach.

### Gotchas

- **Different-length tracks**: If one person joined late, the first 30 seconds may not overlap. Solution: try multiple windows (0-30s, 30-60s, 60-90s) until correlation exceeds threshold.
- **Different sample rates**: Must resample to common rate before correlation.
- **Clock drift**: If recordings used different hardware clocks, there may be gradual drift (tracks sync at the start but diverge). For episodes <2 hours, drift is typically <100ms and ignorable. For longer content, consider DTW or periodic re-alignment.
- **No common audio content**: If tracks are truly independent (no crosstalk, no shared acoustic environment), cross-correlation will fail. This is detectable via low confidence score.
- **Performance**: Full 48kHz cross-correlation of 30s segments takes <2 seconds. With downsampling to 8kHz, it takes <0.5 seconds. Negligible in the pipeline.

---

## Summary: Architecture Impact

These research findings validate the architecture's tech choices with the following updates:

| Architecture Decision | Status | Update Needed |
|----------------------|--------|---------------|
| Whisper for transcription | **Validated** | Add `large-v3-turbo` as recommended default. Add `whisperX` as integrated option. |
| pyannote for diarization | **Validated** | Note HuggingFace token requirement. Consider `whisperX` wrapper. |
| CMX 3600 + JSON sidecar | **Validated** | Use 30fps. Add AAF via `pyaaf2` as P1 feature. Add OTIO as timeline model. |
| FFmpeg for loudness | **Validated** | Must use two-pass linear mode. Single-pass has quality issues. |
| Cross-correlation for alignment | **Validated** | scipy is sufficient. Add downsampling optimization. Add confidence threshold (0.3). |
| Python as language | **Reinforced** | No viable JS path for AAF, whisper integration, or scientific computing. |

### Resolved Open Questions

1. **ADR-005 (AAF/OMF)**: Support AAF export as P1 via `pyaaf2`. Skip OMF entirely.
2. **Whisper model choice**: Default to `large-v3-turbo` (best speed/quality tradeoff). Offer `large-v3` as high-accuracy option.
3. **FFmpeg single-pass**: No — always use two-pass linear for production.
