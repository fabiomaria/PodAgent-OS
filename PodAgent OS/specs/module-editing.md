# Module Spec: Narrative & Content Editing

> **Status**: Draft
> **Last Updated**: 2026-02-25
> **Author**: Spec Writer Agent
> **Position in Pipeline**: Module 2 of 4 — receives structured data from Ingestion, produces EDL for Mixing

---

## 1. Module Overview

The Narrative & Content Editing module analyzes the transcript and context document from Module 1 and produces a non-destructive Edit Decision List (EDL) describing what to cut, keep, or rearrange. It also generates chapter markers, show notes, and an edit rationale log for human review at Gate 2.

This module is the "brain" of the pipeline — it makes editorial judgment calls powered by LLM analysis. Every proposed edit carries a confidence score and rationale, and is subject to human override at the review gate.

This module **does not touch audio**. It operates entirely on text (transcript JSON, context JSON) and outputs text (EDL, JSON sidecar, Markdown).

---

## 2. Inputs

### 2.1 Required Inputs

#### Transcript (`artifacts/ingestion/transcript.json`)

Word-level transcript with timestamps and speaker IDs — the full output from Module 1.

#### Context Document (`artifacts/ingestion/context.json`)

Semantic analysis of the episode: topics, structural segments, proper nouns, key quotes.

> [ASSUMPTION] If the context document is unavailable (e.g., Claude API failed during ingestion), this module operates in **degraded mode**: filler removal and silence detection still work (they use only the transcript), but tangent detection, structural editing, and show notes quality will be significantly reduced. The module should log a warning and proceed.

#### Alignment Map (`artifacts/ingestion/alignment.json`)

Multi-track timing information. Needed to generate EDL timecodes that reference the correct source positions.

### 2.2 Optional Inputs

#### Editing Config (`config.editing` in manifest or `config/overrides.yaml`)

Sensitivity thresholds and style preferences. See Section 5 for all options.

#### Editorial Guidelines (future)

A natural-language description of the show's editing style (e.g., "keep tangents under 2 minutes, always preserve guest anecdotes"). Would be passed to the LLM as system context.

---

## 3. Outputs

All outputs are written to `artifacts/editing/`.

### 3.1 Edit Decision List (`edit-list.edl` + `edit-list.json`)

**CMX 3600 EDL** (`edit-list.edl`) — the DAW-portable artifact:

```
TITLE: Tech Talk Weekly - Episode 42
FCM: NON-DROP FRAME

001  ALICE001 AA/V  C        00:00:00:00 00:00:45:06 00:00:00:00 00:00:45:06
* FROM CLIP NAME: tracks/alice.wav
* COMMENT: KEEP - Intro segment

002  ALICE001 AA/V  D 002    00:01:02:15 00:03:44:20 00:00:45:06 00:03:27:11
* FROM CLIP NAME: tracks/alice.wav
* COMMENT: KEEP - Main topic discussion (2-frame dissolve)

003  BOB_001  AA/V  D 002    00:05:10:00 00:05:22:10 00:03:27:11 00:03:39:21
* FROM CLIP NAME: tracks/bob.wav
* COMMENT: KEEP - Guest response
```

**JSON Sidecar** (`edit-list.json`) — the rich internal representation:

```json
{
  "version": "1.0",
  "episode_id": "my-podcast-ep42",
  "original_duration_seconds": 3842.5,
  "edited_duration_seconds": 3210.8,
  "time_removed_seconds": 631.7,
  "time_removed_percent": 16.4,
  "edl_frame_rate": 30,
  "edl_mode": "NON-DROP FRAME",
  "edits": [
    {
      "id": "edit-001",
      "type": "keep",
      "source_track": "tracks/alice.wav",
      "source_start": 0.0,
      "source_end": 45.2,
      "record_start": 0.0,
      "record_end": 45.2,
      "transition": "cut",
      "speaker": "Alice",
      "description": "Intro segment",
      "segments": ["seg-001", "seg-002", "seg-003"]
    },
    {
      "id": "edit-002",
      "type": "cut",
      "source_track": "tracks/alice.wav",
      "source_start": 45.2,
      "source_end": 62.5,
      "reason": "filler",
      "confidence": 0.95,
      "rationale": "17.3s of repeated false starts and filler words ('um', 'so basically', 'um')",
      "segments": ["seg-004", "seg-005"],
      "auto_applied": true
    },
    {
      "id": "edit-003",
      "type": "cut",
      "source_track": "tracks/bob.wav",
      "source_start": 1400.0,
      "source_end": 1520.0,
      "reason": "tangent",
      "confidence": 0.82,
      "rationale": "120s off-topic digression about lunch restaurants. Not related to episode topic (AI Audio Processing).",
      "segments": ["seg-145", "seg-146", "seg-147", "seg-148", "seg-149"],
      "auto_applied": false,
      "review_flag": "Confidence below auto-cut threshold (0.85). Flagged for human review."
    }
  ],
  "transitions": [
    {
      "between": ["edit-001", "edit-003"],
      "type": "crossfade",
      "duration_ms": 50
    }
  ]
}
```

