# Module Spec: Ingestion & Context Mapping

> **Status**: Draft
> **Last Updated**: 2026-02-25
> **Author**: Spec Writer Agent
> **Position in Pipeline**: Module 1 of 4 — first stage, no upstream dependencies

---

## 1. Module Overview

The Ingestion & Context Mapping module is the entry point of the PodAgent OS pipeline. It accepts raw audio recordings and episode metadata, then produces structured, machine-readable artifacts that all downstream modules depend on: a word-level transcript, a multi-track alignment map, and a semantic context document.

This module transforms unstructured audio into structured data. No editing decisions are made here — that's Module 2's job. This module answers: *"What was said, by whom, when, and what is it about?"*

---

## 2. Inputs

### 2.1 Required Inputs

#### Raw Audio Tracks

| Field | Requirement |
|-------|------------|
| Format | WAV (preferred), FLAC, or MP3 |
| Sample rate | 44.1kHz or 48kHz (auto-detected) |
| Channels | Mono (preferred) or stereo |
| Bit depth | 16-bit or 24-bit (WAV/FLAC) |
| Min tracks | 1 |
| Max tracks | 8 |
| Max duration per track | 5 hours |

#### Episode Metadata (`manifest.yaml` — `project` section)

```yaml
project:
  name: "My Podcast"              # required
  episode_number: 42              # required
  title: "The One About Whisper"  # required
  recording_date: "2026-02-20"   # required, ISO 8601
  participants:                   # required, at least 1
    - name: "Alice"
      role: host                  # host | guest | co-host
      track: "tracks/alice.wav"   # path relative to project root
    - name: "Bob"
      role: guest
      track: "tracks/bob.wav"
```

### 2.2 Optional Inputs

#### Speaker Voice Profiles

Pre-enrolled voice samples to improve speaker diarization accuracy. Stored in `config/voice-profiles/`.

```yaml
# config/voice-profiles.yaml
profiles:
  - name: "Alice"
    sample: "config/voice-profiles/alice-sample.wav"  # 30–60s of clean speech
  - name: "Bob"
    sample: "config/voice-profiles/bob-sample.wav"
```

> [ASSUMPTION] Voice profiles improve diarization accuracy but are not required. Without them, speakers are labeled `Speaker_1`, `Speaker_2`, etc., and must be manually assigned names at Gate 1.

#### Custom Vocabulary

A list of proper nouns, jargon, and domain terms to improve transcription accuracy.

```yaml
# config/vocabulary.yaml
terms:
  - "PodAgent"
  - "LUFS"
  - "pyannote"
  - "Auphonic"
```

---

## 3. Outputs

All outputs are written to `artifacts/ingestion/`.

### 3.1 Transcript (`transcript.json`)

Word-level transcript with timestamps and speaker attribution.

```json
{
  "version": "1.0",
  "episode_id": "my-podcast-ep42",
  "duration_seconds": 3842.5,
  "language": "en",
  "segments": [
    {
      "id": "seg-001",
      "speaker": "Alice",
      "start": 0.0,
      "end": 4.32,
      "text": "Welcome back to the show everyone.",
      "words": [
        { "word": "Welcome", "start": 0.0, "end": 0.45, "confidence": 0.97 },
        { "word": "back", "start": 0.48, "end": 0.72, "confidence": 0.99 },
        { "word": "to", "start": 0.74, "end": 0.82, "confidence": 0.98 },
        { "word": "the", "start": 0.84, "end": 0.92, "confidence": 0.99 },
        { "word": "show", "start": 0.95, "end": 1.20, "confidence": 0.99 },
        { "word": "everyone.", "start": 1.23, "end": 1.78, "confidence": 0.96 }
      ]
    },
    {
      "id": "seg-002",
      "speaker": "Bob",
      "start": 4.50,
      "end": 7.10,
      "text": "Thanks for having me, Alice.",
      "words": [
        { "word": "Thanks", "start": 4.50, "end": 4.82, "confidence": 0.98 },
        { "word": "for", "start": 4.85, "end": 4.98, "confidence": 0.99 },
        { "word": "having", "start": 5.01, "end": 5.38, "confidence": 0.97 },
        { "word": "me,", "start": 5.40, "end": 5.58, "confidence": 0.99 },
        { "word": "Alice.", "start": 5.62, "end": 6.10, "confidence": 0.95 }
      ]
    }
  ],
  "metadata": {
    "transcription_model": "faster-whisper-large-v3",
    "diarization_model": "pyannote/speaker-diarization-3.1",
    "processing_time_seconds": 245.3,
    "word_count": 5842,
    "segment_count": 312
  }
}
```

