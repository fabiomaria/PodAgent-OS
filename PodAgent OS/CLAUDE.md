# PodAgent OS — Claude Code Project Guide

## What Is This?
PodAgent OS is an AI-powered podcast production pipeline that automates the end-to-end workflow from raw multi-track audio to a mastered, tagged, publishable episode. This project is in the **architecture and specification phase**.

## Project Structure
```
podagent-os/
├── CLAUDE.md              ← You are here (orchestrator prompt)
├── agents/                ← Specialized agent prompts
│   ├── architect.md       ← System design & architecture agent
│   ├── spec-writer.md     ← PRD & technical spec agent
│   ├── researcher.md      ← Technology research & feasibility agent
│   └── reviewer.md        ← Spec review & gap analysis agent
├── docs/                  ← Architecture documents (outputs)
│   ├── architecture.md    ← System design document
│   ├── data-flow.md       ← Data flow & pipeline design
│   └── api-contracts.md   ← Internal API contracts between modules
├── specs/                 ← Technical specifications (outputs)
│   ├── prd.md             ← Product Requirements Document
│   ├── module-ingestion.md
│   ├── module-editing.md
│   ├── module-mixing.md
│   └── module-mastering.md
```

## Agent Architecture
This project uses a **hub-and-spoke agent model**:

- **You (the orchestrator)** coordinate work by delegating to specialized agents
- Each agent has a focused role and writes to specific output files
- Agents can be invoked with: `/run agents/<agent-name>.md`

### Agent Roles
| Agent | Role | Outputs |
|-------|------|---------|
| `architect` | Designs the system, defines module boundaries, data flow, and tech stack decisions | `docs/architecture.md`, `docs/data-flow.md`, `docs/api-contracts.md` |
| `spec-writer` | Writes detailed PRD and per-module technical specs | `specs/prd.md`, `specs/module-*.md` |
| `researcher` | Investigates feasibility of specific technologies (Whisper, Auphonic, FFmpeg, EDL formats) | Inline findings added to relevant docs |
| `reviewer` | Reviews all docs for gaps, contradictions, and missing edge cases | Adds `> [REVIEW]` callouts inline |

## How to Work
1. Start with the **architect** agent to define the system boundaries
2. Then use **researcher** to validate tech choices
3. Hand off to **spec-writer** for detailed module specs
4. Run **reviewer** as a final pass

## Core Feature Modules
1. **Ingestion & Context Mapping** — Transcription, multi-track sync, context grounding
2. **Narrative & Content Editing** — Semantic tangent detection, smart silence/filler removal, EDL output
3. **Audio Processing & Mixing** — Auto-ducking, AI noise separation, crossfade generation
4. **Mastering & Publishing** — Loudness normalization, true-peak limiting, metadata/show notes

## Key Design Constraints
- Non-destructive editing: always output EDLs, never modify source audio directly
- Human-in-the-loop: every automated decision must be reviewable/overridable
- Pipeline must be resumable: if a step fails, re-run from that step, not from scratch
- Format agnostic: support WAV, FLAC, MP3 inputs; output MP3 + WAV masters
- Must integrate with existing DAWs (Adobe Audition, Pro Tools) via standard EDL/AAF/OMF

## Tech Stack Considerations (To Be Validated)
- **Transcription**: OpenAI Whisper (local) or Whisper API
- **Audio Processing**: FFmpeg, SoX, Auphonic API, Dolby.io API
- **LLM Layer**: Claude API for semantic analysis (tangent detection, show notes)
- **EDL Format**: CMX 3600 or AAF for DAW compatibility
- **Language**: TBD — Python (rich audio ecosystem) vs TypeScript (better for web UI)
- **Orchestration**: Likely a DAG-based pipeline (like Prefect or custom)
