# PodAgent OS — Product Requirements Document

> **Status**: Draft
> **Last Updated**: 2026-02-25
> **Author**: Spec Writer Agent

---

## 1. Executive Summary

PodAgent OS is an open-source, AI-powered podcast production pipeline that automates the end-to-end workflow from raw multi-track audio recordings to mastered, tagged, publishable episodes. It runs locally as a CLI tool, processes audio through four sequential stages (ingestion, editing, mixing, mastering), and keeps the human in the loop with review gates between each stage.

The tool is designed for independent podcast producers and small studios who want professional-quality post-production without the cost of a dedicated audio engineer or the hours of manual editing per episode. PodAgent OS handles transcription, filler/tangent removal, noise reduction, loudness normalization, metadata tagging, and show notes generation — while ensuring the producer retains full editorial control through non-destructive editing and human review at every step.

---

## 2. Problem Statement & Target User

### The Problem

Podcast post-production is time-consuming and repetitive. A typical 1-hour interview episode requires:

| Task | Manual Time | Skill Required |
|------|-------------|----------------|
| Listen-through + note-taking | 60–90 min | None |
| Editing (fillers, tangents, dead air) | 60–120 min | Moderate (DAW proficiency) |
| Noise reduction + leveling | 15–30 min | Moderate (audio engineering basics) |
| Mixing (ducking, crossfades, music beds) | 20–40 min | Moderate–High |
| Loudness normalization + mastering | 10–20 min | Moderate (LUFS knowledge) |
| Metadata tagging + chapter markers | 15–30 min | Low |
| Show notes + timestamps | 20–40 min | Low |
| **Total** | **3–6 hours per episode** | |

Most independent podcasters either spend this time themselves (unsustainable at scale) or compromise on quality (no editing, poor loudness, no chapters). Professional studios charge $100–500+ per episode for this work.

### Target Users

**Primary: The Solo/Small-Team Podcaster**
- Produces 1–4 episodes per week
- Has basic DAW knowledge but is not an audio engineer
- Records remotely (each participant records a local track via Riverside, Zencastr, or similar)
- Spends 3–6 hours per episode on post-production and wants to cut that to under 30 minutes of review time
- Budget-conscious — prefers free/open-source tools over subscription services
- Values editorial control — wants to review and approve automated decisions, not blindly trust AI

**Secondary: The Podcast Production Studio**
- Manages 5–20 shows for clients
- Has audio engineers on staff but wants to automate the repetitive parts (filler removal, loudness normalization, metadata)
- Needs DAW interoperability — exports must be importable into Pro Tools, Audition, or Resolve for manual refinement
- Values consistency — every episode should meet the same loudness and quality standards

**Anti-User: NOT For**
- Live podcast streamers (PodAgent OS is post-production only)
- Music producers (optimized for speech, not music)
- Listeners (this is a production tool, not a player)

### User Environment

| Attribute | Expected |
|-----------|----------|
| Operating system | macOS (primary), Linux (secondary), Windows (future) |
| Hardware | MacBook Pro (M1–M4) or Linux workstation with optional NVIDIA GPU |
| Audio format | Multi-track WAV/FLAC from remote recording platforms |
| Episode length | 20 min – 3 hours (typical: 45–90 min) |
| Episodes per week | 1–4 |
| Technical comfort | Terminal-literate, can install Python packages and run CLI commands |

---

## 3. User Stories

### US-01: First-Time Setup

**As a** podcaster installing PodAgent OS for the first time,
**I want to** install the tool and process a test episode in under 15 minutes,
**so that** I can evaluate whether it meets my needs before committing to it.

**Acceptance Criteria:**
- [ ] `pip install podagent-os` succeeds on macOS and Linux with Python 3.11+
- [ ] `podagent init --title "Test Episode" --tracks host.wav guest.wav` scaffolds a project in < 5 seconds
- [ ] `podagent run` processes a 10-minute test episode end-to-end in < 5 minutes (on a Mac M2)
- [ ] The output includes a playable MP3, show notes, and chapter markers
- [ ] Error messages are clear if FFmpeg or other dependencies are missing