### 3.2 Edit Rationale Log (`rationale.json`)

Human-readable explanations for every proposed edit, organized for Gate 2 review.

```json
{
  "version": "1.0",
  "summary": {
    "total_edits": 24,
    "auto_applied": 18,
    "flagged_for_review": 6,
    "time_removed_seconds": 631.7,
    "breakdown": {
      "filler_removal": { "count": 12, "time_removed": 48.3 },
      "silence_removal": { "count": 5, "time_removed": 63.4 },
      "tangent_removal": { "count": 4, "time_removed": 480.0 },
      "false_start_removal": { "count": 3, "time_removed": 40.0 }
    }
  },
  "edits": [
    {
      "edit_id": "edit-002",
      "type": "filler_removal",
      "time": "00:45 - 01:02",
      "duration": "17.3s",
      "confidence": 0.95,
      "rationale": "Repeated false starts: 'So basically, um, what I was going to say is, um...'",
      "auto_applied": true,
      "words_removed": ["So", "basically", "um", "what", "I", "was", "going", "to", "say", "is", "um"]
    }
  ]
}
```

### 3.3 Content Summary (`summary.md`)

Episode summary, chapter markers, and show notes draft.

```markdown
# Episode 42: AI Audio Processing

## Summary
Alice and Bob discuss the state of AI-powered audio processing, focusing on
Whisper for transcription and new approaches to automated podcast editing.

## Chapters
- 00:00 — Introduction
- 00:45 — What is Whisper?
- 12:30 — Word-level timestamps and accuracy
- 23:10 — Automated podcast editing tools
- 45:00 — The future of AI in audio production
- 58:20 — Closing thoughts

## Key Quotes
> "I think we're maybe two years away from fully automated podcast editing."
> — Bob, 30:56

## Links Mentioned
- OpenAI Whisper: https://github.com/openai/whisper
- Auphonic: https://auphonic.com

## Keywords
Whisper, transcription, podcast editing, AI audio, diarization, EDL
```

---

## 4. Processing Steps

### Step 1: Load and Validate Inputs

```
1. Read transcript.json — validate schema, confirm segments are present
2. Read context.json — if missing, log warning and enter degraded mode
3. Read alignment.json — needed for multi-track EDL timecode calculation
4. Read editing config from manifest
5. Build an in-memory timeline: ordered list of segments with speaker, timestamps, text
```

### Step 2: Filler & False Start Detection

Detect filler words, verbal tics, and false starts using pattern matching on the transcript text.

```python
# Filler word patterns
FILLER_PATTERNS = [
    r'\bum+\b', r'\buh+\b', r'\bah+\b', r'\ber+\b',
    r'\byou know\b', r'\blike\b(?=\s*,)',  # "like" as filler, not comparison
    r'\bbasically\b', r'\bactually\b',      # when repeated/unnecessary
    r'\bso+\b(?=\s*,)',                      # "so" as sentence filler
    r'\bright\b(?=\s*[,?])',                 # "right?" as filler
]

# False start detection: speaker begins a sentence, abandons it, restarts
# Heuristic: segment < 3 words followed by silence > 500ms then a new segment
# starting with similar words
def detect_false_starts(segments: list, min_gap_ms: float = 500) -> list:
    false_starts = []
    for i in range(len(segments) - 1):
        seg = segments[i]
        next_seg = segments[i + 1]
        if (seg.speaker == next_seg.speaker
            and seg.word_count <= 3
            and (next_seg.start - seg.end) * 1000 > min_gap_ms):
            false_starts.append(seg)
    return false_starts
```

**For each detected filler region:**
1. Calculate the region boundaries (start/end time)
2. Assign confidence based on pattern strength:
   - Isolated "um" / "uh": confidence 0.95
   - "you know" / "like": confidence 0.80 (context-dependent)
   - False starts: confidence 0.85