### 3.2 Alignment Map (`alignment.json`)

Describes how multi-track recordings map to a common timeline.

```json
{
  "version": "1.0",
  "reference_track": "tracks/alice.wav",
  "tracks": [
    {
      "path": "tracks/alice.wav",
      "offset_ms": 0,
      "duration_ms": 3842500,
      "sample_rate": 48000,
      "channels": 1,
      "is_reference": true
    },
    {
      "path": "tracks/bob.wav",
      "offset_ms": 12,
      "duration_ms": 3840100,
      "sample_rate": 48000,
      "channels": 1,
      "is_reference": false,
      "alignment_confidence": 0.994,
      "alignment_method": "cross-correlation"
    }
  ],
  "common_timeline": {
    "start_ms": 0,
    "end_ms": 3842500
  }
}
```

### 3.3 Context Document (`context.json`)

Semantic analysis of the episode content, produced by LLM (Claude).

```json
{
  "version": "1.0",
  "episode_summary": "Alice and Bob discuss the state of AI-powered audio processing, focusing on Whisper for transcription and new approaches to automated podcast editing.",
  "topics": [
    {
      "name": "Whisper transcription accuracy",
      "start_segment": "seg-045",
      "end_segment": "seg-078",
      "start_time": 342.5,
      "end_time": 612.3,
      "description": "Discussion of Whisper's word error rate across different accents"
    },
    {
      "name": "Automated podcast editing",
      "start_segment": "seg-102",
      "end_segment": "seg-156",
      "start_time": 815.0,
      "end_time": 1245.8,
      "description": "Overview of tools that auto-detect tangents and filler words"
    }
  ],
  "proper_nouns": [
    { "text": "OpenAI", "category": "organization", "occurrences": 12 },
    { "text": "Whisper", "category": "product", "occurrences": 34 },
    { "text": "Auphonic", "category": "product", "occurrences": 5 }
  ],
  "structural_segments": [
    { "type": "intro", "start_time": 0.0, "end_time": 45.2 },
    { "type": "main_topic", "label": "AI in Audio", "start_time": 45.2, "end_time": 2800.0 },
    { "type": "tangent", "label": "Lunch recommendations", "start_time": 1400.0, "end_time": 1520.0, "confidence": 0.82 },
    { "type": "outro", "start_time": 3600.0, "end_time": 3842.5 }
  ],
  "key_quotes": [
    {
      "speaker": "Bob",
      "text": "I think we're maybe two years away from fully automated podcast editing.",
      "time": 1856.3,
      "segment": "seg-198"
    }
  ],
  "metadata": {
    "llm_model": "claude-sonnet-4-6",
    "prompt_tokens": 28500,
    "completion_tokens": 2100,
    "processing_time_seconds": 8.2
  }
}
```

---

## 4. Processing Steps

### Step 1: Validate and Catalog Input Files

```
FOR each track in manifest.project.participants:
  1. Verify file exists at track.path
  2. Probe with FFmpeg to extract: duration, sample_rate, channels, codec, bit_depth
  3. Validate:
     - duration > 10 seconds (reject trivially short files)
     - duration < 18000 seconds (5 hours max)
     - sample_rate is 44100 or 48000 (warn and resample if different)
     - channels is 1 or 2 (warn if stereo — will use left channel only)
  4. Write file metadata to manifest.files.source_tracks[]
  5. If sample rates differ across tracks, resample all to the highest rate
```

**FFmpeg probe command:**
```bash
ffprobe -v quiet -print_format json -show_format -show_streams "tracks/alice.wav"
```

**FFmpeg resample command (if needed):**
```bash
ffmpeg -i input.wav -ar 48000 -ac 1 output.wav
```

### Step 2: Transcribe Audio

Run speech-to-text on each track independently.