---

### US-02: Ingest and Transcribe

**As a** podcast producer,
**I want to** give PodAgent my raw audio tracks and get a full transcript with speaker labels,
**so that** I can review what was said before editing begins.

**Acceptance Criteria:**
- [ ] Accepts 1–8 WAV/FLAC/MP3 tracks
- [ ] Produces a word-level transcript with timestamps and speaker attribution
- [ ] Correctly identifies which participant is speaking (via multi-track mapping or diarization)
- [ ] Aligns multi-track recordings to a common timeline (handles offset from different "record" buttons)
- [ ] Transcription accuracy ≥ 95% WER for clear English speech
- [ ] Processing time < 15 minutes for a 1-hour, 2-track episode on a Mac M2

---

### US-03: Review Transcript (Gate 1)

**As a** podcast producer,
**I want to** review the transcript and correct any errors before editing begins,
**so that** downstream edits are based on accurate text.

**Acceptance Criteria:**
- [ ] Pipeline pauses after ingestion and presents the transcript for review
- [ ] Transcript is displayed in a human-readable format (not raw JSON)
- [ ] I can see speaker labels and correct misidentifications
- [ ] I can approve, edit, or re-run ingestion with different settings
- [ ] My edits are preserved in the transcript artifact

---

### US-04: Automated Editing

**As a** podcast producer,
**I want** PodAgent to automatically detect and mark filler words, dead air, and off-topic tangents for removal,
**so that** I can produce a tighter episode without manually listening through the entire recording.

**Acceptance Criteria:**
- [ ] Detects "um", "uh", repeated false starts, and other filler patterns
- [ ] Trims extended silences (> 800ms) to natural pause length
- [ ] Uses AI to identify off-topic tangents with confidence scores
- [ ] High-confidence edits (≥ 0.85) are auto-applied; lower-confidence edits are flagged for review
- [ ] Produces a non-destructive EDL (CMX 3600) importable into Pro Tools, Audition, or Resolve
- [ ] Every edit includes a rationale ("Cut: 45s tangent about lunch at 23:14")
- [ ] Total time removed is reported as a summary

---

### US-05: Review Edit Decisions (Gate 2)

**As a** podcast producer,
**I want to** review every proposed edit before it's applied,
**so that** I maintain editorial control and don't accidentally cut important content.

**Acceptance Criteria:**
- [ ] I can see each proposed edit with its rationale and confidence score
- [ ] I can approve all, reject all, or cherry-pick individual edits
- [ ] I can adjust cut points manually
- [ ] I can re-run editing with different sensitivity settings
- [ ] I can see total time removed vs. original duration
- [ ] Chapter markers and show notes draft are presented for review

---

### US-06: Audio Processing and Mixing

**As a** podcast producer,
**I want** PodAgent to apply noise reduction, level my tracks, and mix them down,
**so that** the audio sounds professional without me needing to learn audio engineering.

**Acceptance Criteria:**
- [ ] Applies noise reduction (at least FFmpeg-quality, with option for Auphonic/Dolby.io)
- [ ] Evens out volume differences between speakers via compression
- [ ] Auto-ducks secondary tracks when the primary speaker is talking
- [ ] Applies crossfades at edit points (no audible clicks or pops)
- [ ] Supports intro/outro music bed insertion
- [ ] Outputs a single stereo WAV mix

---

### US-07: Review Mix (Gate 3)

**As a** podcast producer,
**I want to** listen to the mixed audio before mastering,
**so that** I can catch any audio issues (bad cuts, over-aggressive noise reduction, ducking problems).

**Acceptance Criteria:**
- [ ] Pipeline pauses and presents the mixed audio for review
- [ ] I can see a waveform overview with edit points marked
- [ ] I can see what processing was applied to each track
- [ ] I can adjust parameters (noise reduction level, crossfade duration) and re-run
- [ ] I can go back to Gate 2 if the edits themselves are wrong