3. Add to the cut list with reason `"filler"` or `"false_start"`

**Auto-apply threshold**: Fillers with confidence >= `filler_sensitivity` config value (default 0.7) are auto-applied. Below threshold, flagged for review.

### Step 3: Silence Detection

Detect extended silences (dead air) that should be shortened or removed.

```python
def detect_silences(segments: list, min_duration_ms: float = 800) -> list:
    """
    Find gaps between segments longer than min_duration_ms.
    These are candidates for trimming.
    """
    silences = []
    for i in range(len(segments) - 1):
        gap_start = segments[i].end
        gap_end = segments[i + 1].start
        gap_ms = (gap_end - gap_start) * 1000

        if gap_ms > min_duration_ms:
            # Keep a natural pause (300ms), trim the rest
            keep_ms = 300
            trim_start = gap_start + (keep_ms / 1000)
            trim_end = gap_end
            silences.append({
                "start": trim_start,
                "end": trim_end,
                "original_gap_ms": gap_ms,
                "trimmed_to_ms": keep_ms,
                "between_speakers": segments[i].speaker != segments[i + 1].speaker
            })
    return silences
```

**Rules:**
- Silences < `min_silence_duration_ms` (default 800ms): keep entirely
- Silences >= threshold: trim to 300ms (natural conversational pause)
- Between-speaker silences: trim to 500ms (slightly longer for turn-taking)
- Confidence is always 1.0 for silence trimming (objective measurement)

### Step 4: Tangent Detection (LLM-Powered)

Use Claude to identify off-topic digressions in the transcript.

```python
import anthropic

client = anthropic.Anthropic()

# Build the prompt with context
system_prompt = """You are an expert podcast editor. Your job is to identify
tangents (off-topic digressions) in a podcast transcript. A tangent is a section
where the conversation drifts away from the episode's main topics and does not
contribute to the core narrative.

You will receive:
1. The episode's main topics (from the context document)
2. The full transcript with segment IDs and timestamps

For each tangent you identify, provide:
- start_segment and end_segment IDs
- A confidence score (0.0-1.0) — how confident you are this is a true tangent
- A brief rationale explaining why it's off-topic
- Whether it's "hard" (clearly off-topic) or "soft" (marginally related,
  might be interesting to some listeners)

Do NOT flag:
- Humorous asides that last < 30 seconds (these add personality)
- Personal anecdotes that illustrate the main topic
- Brief digressions that the speakers self-correct from quickly

Return a JSON array of tangent objects."""

topics_summary = format_topics(context_doc["topics"])
transcript_text = format_transcript_for_llm(transcript)

message = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=4096,
    system=system_prompt,
    messages=[{
        "role": "user",
        "content": f"""EPISODE TOPICS:
{topics_summary}

TRANSCRIPT:
{transcript_text}

Identify all tangents. Return JSON array."""
    }]
)
```

**Tangent classification:**

| Confidence | Auto-apply? | Behavior |
|-----------|-------------|----------|
| >= 0.85 | Yes (if `tangent_sensitivity` >= 0.5) | Auto-marked for cut |
| 0.60 – 0.84 | No | Flagged for human review with rationale |
| < 0.60 | No | Not included in edit list (too uncertain) |

**Degraded mode** (no context document): Skip tangent detection entirely. Log warning: "Context document unavailable — tangent detection disabled."

### Step 5: Structural Editing Proposals

Analyze episode structure and propose improvements. These are always flagged for human review (never auto-applied).

```python
def analyze_structure(transcript, context_doc):
    """
    Identify structural issues and propose improvements.
    All proposals require human approval.
    """
    proposals = []

    # 1. Long intro detection
    intro = find_segment_by_type(context_doc, "intro")
    if intro and (intro.end - intro.start) > 120:  # > 2 minutes
        proposals.append({
            "type": "trim_intro",
            "rationale": f"Intro is {intro.duration:.0f}s. Consider trimming to < 60s.",
            "suggestion": "Move the first substantive topic mention earlier.",
            "auto_applied": False
        })

    # 2. Segment reordering (rare, high-risk)
    # Only propose if a topic is split across non-contiguous segments
    # e.g., topic A discussed at 10:00, then B at 20:00, then A again at 40:00

    # 3. Abrupt ending detection
    outro = find_segment_by_type(context_doc, "outro")
    if not outro or (transcript.duration - outro.start) < 10:
        proposals.append({
            "type": "missing_outro",
            "rationale": "No clear outro detected. Episode may end abruptly.",
            "suggestion": "Consider adding a closing segment.",
            "auto_applied": False
        })

    return proposals
```