```python
# Using faster-whisper
from faster_whisper import WhisperModel

model = WhisperModel("large-v3", device="cuda", compute_type="float16")
# Fallback: device="cpu", compute_type="int8" for machines without GPU
# Note: On macOS, use whisper.cpp instead — faster-whisper has no Apple GPU support

segments, info = model.transcribe(
    "tracks/alice.wav",
    beam_size=5,
    word_timestamps=True,
    vad_filter=True,         # Skip non-speech segments for speed
    vad_parameters=dict(
        min_silence_duration_ms=500,
        speech_pad_ms=200
    )
)

# Collect results
for segment in segments:
    print(f"[{segment.start:.2f} -> {segment.end:.2f}] {segment.text}")
    for word in segment.words:
        print(f"  {word.word} [{word.start:.2f}-{word.end:.2f}] conf={word.probability:.2f}")
```

**Decision: Transcribe each track independently, not a mixdown.** This avoids crosstalk artifacts and gives us per-speaker transcripts that are easier to diarize.

> [ASSUMPTION] Word-level timestamps from faster-whisper are accurate to approximately ±50–100ms for clear speech. Accuracy degrades for fast speech, overlapping speakers, and heavy accents.

> [REVIEW] **Gap**: Step 2 transcribes each track independently, but there's no step that **merges** the per-track transcripts into a unified, time-ordered transcript. The output schema (Section 3.1) shows a single interleaved transcript with segments from multiple speakers. Document the merge algorithm: interleave segments by timestamp, resolve overlapping segments (both speakers talking), and handle gaps. This is non-trivial and deserves its own sub-step between Step 3 and Step 4.

### Step 3: Speaker Diarization

Assign speaker identities to transcript segments.

**Strategy A — Multi-track (preferred when each speaker has their own track):**
If each participant recorded a separate track (the common case for remote podcasts), diarization is trivial: each track maps directly to a speaker. We still run energy-based voice activity detection (VAD) to identify who is speaking at any given moment.

```python
# Per-track VAD to detect active speech regions
# Use the same VAD from faster-whisper or pyannote's VAD
from pyannote.audio import Pipeline

vad_pipeline = Pipeline.from_pretrained("pyannote/voice-activity-detection")
vad_result = vad_pipeline("tracks/alice.wav")

for speech_turn in vad_result.get_timeline().support():
    print(f"Alice speaking: {speech_turn.start:.2f} -> {speech_turn.end:.2f}")
```

**Strategy B — Single-track (fallback for pre-mixed recordings):**
If only a single mixed track is provided, use full speaker diarization.

```python
from pyannote.audio import Pipeline

diarization_pipeline = Pipeline.from_pretrained(
    "pyannote/speaker-diarization-3.1",
    use_auth_token="HF_TOKEN"
)

diarization = diarization_pipeline("tracks/mixed.wav", num_speakers=2)
# num_speakers is inferred from manifest.project.participants count

for turn, _, speaker in diarization.itertracks(yield_label=True):
    print(f"{speaker}: {turn.start:.2f} -> {turn.end:.2f}")
```

**Speaker label assignment:**
- If voice profiles are provided, match diarized clusters to profiles using embedding similarity
- If no profiles, assign labels as `Speaker_1`, `Speaker_2`, etc. — the human will rename at Gate 1
- Map speaker labels back onto transcript segments by timestamp overlap

### Step 4: Multi-Track Alignment