---

### US-08: Mastering and Delivery

**As a** podcast producer,
**I want** PodAgent to normalize loudness, encode to MP3, embed metadata and chapters, and give me a ready-to-upload package,
**so that** I can publish without any additional processing.

**Acceptance Criteria:**
- [ ] Loudness normalized to -16 LUFS (configurable) with true-peak limiting at -1 dBTP
- [ ] Produces MP3 (192kbps CBR) and lossless WAV archive
- [ ] Embeds ID3v2 tags: title, artist, album, episode number, genre, cover art
- [ ] Embeds chapter markers as ID3 CHAP frames
- [ ] Generates show notes in Markdown and HTML
- [ ] Bundles all deliverables in a single output directory
- [ ] Meets Apple Podcasts, Spotify, and general RSS distribution requirements

---

### US-09: Resume After Failure

**As a** podcast producer,
**I want to** resume the pipeline from where it failed without re-processing completed steps,
**so that** a transient error (API timeout, disk full) doesn't waste the work already done.

**Acceptance Criteria:**
- [ ] Re-running `podagent run` skips completed stages and resumes from the failed/pending stage
- [ ] The manifest tracks stage status (`pending`, `in_progress`, `completed`, `failed`)
- [ ] Failed stages include an error message explaining what went wrong
- [ ] Completed artifacts are not regenerated

---

### US-10: DAW Export

**As a** podcast producer who sometimes fine-tunes edits manually,
**I want to** import PodAgent's edit decisions into my DAW,
**so that** I can use PodAgent for the heavy lifting and do final tweaks in Pro Tools or Audition.

**Acceptance Criteria:**
- [ ] EDL files (CMX 3600) import successfully into Adobe Audition, Pro Tools, and DaVinci Resolve
- [ ] Each speaker's track has its own EDL file
- [ ] Edit points, crossfades, and source file references are correct
- [ ] A JSON sidecar carries additional metadata (rationale, confidence) for tools that can read it

---

### US-11: Configuration and Customization

**As a** podcast producer with specific preferences,
**I want to** configure editing sensitivity, loudness targets, and processing options,
**so that** PodAgent matches my show's style.

**Acceptance Criteria:**
- [ ] All key parameters are configurable via the manifest YAML or a config override file
- [ ] Sensible defaults work out of the box — no config required for basic use
- [ ] Configuration is documented with valid ranges and descriptions
- [ ] Per-episode overrides don't affect the global defaults

---

## 4. Feature Requirements

### P0 — Must Have (MVP)

These are required for the first usable release.