### Step 6: Generate Chapter Markers

Use the context document's topic boundaries to propose chapter markers.

```python
def generate_chapters(context_doc, edited_timeline):
    """
    Map context document topics to chapter markers on the edited timeline.
    Adjust timestamps to account for removed segments.
    """
    chapters = []

    # Always add an "Introduction" chapter at 00:00
    chapters.append({"title": "Introduction", "time": 0.0})

    for topic in context_doc["topics"]:
        # Map original timestamp to edited timeline position
        edited_time = map_to_edited_timeline(topic["start_time"], edited_timeline)
        if edited_time is not None:
            chapters.append({
                "title": topic["name"],
                "time": edited_time
            })

    return chapters
```

> [ASSUMPTION] Chapter markers reference the *edited* timeline, not the original. If a tangent is cut before a chapter, the chapter's timestamp shifts earlier. The `map_to_edited_timeline()` function accounts for all cumulative cuts before the marker's position.

### Step 7: Generate Show Notes Draft

Use Claude to produce episode show notes from the transcript and context.

```python
message = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=2048,
    messages=[{
        "role": "user",
        "content": f"""Write podcast show notes for this episode.

EPISODE TITLE: {manifest.title}
EPISODE SUMMARY: {context_doc["episode_summary"]}
TOPICS: {format_topics(context_doc["topics"])}
KEY QUOTES: {format_quotes(context_doc["key_quotes"])}

Include:
1. A 2-3 sentence description suitable for a podcast feed
2. Chapter timestamps (provided below)
3. Key quotes (attributed, with timestamps)
4. Links/resources mentioned (extract URLs from transcript if present)
5. Guest bio if applicable

CHAPTERS:
{format_chapters(chapters)}

Format as Markdown."""
    }]
)
```

### Step 8: Build EDL and Write Outputs

Assemble all edit decisions into a final EDL.

```python
import opentimelineio as otio

def build_edl(edits: list, tracks: dict, frame_rate: int = 30):
    """
    Convert edit decisions into an OTIO timeline, then export to CMX 3600 EDL.
    """
    timeline = otio.schema.Timeline(name=f"{manifest.title}")

    for track_name, track_path in tracks.items():
        otio_track = otio.schema.Track(
            name=track_name,
            kind=otio.schema.TrackKind.Audio
        )

        # Add keep segments for this track, in record-time order
        keep_edits = [e for e in edits if e["type"] == "keep"
                      and e["source_track"] == track_path]

        for i, edit in enumerate(keep_edits):
            clip = otio.schema.Clip(
                name=f"{track_name}-{edit['id']}",
                media_reference=otio.schema.ExternalReference(
                    target_url=f"file:///{track_path}"
                ),
                source_range=otio.opentime.TimeRange(
                    start_time=otio.opentime.RationalTime(
                        int(edit["source_start"] * frame_rate), frame_rate
                    ),
                    duration=otio.opentime.RationalTime(
                        int((edit["source_end"] - edit["source_start"]) * frame_rate),
                        frame_rate
                    )
                )
            )
            otio_track.append(clip)

            # Add crossfade transition between consecutive clips
            if i < len(keep_edits) - 1:
                xfade_frames = int(0.05 * frame_rate)  # 50ms default
                transition = otio.schema.Transition(
                    transition_type=otio.schema.TransitionTypes.SMPTE_Dissolve,
                    in_offset=otio.opentime.RationalTime(xfade_frames, frame_rate),
                    out_offset=otio.opentime.RationalTime(xfade_frames, frame_rate)
                )
                otio_track.append(transition)

        timeline.tracks.append(otio_track)

    # Export one EDL per track (CMX 3600 limitation: max 2 audio channels)
    for i, track in enumerate(timeline.tracks):
        single_track_tl = otio.schema.Timeline(name=timeline.name)
        single_track_tl.tracks.append(track)
        otio.adapters.write_to_file(
            single_track_tl,
            f"artifacts/editing/edit-list-{track.name.lower()}.edl",
            adapter_name="cmx_3600"
        )

    # Write JSON sidecar (rich representation)
    write_atomic("artifacts/editing/edit-list.json", sidecar_data)

    # Write rationale log
    write_atomic("artifacts/editing/rationale.json", rationale_data)

    # Write show notes
    with open("artifacts/editing/summary.md", "w") as f:
        f.write(show_notes_markdown)

    # Update manifest
    manifest["pipeline"]["stages"]["editing"]["status"] = "completed"
    manifest["pipeline"]["stages"]["editing"]["completed_at"] = now_iso()
    write_atomic("manifest.yaml", manifest)
```