Align all tracks to a common timeline. One track is selected as the reference (the longest, or the host's track).

```python
import numpy as np
from scipy import signal
import soundfile as sf

def align_tracks(reference_path: str, target_path: str) -> int:
    """Returns the offset of target relative to reference, in samples."""
    # Load first 30 seconds for alignment (faster than full file)
    ref, sr_ref = sf.read(reference_path, stop=30 * 48000)  # BUG: hardcodes 48000
    target, sr_target = sf.read(target_path, stop=30 * 48000)  # should use sr_ref

    # Ensure mono
    if ref.ndim > 1:
        ref = ref[:, 0]
    if target.ndim > 1:
        target = target[:, 0]

    # Cross-correlation
    correlation = signal.correlate(ref, target, mode="full")
    lag = np.argmax(np.abs(correlation)) - (len(target) - 1)

    offset_ms = (lag / sr_ref) * 1000
    confidence = np.max(np.abs(correlation)) / np.sqrt(
        np.sum(ref**2) * np.sum(target**2)
    )

    return offset_ms, confidence
```

> [REVIEW] **Bug**: The `sf.read(path, stop=30 * 48000)` hardcodes the sample rate. If the file is 44.1kHz, `stop=30*48000` reads ~32.6 seconds, not 30. Use `stop=window_seconds * sr` after reading the sample rate, or read without `stop` and truncate after. Also, the function signature says it returns `int` but actually returns `tuple[float, float]`.

> [REVIEW] **Missing optimization**: Research recommends downsampling to 8kHz before cross-correlation (36x fewer operations), then refining at full sample rate. The current implementation runs correlation at full 48kHz on 30s of audio. See `docs/research-p0.md` Section 4 for the optimized two-pass approach.

**Algorithm:**
1. Select the host's track as the reference (or longest track if roles aren't specified)
2. For each non-reference track, compute cross-correlation against the reference using the first 30 seconds
3. The lag at the correlation peak gives the time offset
4. Apply the offset to all timestamps for that track
5. Trim or pad tracks so they share a common timeline

> [ASSUMPTION] All tracks were recorded during the same session. If tracks are from different recording sessions, alignment is not applicable and should be skipped (single-track workflow).

### Step 5: LLM Context Extraction

Send the complete transcript to Claude for semantic analysis.

```python
import anthropic

client = anthropic.Anthropic()

# For long episodes, the transcript may exceed context limits.
# Strategy: chunk into ~15-minute segments with 1-minute overlap.
# Process each chunk, then merge results.

transcript_text = format_transcript_for_llm(transcript_json)

message = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=4096,
    messages=[{
        "role": "user",
        "content": f"""Analyze this podcast transcript and produce a structured analysis.

TRANSCRIPT:
{transcript_text}

Return a JSON object with:
1. "episode_summary": 2-3 sentence summary
2. "topics": array of {{name, start_segment, end_segment, description}} for each distinct topic discussed
3. "proper_nouns": array of {{text, category, occurrences}} for names, products, organizations mentioned
4. "structural_segments": array of {{type, label, start_time, end_time}} where type is intro/main_topic/tangent/aside/outro
5. "key_quotes": array of {{speaker, text, time, segment}} for notable or quotable moments (max 5)

For "structural_segments", mark potential tangents (off-topic digressions) with type "tangent" and include a confidence score (0.0-1.0).
"""
    }]
)
```

**Chunking strategy for long episodes:**

| Episode Length | Strategy |
|---------------|----------|
| < 30 min (~7,500 words) | Send full transcript in one call |
| 30 min – 2 hours | Chunk into 15-min segments with 1-min overlap, merge results |
| > 2 hours | Chunk into 15-min segments, process in parallel (max 4 concurrent), merge |

> ~~[NEEDS RESEARCH] Exact token count per minute of podcast transcript. Estimate: ~150 words/min spoken × 1.3 tokens/word ≈ 195 tokens/min. A 1-hour episode ≈ 11,700 tokens — fits in a single Claude call comfortably.~~

> [REVIEW] **Resolved**: The estimate is roughly correct. ~150 words/min × 1.3 tokens/word ≈ 195 tokens/min. A 1-hour episode ≈ 11,700 input tokens — well within Claude's context window. However, the transcript JSON format (with timestamps and speaker IDs per word) will be significantly larger than plain text. Estimate 3-4x more tokens for the full JSON. For a 1-hour episode, the JSON transcript is ~35,000-47,000 tokens — still fits in a single call but is no longer "comfortable." For episodes >1.5 hours, chunking will be necessary. Update the chunking thresholds accordingly.

> [REVIEW] **Gap**: The LLM prompt asks Claude to return JSON, but there's no validation of the response. What if the LLM returns malformed JSON? What if it hallucinates segment IDs that don't exist in the transcript? Add: (1) JSON schema validation of the response, (2) cross-reference segment IDs against actual transcript segments, (3) retry with a rephrased prompt if validation fails.

### Step 6: Write Outputs and Update Manifest