| ID | Feature | Module | Description |
|----|---------|--------|-------------|
| F-001 | Multi-track audio ingestion | Ingestion | Accept 1–8 WAV/FLAC/MP3 tracks, validate, and catalog |
| F-002 | Speech-to-text transcription | Ingestion | Word-level transcript with timestamps via Whisper (`large-v3-turbo`) |
| F-003 | Speaker identification | Ingestion | Map transcripts to speakers via multi-track VAD or pyannote diarization |
| F-004 | Multi-track alignment | Ingestion | Cross-correlation-based alignment to shared timeline |
| F-005 | LLM context extraction | Ingestion | Topics, proper nouns, structural segments via Claude API |
| F-006 | Gate 1: Transcript review | Pipeline | Pause for human review of transcript and speaker labels |
| F-007 | Filler word removal | Editing | Detect and mark "um", "uh", false starts for removal |
| F-008 | Silence trimming | Editing | Trim dead air > 800ms to natural pause length |
| F-009 | Tangent detection | Editing | LLM-powered off-topic detection with confidence scoring |
| F-010 | EDL generation | Editing | Non-destructive CMX 3600 EDL + JSON sidecar |
| F-011 | Chapter marker generation | Editing | Auto-generate chapters from topic boundaries |
| F-012 | Show notes generation | Editing | LLM-generated episode summary, timestamps, links |
| F-013 | Gate 2: Edit review | Pipeline | Pause for human review of proposed edits |
| F-014 | EDL execution | Mixing | Apply edit decisions to source audio |
| F-015 | Noise reduction (FFmpeg) | Mixing | Local noise reduction via `afftdn` |
| F-016 | Per-track compression | Mixing | Dynamic range compression to even out volume |
| F-017 | Auto-ducking | Mixing | Duck secondary tracks when primary speaker is active |
| F-018 | Crossfade generation | Mixing | Smooth crossfades at edit points |
| F-019 | Multi-track mix-down | Mixing | Combine all tracks into stereo WAV |
| F-020 | Gate 3: Mix review | Pipeline | Pause for human review of mixed audio |
| F-021 | Loudness normalization | Mastering | Two-pass linear EBU R128 to -16 LUFS |
| F-022 | True-peak limiting | Mastering | -1 dBTP ceiling per ITU-R BS.1770 |
| F-023 | MP3 encoding | Mastering | LAME, 192kbps CBR, ID3v2.4 tags |
| F-024 | Metadata embedding | Mastering | Title, artist, album, cover art, chapters via mutagen |
| F-025 | Archive WAV | Mastering | Lossless 48kHz/24-bit normalized master |
| F-026 | Manifest-based state management | Pipeline | YAML manifest tracks all state, enables resume |
| F-027 | Resumable pipeline | Pipeline | Re-run skips completed stages |
| F-028 | CLI interface | Pipeline | `podagent init`, `podagent run`, `podagent gate` commands |

### P1 — Should Have (V1)

Important for a complete V1 release, but not blockers for MVP.

| ID | Feature | Module | Description |
|----|---------|--------|-------------|
| F-101 | AAF export | Editing | Export edit decisions as AAF via `pyaaf2` for Pro Tools/Resolve |
| F-102 | Auphonic noise reduction | Mixing | Pluggable premium provider for cloud-based noise reduction |
| F-103 | Dolby.io noise reduction | Mixing | Pluggable premium provider for cloud-based noise reduction |
| F-104 | De-essing | Mixing | Optional sibilance reduction filter |
| F-105 | Music bed insertion | Mixing | Auto-insert intro/outro music with ducking |
| F-106 | Whisper API fallback | Ingestion | Cloud transcription when local GPU is unavailable |
| F-107 | Voice profiles | Ingestion | Pre-enrolled voice samples for improved diarization |
| F-108 | Custom vocabulary | Ingestion | User-provided term lists for better transcription |
| F-109 | FLAC output | Mastering | Lossless compressed archive format |
| F-110 | Editorial guidelines | Editing | Natural-language editing style preferences for the LLM |
| F-111 | Web UI for gates | Pipeline | Local browser-based interface for reviewing gate outputs |
| F-112 | Waveform preview | Mixing | Visual waveform overview for Gate 3 |
| F-113 | Before/after clips | Mixing | Audio comparison at key edit points for Gate 3 |

### P2 — Nice to Have (Future)

Post-V1 features that expand the tool's capabilities.

| ID | Feature | Module | Description |
|----|---------|--------|-------------|
| F-201 | Podcast hosting API integration | Mastering | Auto-publish to Spotify, Apple Podcasts, Podbean, etc. |
| F-202 | RSS feed generation | Mastering | Generate/update podcast RSS feed XML |
| F-203 | Audiogram generation | Mastering | Auto-generate shareable video clips with waveforms and captions |
| F-204 | Transcript search | Ingestion | Full-text search across episode transcripts |
| F-205 | Multi-episode batch processing | Pipeline | Process multiple episodes in a queue |
| F-206 | VST/AU plugin | All | Run PodAgent as a plugin inside a DAW |
| F-207 | Windows support | All | Native Windows installation (not just WSL) |
| F-208 | Vocal separation (Demucs) | Ingestion | Separate speech from background music for mixed sources |
| F-209 | Translation | Ingestion | Translate transcripts to other languages |
| F-210 | Clock drift correction | Ingestion | Detect and correct gradual timing drift in multi-track recordings |
| F-211 | Cloud deployment | Pipeline | Run as a hosted service with multi-user support |
| F-212 | Transcript editor UI | Pipeline | Rich web UI for editing transcripts at Gate 1 |