---

## 5. Configuration Options

All options live under `config.editing` in the manifest.

| Option | Type | Default | Range | Description |
|--------|------|---------|-------|-------------|
| `filler_sensitivity` | float | `0.7` | 0.0–1.0 | Filler detection threshold. Higher = more aggressive removal. |
| `tangent_sensitivity` | float | `0.5` | 0.0–1.0 | Tangent detection threshold. Higher = cuts more tangents. |
| `min_silence_duration_ms` | int | `800` | 200–5000 | Minimum silence duration to trigger trimming. |
| `silence_keep_ms` | int | `300` | 100–1000 | How much silence to keep after trimming (natural pause). |
| `speaker_turn_pause_ms` | int | `500` | 200–1500 | Silence to keep between different speakers. |
| `tangent_auto_cut_threshold` | float | `0.85` | 0.5–1.0 | Confidence threshold for auto-cutting tangents. Below this, flagged for review. |
| `max_tangent_keep_seconds` | int | `30` | 10–120 | Tangents shorter than this are kept regardless of confidence (personality preservation). |
| `detect_false_starts` | bool | `true` | — | Enable false start detection. |
| `generate_chapters` | bool | `true` | — | Auto-generate chapter markers. |
| `generate_show_notes` | bool | `true` | — | Auto-generate show notes via LLM. |
| `llm_model` | string | `"claude-sonnet-4-6"` | Any Claude model ID | Model for tangent detection and show notes. |
| `edl_frame_rate` | int | `30` | 24, 25, 30 | Frame rate for CMX 3600 EDL output. |
| `crossfade_duration_ms` | int | `50` | 0–500 | Default crossfade duration at edit points. |

---

## 6. External Dependencies

| Dependency | Type | Purpose | Required | Fallback |
|-----------|------|---------|----------|----------|
| `anthropic` | Python package | Claude API for tangent detection, show notes | Yes | Degraded mode: filler/silence removal only |
| `opentimelineio` | Python package | Timeline modeling and EDL export | Yes | DIY EDL generator (50-100 lines) |
| `re` | Python stdlib | Regex-based filler word detection | Yes (stdlib) | — |

No heavy system dependencies — this module operates on JSON text, not audio.

---

## 7. Error Handling

| Error | Detection | Recovery | User Impact |
|-------|-----------|----------|-------------|
| **Transcript file missing** | File existence check | Abort with clear error | Cannot proceed — re-run ingestion |
| **Context doc missing** | File existence check | Enter degraded mode (no tangent detection) | Reduced editing quality; log warning |
| **Alignment map missing** | File existence check | Abort with error | Cannot generate correct EDL timecodes |
| **Claude API error** | HTTP 5xx or timeout | Retry 3× with backoff. If all fail, skip tangent detection and show notes (degraded mode). | Filler/silence edits still applied, but no semantic editing |
| **LLM returns malformed JSON** | JSON parse error | Retry with rephrased prompt (max 2 retries). If still fails, skip that analysis step. | One edit type unavailable |
| **LLM hallucinates segment IDs** | Cross-reference against transcript segments | Filter out edits referencing non-existent segments. Log warning. | Slightly fewer tangent detections |
| **No edits detected** | Empty edit list | Write empty EDL, log info message. Proceed to gate. | Human reviews "no changes" and can approve or manually add edits |
| **OTIO EDL export fails** | Exception during write | Fall back to DIY EDL generator. Log warning. | EDL may have minor formatting differences |
| **Disk full** | Write failure (OSError) | Abort immediately, do not update manifest | User must free disk space |

---

## 8. Edge Cases