```python
# Write all artifacts atomically (write to temp, then rename)
def write_atomic(path: str, data: dict):
    tmp_path = path + ".tmp"
    with open(tmp_path, "w") as f:
        json.dump(data, f, indent=2)
    os.rename(tmp_path, path)  # atomic on POSIX

write_atomic("artifacts/ingestion/transcript.json", transcript)
write_atomic("artifacts/ingestion/alignment.json", alignment)
write_atomic("artifacts/ingestion/context.json", context)

# Update manifest
manifest["pipeline"]["stages"]["ingestion"]["status"] = "completed"
manifest["pipeline"]["stages"]["ingestion"]["completed_at"] = now_iso()
manifest["pipeline"]["current_stage"] = "editing"
write_atomic("manifest.yaml", manifest)
```

---

## 5. Configuration Options

All options live under `config.ingestion` in the manifest or in `config/overrides.yaml`.

| Option | Type | Default | Range | Description |
|--------|------|---------|-------|-------------|
| `transcription_model` | string | `"large-v3"` | `tiny`, `base`, `small`, `medium`, `large-v3`, `large-v3-turbo` | Whisper model size. Larger = more accurate, slower. |

> [REVIEW] **Update from research**: Default should be `large-v3-turbo`, not `large-v3`. The turbo model is 6-8x faster with only 1-3% WER degradation — imperceptible for podcast-quality audio. Add `large-v3-turbo` to the range and make it the default.
| `transcription_device` | string | `"auto"` | `auto`, `cuda`, `cpu` | Force CPU or GPU. `auto` uses GPU if available. |
| `transcription_language` | string | `null` | ISO 639-1 code or `null` | Force language. `null` = auto-detect. |
| `vad_enabled` | bool | `true` | — | Skip non-speech segments during transcription. |
| `vad_min_silence_ms` | int | `500` | 100–5000 | Minimum silence duration to skip (ms). |
| `diarization_strategy` | string | `"auto"` | `auto`, `multi-track`, `single-track` | `auto` picks based on track count. |
| `diarization_num_speakers` | int | `null` | 1–8 or `null` | Force speaker count. `null` = infer from participants list. |
| `alignment_segment_seconds` | int | `30` | 10–120 | Duration of audio used for cross-correlation alignment. |
| `llm_model` | string | `"claude-sonnet-4-6"` | Any Claude model ID | Model for context extraction. |
| `llm_chunk_minutes` | int | `15` | 5–30 | Transcript chunk size for long episodes. |
| `custom_vocabulary_path` | string | `null` | File path or `null` | Path to custom vocabulary YAML. |
| `voice_profiles_path` | string | `null` | File path or `null` | Path to voice profiles YAML. |

---

## 6. External Dependencies

| Dependency | Type | Purpose | Required | Fallback |
|-----------|------|---------|----------|----------|
| `faster-whisper` | Python package | Speech-to-text transcription | Yes | OpenAI Whisper API (cloud) |

> [REVIEW] **Gap**: `faster-whisper` does NOT support Apple Silicon GPU (MPS). On macOS, the spec should recommend `whisper.cpp` as the primary transcription engine (with native Metal/CoreML acceleration). Add `whisper.cpp` as an alternative dependency and document platform-specific recommendations: Linux/CUDA → `faster-whisper`, macOS/Metal → `whisper.cpp`.

| `pyannote.audio` | Python package | Speaker diarization & VAD | Yes (for single-track) | Manual speaker labeling at Gate 1 |
| `ffmpeg` | System binary | Audio probing, resampling, format conversion | Yes | None — hard dependency |
| `ffprobe` | System binary (bundled with ffmpeg) | Audio file metadata extraction | Yes | None |
| `numpy` / `scipy` | Python packages | Cross-correlation for multi-track alignment | Yes | None |
| `soundfile` | Python package | Reading WAV/FLAC files | Yes | None |
| `anthropic` | Python package | Claude API for context extraction | Yes | None — hard dependency for context doc |
| HuggingFace token | API token | Downloading pyannote models | Yes (first run) | Pre-downloaded models |

**Install:**
```bash
pip install faster-whisper pyannote.audio anthropic soundfile numpy scipy pyyaml
# System dependency:
brew install ffmpeg   # macOS
apt install ffmpeg    # Linux
```

---

## 7. Error Handling