---

## 5. Non-Functional Requirements

### Performance

| Metric | Target | Condition |
|--------|--------|-----------|
| End-to-end processing time | < 25 minutes | 1-hour, 2-track episode, Mac M2 Pro (local Whisper) |
| End-to-end processing time | < 15 minutes | 1-hour, 2-track episode, Linux + RTX 4090 |
| Ingestion (transcription) | < 15 min | 1-hour episode, Mac M2 Pro with whisper.cpp |
| Editing (LLM analysis) | < 90 seconds | 1-hour episode, Claude API |
| Mixing (FFmpeg processing) | < 10 min | 1-hour episode |
| Mastering (normalization + encoding) | < 4 min | 1-hour episode |
| Gate response time | Instant | Pipeline pauses until human acts |

### Reliability

| Requirement | Description |
|-------------|-------------|
| **Crash recovery** | Pipeline is fully resumable. Re-running after a crash resumes from the last completed stage. |
| **Atomic writes** | All output files are written atomically (write temp, rename) to prevent corruption. |
| **API failure tolerance** | Transient API failures (Claude, Whisper) are retried 3× with exponential backoff. Permanent failures degrade gracefully. |
| **Source preservation** | Source audio files are NEVER modified. All edits are expressed as EDLs. |
| **Idempotent re-execution** | Re-running a completed stage produces the same output (deterministic, except for LLM calls). |

### Scalability

| Scenario | Support |
|----------|---------|
| Episode length | Up to 5 hours (18,000 seconds) |
| Track count | Up to 8 simultaneous tracks |
| Episodes per project | 1 (each episode is a separate project directory) |
| Concurrent pipeline runs | Not supported in MVP (single sequential pipeline) |
| File sizes | Up to 4 GB per source track (WAV, 48kHz, 24-bit, 5 hours) |

### Security & Privacy

| Requirement | Description |
|-------------|-------------|
| **Local-first processing** | Audio processing, transcription, and mixing run locally by default. No audio is uploaded to cloud services unless the user explicitly configures a cloud provider (Whisper API, Auphonic, Dolby.io). |
| **API key management** | API keys (Anthropic, HuggingFace, Auphonic, Dolby.io) are stored in environment variables or a local `.env` file, never in the manifest or committed to version control. |
| **No telemetry** | PodAgent OS does not collect usage data, analytics, or telemetry of any kind. |
| **Transcript privacy** | Transcripts sent to the Claude API for context extraction and tangent detection contain the full spoken content. Users must be aware that this content is sent to Anthropic's servers. A future local LLM option (F-2xx) could eliminate this. |

### Compatibility

| Platform | Support Level |
|----------|-------------|
| macOS 13+ (Ventura) on Apple Silicon | Primary — fully tested |
| macOS 13+ on Intel | Supported — slower transcription (no Metal) |
| Ubuntu 22.04+ / Debian 12+ | Primary — fully tested |
| Other Linux distros | Best-effort — should work if FFmpeg and Python 3.11+ are available |
| Windows | Not supported in MVP (use WSL2) |
| Python | 3.11+ required |
| FFmpeg | 5.0+ required (6.x recommended) |

---

## 6. Success Metrics

### For Individual Users

| Metric | Target | How to Measure |
|--------|--------|---------------|
| **Time saved per episode** | ≥ 70% reduction vs. manual workflow | User survey: compare time before/after PodAgent |
| **Gate approval rate** | ≥ 80% of proposed edits approved without modification | Track approve/modify/reject counts in manifest gate_notes |
| **Output loudness compliance** | 100% of episodes within ±0.5 LU of -16 LUFS | Automated verification in Module 4 |
| **Transcription accuracy** | ≥ 95% word accuracy for clear English speech | Benchmark against manually corrected transcripts |
| **DAW import success rate** | ≥ 95% of EDLs import cleanly | Test with Pro Tools, Audition, Resolve |