| Edge Case | Behavior |
|-----------|----------|
| **Very short episode (< 5 min)** | May have 0 tangents and few fillers. Produce minimal or empty EDL. Log info. |
| **Very long episode (> 3 hours)** | Chunk transcript for LLM tangent detection (15-min chunks with 1-min overlap). Merge tangent results. |
| **Solo show (1 speaker)** | Filler/silence detection works normally. Tangent detection still applies. No between-speaker pause logic. |
| **No fillers detected** | Possible for scripted/polished recordings. Produce EDL with no filler cuts. |
| **Entire episode is one tangent** | LLM might flag a very large portion. Cap auto-cuts at 50% of episode duration. Flag for human review if proposed cuts exceed 40%. |
| **Multiple languages** | Filler word patterns are English-specific. For non-English, rely on LLM for filler detection (add language-aware prompt). Silence detection is language-agnostic. |
| **Overlapping speech** | Do not cut overlapping regions (crosstalk). Mark them as "review" for the human. |
| **Music segments (intro/outro)** | Do not apply filler or silence detection to music-flagged segments in the context document. Pass music regions through as-is. |
| **Context doc has no topics** | LLM context extraction returned empty topics. Tangent detection is impossible. Skip it, proceed with filler/silence only. |
| **All edits rejected at Gate 2** | Human rejects entire EDL. Module produces a "pass-through" EDL that keeps everything. Pipeline continues with unedited audio. |
| **EDL event count > 999** | CMX 3600 limit. Split into multiple EDL files (`edit-list-alice-001.edl`, `edit-list-alice-002.edl`). In practice, very unlikely for podcasts. |

---

## 9. Performance Targets

| Operation | Target | Notes |
|-----------|--------|-------|
| Load and validate inputs | < 2 seconds | JSON parsing |
| Filler detection | < 5 seconds for 1-hour episode | Regex on transcript text |
| Silence detection | < 2 seconds for 1-hour episode | Gap calculation between segments |
| Tangent detection (LLM) | ~10-20 seconds per 15-min chunk | Claude Sonnet, depends on API latency |
| Structural analysis | < 5 seconds | Simple heuristics |
| Chapter generation | < 2 seconds | Timestamp mapping |
| Show notes generation (LLM) | ~5-10 seconds | Single Claude call |
| EDL generation | < 3 seconds | OTIO serialization |
| **Total — 1-hour episode** | **~30-60 seconds** | Dominated by LLM API calls |

> [ASSUMPTION] LLM calls are the bottleneck. With 4 × 15-min chunks for tangent detection + 1 call for show notes = 5 API calls. At ~10s each, that's ~50 seconds. Filler/silence detection is near-instant.

---

## 10. Example: Sample Input → Expected Output

### Input

- `transcript.json`: 557 segments, 10,052 words, 64-minute episode
- `context.json`: 4 topics, 5 structural segments (including 1 tangent at 23:20–25:20)
- Editing config: defaults (`filler_sensitivity: 0.7`, `tangent_sensitivity: 0.5`)

### Processing

```
[10:16:00] Editing started
[10:16:01] Loaded transcript (557 segments, 10,052 words)
[10:16:01] Loaded context document (4 topics, 5 structural segments)
[10:16:01] Loaded alignment map (2 tracks)
[10:16:02] Filler detection: found 12 filler regions (48.3s total)
[10:16:02] Silence detection: found 5 long silences (63.4s total, trimming to 1.5s)
[10:16:02] False start detection: found 3 false starts (40.0s total)
[10:16:03] Tangent detection: sending 5 chunks to Claude...
[10:16:52] Tangent detection: found 4 tangents (480.0s total)
  - 23:20-25:20 "Lunch recommendations" (confidence: 0.82, flagged for review)
  - 34:15-38:40 "Weekend plans" (confidence: 0.91, auto-cut)
  - 41:00-41:45 "Coffee joke" (confidence: 0.45, below threshold, skipped)
  - 52:30-54:10 "Unrelated tech complaint" (confidence: 0.88, auto-cut)
[10:16:53] Structural analysis: intro length OK (45s), outro detected
[10:16:53] Generating chapter markers (5 chapters)
[10:16:54] Generating show notes via Claude...
[10:17:02] Show notes generated
[10:17:02] Building EDL (24 edits: 18 auto-applied, 6 flagged for review)
[10:17:03] Writing artifacts to artifacts/editing/
[10:17:03] Editing complete in 63s. Awaiting Gate 2 review.
```

### Output Summary

| Metric | Value |
|--------|-------|
| Original duration | 64:02 |
| Edited duration | 53:31 |
| Time removed | 10:31 (16.4%) |
| Filler cuts | 12 (48.3s) |
| Silence trims | 5 (61.9s removed, 1.5s kept) |
| False start cuts | 3 (40.0s) |
| Tangent cuts | 2 auto + 1 flagged (480.0s proposed, 365.0s auto-applied) |
| Chapters | 5 |
| Edits for review | 6 |