| Error | Detection | Recovery | User Impact |
|-------|-----------|----------|-------------|
| **Audio file not found** | File existence check in Step 1 | Abort with clear error: "Track 'tracks/bob.wav' not found" | Fix path in manifest, re-run |
| **Unsupported audio format** | FFprobe returns error or unexpected codec | Abort with error listing supported formats | Convert file manually, re-run |
| **Whisper GPU out of memory** | CUDA OOM exception | Auto-retry with smaller model (`medium` → `small`) or fall back to CPU with `int8` quantization | Slower transcription, possibly lower accuracy |
| **Whisper API rate limit** | HTTP 429 response | Exponential backoff: wait 1s, 2s, 4s, 8s, max 3 retries | Slight delay |
| **Pyannote model download failure** | Network error on first run | Retry 3 times, then abort with instructions to download manually | User needs internet for first run |
| **Cross-correlation fails** | Confidence score < 0.3 | Log warning, set offset to 0, flag for human review at Gate 1 | Human must manually verify alignment |
| **Claude API error** | HTTP 5xx or timeout | Retry 3 times with exponential backoff. If all fail, write manifest with `status: failed` and skip context doc | Pipeline can proceed without context doc, but Module 2 will have degraded tangent detection |

> [REVIEW] **Contradiction**: The error handling says "Pipeline can proceed without context doc" if Claude API fails, but the architecture (Section 2.2, Module 2 Inputs) lists the context document as **Required**. Either: (1) make the context document truly optional in Module 2 and document degraded behavior, or (2) make Claude API failure a hard stop for ingestion (status: failed, don't proceed). Recommend option 1 with clear documentation of what Module 2 loses without it (tangent detection, structural segmentation, show notes quality).
| **Claude API token limit exceeded** | HTTP 400 with token error | Reduce chunk size by 50% and retry | Slightly lower context quality due to smaller chunks |
| **Disk full** | Write failure (OSError) | Abort immediately, do not update manifest | User must free disk space |
| **Track duration mismatch > 60s** | Comparison after alignment | Log warning, proceed, flag at Gate 1 | Human reviews whether tracks are from the same session |

### Retry policy

```python
import tenacity

@tenacity.retry(
    stop=tenacity.stop_after_attempt(3),
    wait=tenacity.wait_exponential(multiplier=1, min=1, max=30),
    retry=tenacity.retry_if_exception_type((httpx.TimeoutException, httpx.HTTPStatusError))
)
def call_claude_api(transcript_chunk: str) -> dict:
    ...
```

---

## 8. Edge Cases

| Edge Case | Behavior |
|-----------|----------|
| **Single track (no multi-track)** | Skip alignment (Step 4). Use single-track diarization (Strategy B). |
| **Episode with 1 speaker (solo show)** | Set `diarization_num_speakers: 1`. Diarization still runs for VAD but assigns all speech to one speaker. |
| **Very short episode (< 5 minutes)** | Process normally. Send full transcript to LLM in one call. Context doc may have minimal topic analysis. |
| **Very long episode (> 3 hours)** | Chunk transcription is unaffected (Whisper processes sequentially). Chunk LLM calls into 15-min segments. Warn user about extended processing time. |
| **Tracks with different sample rates** | Resample all to the highest sample rate found (Step 1). Log the resampling. |
| **Stereo track provided** | Extract left channel only (convention: primary mic is left). Log a warning. |

> [REVIEW] **Assumption risk**: "Primary mic is left channel" is not a universal convention. Some interfaces record mic on right. Some record different sources on L/R (e.g., mic on left, room on right). Safer approach: analyze both channels for speech energy and pick the one with higher speech content, or prompt the user at Gate 1 to confirm which channel to use.
| **Silence-only track** | Whisper returns empty transcript. Log error: "Track 'X' contains no speech — verify correct file was provided." Mark track as silent in alignment map but do not abort. |
| **Non-English audio** | Whisper auto-detects language. Log detected language. Context extraction prompt is sent in English but transcript is in original language. |
| **Overlapping speech (crosstalk)** | On multi-track: each track captures one speaker, so crosstalk is minimal bleed. On single-track: Whisper transcribes the dominant speaker; pyannote may mis-attribute. Flag overlap regions with low confidence. |
| **Background music throughout** | Whisper's VAD may struggle. Recommend pre-processing with a vocal separation tool (Demucs) if music is constant. Flag as `> [NEEDS RESEARCH]`. |
| **Tracks from different sessions** | Cross-correlation will fail (low confidence). Alignment is skipped, tracks treated as independent. Warning logged. |
| **Custom vocabulary with >100 terms** | Whisper `initial_prompt` has a token limit (~224 tokens). Prioritize terms by expected frequency. Truncate with warning. |

---

## 9. Performance Targets

| Operation | Target (per minute of audio) | Notes |
|-----------|------------------------------|-------|
| Audio validation (Step 1) | < 1 second | FFprobe is near-instant |
| Transcription — GPU (large-v3) | ~6 seconds | NVIDIA RTX 3080 or better, float16 |
| Transcription — CPU (large-v3) | ~60 seconds | int8 quantization, 8-core CPU |
| Transcription — API | ~3 seconds + network latency | OpenAI Whisper API |
| Speaker diarization | ~4 seconds | pyannote on GPU |
| Multi-track alignment | < 2 seconds total | Only processes first 30s of audio |
| LLM context extraction | ~5 seconds per 15-min chunk | Claude Sonnet, depends on API latency |
| **Total — GPU machine** | **~15 seconds per minute of audio** | ~15 minutes for a 1-hour episode |
| **Total — CPU only** | **~70 seconds per minute of audio** | ~70 minutes for a 1-hour episode |

> [ASSUMPTION] GPU performance targets assume NVIDIA RTX 3080 or equivalent with ≥10GB VRAM. Apple Silicon Macs with `mlx-whisper` may achieve similar speeds.

---

## 10. Example: Sample Input → Expected Output

### Input

**Manifest** (`manifest.yaml`):
```yaml
project:
  name: "Tech Talk Weekly"
  episode_number: 42
  title: "AI Audio Processing"
  recording_date: "2026-02-20"
  participants:
    - name: "Alice"
      role: host
      track: "tracks/alice.wav"
    - name: "Bob"
      role: guest
      track: "tracks/bob.wav"
```

**Audio files:**
- `tracks/alice.wav` — 64 min 02s, 48kHz, mono, 24-bit WAV (368 MB)
- `tracks/bob.wav` — 64 min 00s, 48kHz, mono, 24-bit WAV (368 MB)

### Expected Output

**Processing log:**
```
[10:00:00] Ingestion started
[10:00:01] Validated tracks/alice.wav — 64m02s, 48kHz, mono, 24-bit
[10:00:01] Validated tracks/bob.wav — 64m00s, 48kHz, mono, 24-bit
[10:00:01] Sample rates match (48kHz), no resampling needed
[10:00:02] Transcribing tracks/alice.wav with faster-whisper large-v3 (GPU)
[10:06:24] Transcription complete — 5,842 words, 312 segments
[10:06:25] Transcribing tracks/bob.wav with faster-whisper large-v3 (GPU)
[10:12:41] Transcription complete — 4,210 words, 245 segments
[10:12:41] Multi-track mode: using per-track VAD (skipping full diarization)
[10:12:43] Aligning tracks via cross-correlation (30s window)
[10:12:44] Alignment: bob.wav offset = +12ms relative to alice.wav (confidence: 0.994)
[10:12:44] Merging transcripts into unified timeline
[10:12:45] Sending transcript to Claude for context extraction (1 chunk, 11,200 tokens)
[10:12:53] Context extraction complete — 4 topics, 12 proper nouns, 3 key quotes
[10:12:53] Writing artifacts to artifacts/ingestion/
[10:12:53] Updating manifest — ingestion status: completed
[10:12:53] Ingestion complete in 12m53s. Awaiting Gate 1 review.
```

**Output files:**
- `artifacts/ingestion/transcript.json` — 312 + 245 = 557 segments, 10,052 words
- `artifacts/ingestion/alignment.json` — 2 tracks, bob offset +12ms
- `artifacts/ingestion/context.json` — 4 topics, 12 proper nouns, 5 structural segments

**Manifest updated:**
```yaml
pipeline:
  current_stage: "editing"
  stages:
    ingestion:
      status: "completed"
      started_at: "2026-02-25T10:00:00Z"
      completed_at: "2026-02-25T10:12:53Z"
      gate_approved: null  # awaiting human review
```