### For the Project

| Metric | Target | Timeline |
|--------|--------|----------|
| **GitHub stars** | 500+ | 6 months post-launch |
| **Active users** (run the pipeline at least 1×/week) | 100+ | 6 months post-launch |
| **Issues resolved** | ≥ 80% of reported issues resolved within 2 weeks | Ongoing |
| **Contributor PRs merged** | ≥ 10 external contributions | 12 months post-launch |

---

## 7. Out of Scope

The following are explicitly NOT part of PodAgent OS, at any priority level:

| Item | Reason |
|------|--------|
| **Live streaming** | PodAgent is a post-production tool. Live processing has entirely different latency and architecture requirements. |
| **Video editing** | Audio-only. Video podcast workflows (e.g., YouTube) are a separate problem. |
| **Music production** | Optimized for speech. Noise reduction, compression, and editing algorithms assume spoken content. |
| **DAW replacement** | PodAgent complements DAWs, not replaces them. The EDL export is the bridge. |
| **Podcast hosting** | We produce deliverables; hosting/distribution is the user's choice. (P2 features may add API integration.) |
| **Listener-facing features** | No player, no recommendation engine, no analytics dashboard. |
| **Multi-user collaboration** | Single-user local tool in V1. No accounts, permissions, or shared state. |
| **Mobile app** | CLI-first. Mobile is a fundamentally different UX. |
| **Real-time preview** | Processing is batch-mode. No real-time audio playback during processing (though the web UI gate may offer playback of finished artifacts). |
| **Training custom AI models** | We use off-the-shelf models (Whisper, pyannote, Claude). No fine-tuning or model training. |

---

## 8. Open Questions

| # | Question | Impact | Owner | Status |
|---|----------|--------|-------|--------|
| 1 | **Should there be a Gate 4 after mastering?** The architecture currently has no final review after Module 4. A producer should be able to listen to the mastered MP3 before it's marked "complete." | Medium — affects pipeline design | Architect | Open |
| 2 | **Intra-module resume**: Should the pipeline support partial resume within a module (e.g., skip already-transcribed tracks if Module 1 fails at track 3 of 4)? | Medium — adds complexity, saves time for long episodes | Architect | Open |
| 3 | **Local LLM option**: Should we support a local LLM (e.g., Llama) as an alternative to Claude API for context extraction and tangent detection? This would eliminate cloud dependency and improve privacy but likely reduce quality. | Low for MVP, High for privacy-focused users | Researcher | Open |
| 4 | **Stereo channel handling**: When a stereo track is provided, which channel do we use? The spec assumes "left = primary mic" but this is unreliable. Should we analyze both channels and pick the one with more speech energy? | Low — affects edge case only | Spec Writer | Open |
| 5 | **Backward gate navigation state machine**: When a user rejects at Gate 3 and goes back to Gate 2, what are the exact manifest state transitions? Are Module 2's artifacts preserved or regenerated? | Medium — affects pipeline implementation | Architect | Open |
| 6 | **Pricing for cloud providers**: Auphonic and Dolby.io pricing may change. Should the pipeline estimate and display cost before using a cloud provider? | Low | Spec Writer | Open |
| 7 | **Transcript format for the LLM**: Should we send plain text or structured JSON to Claude for tangent detection? JSON is larger (3-4× more tokens) but preserves timestamps. Plain text is cheaper but loses timing. | Medium — affects cost and accuracy | Spec Writer | Open |
| 8 | **macOS vs Linux parity**: `faster-whisper` doesn't support Apple Silicon GPU. The recommended stack differs by platform (whisper.cpp on Mac, faster-whisper on Linux). Should we abstract this behind a provider interface, or document the platform differences? | Medium — affects developer experience | Architect | Open |
