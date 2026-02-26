"""EDL generation — CMX 3600 via opentimelineio + JSON sidecar."""

from __future__ import annotations

from pathlib import Path

from podagent.models.edl import EDLSidecar, Edit, Transition
from podagent.models.transcript import Segment
from podagent.utils.io import write_json
from podagent.utils.progress import log_step, log_warning


def build_edl(
    segments: list[Segment],
    cut_edits: list[Edit],
    *,
    episode_id: str = "",
    frame_rate: int = 30,
    crossfade_duration_ms: int = 50,
) -> EDLSidecar:
    """Build an EDL from transcript segments and cut edits.

    Creates keep edits from the gaps between cuts, and assembles
    the full edit list with record-time positions.
    """
    total_duration = segments[-1].end if segments else 0

    # Sort cuts by start time
    cuts = sorted(cut_edits, key=lambda e: e.source_start)

    # Build keep regions (everything not in a cut)
    keep_edits: list[Edit] = []
    keep_counter = 0
    current_pos = 0.0
    record_pos = 0.0

    for cut in cuts:
        # Keep region before this cut
        if cut.source_start > current_pos:
            duration = cut.source_start - current_pos
            keep_counter += 1

            # Find segments in this keep region
            region_segments = [
                s for s in segments
                if s.start >= current_pos and s.end <= cut.source_start
            ]
            speaker = region_segments[0].speaker if region_segments else ""

            keep_edits.append(Edit(
                id=f"keep-{keep_counter:03d}",
                type="keep",
                source_track="",  # Will be set per-track in mixing
                source_start=current_pos,
                source_end=cut.source_start,
                record_start=record_pos,
                record_end=record_pos + duration,
                transition="cut" if keep_counter == 1 else "crossfade",
                speaker=speaker,
                description=_summarize_region(region_segments),
                segments=[s.id for s in region_segments],
            ))
            record_pos += duration

        current_pos = cut.source_end

    # Final keep region after last cut
    if current_pos < total_duration:
        duration = total_duration - current_pos
        keep_counter += 1
        region_segments = [
            s for s in segments if s.start >= current_pos
        ]
        speaker = region_segments[0].speaker if region_segments else ""

        keep_edits.append(Edit(
            id=f"keep-{keep_counter:03d}",
            type="keep",
            source_track="",
            source_start=current_pos,
            source_end=total_duration,
            record_start=record_pos,
            record_end=record_pos + duration,
            transition="crossfade",
            speaker=speaker,
            description=_summarize_region(region_segments),
            segments=[s.id for s in region_segments],
        ))
        record_pos += duration

    # Build transitions
    transitions: list[Transition] = []
    for i in range(len(keep_edits) - 1):
        transitions.append(Transition(
            between=[keep_edits[i].id, keep_edits[i + 1].id],
            type="crossfade",
            duration_ms=crossfade_duration_ms,
        ))

    # Combine all edits
    all_edits = keep_edits + cuts

    edited_duration = record_pos
    time_removed = total_duration - edited_duration
    time_removed_pct = (time_removed / total_duration * 100) if total_duration > 0 else 0

    sidecar = EDLSidecar(
        episode_id=episode_id,
        original_duration_seconds=total_duration,
        edited_duration_seconds=edited_duration,
        time_removed_seconds=time_removed,
        time_removed_percent=round(time_removed_pct, 1),
        edl_frame_rate=frame_rate,
        edits=all_edits,
        transitions=transitions,
    )

    log_step(
        "EDL",
        f"Built EDL: {len(keep_edits)} keep, {len(cuts)} cut, "
        f"{time_removed:.0f}s removed ({time_removed_pct:.1f}%)",
    )

    return sidecar


def write_edl_files(
    sidecar: EDLSidecar,
    output_dir: Path,
    *,
    tracks: dict[str, str] | None = None,
) -> None:
    """Write EDL files: JSON sidecar and CMX 3600 EDL."""
    # JSON sidecar
    write_json(output_dir / "edit-list.json", sidecar.model_dump(mode="json"))

    # CMX 3600 EDL
    _write_cmx3600(sidecar, output_dir / "edit-list.edl")


def _write_cmx3600(sidecar: EDLSidecar, output_path: Path) -> None:
    """Write a CMX 3600 EDL file.

    Try opentimelineio first, fall back to manual generation.
    """
    try:
        _write_cmx3600_otio(sidecar, output_path)
    except ImportError:
        log_warning("opentimelineio not available — generating EDL manually")
        _write_cmx3600_manual(sidecar, output_path)


def _write_cmx3600_otio(sidecar: EDLSidecar, output_path: Path) -> None:
    """Generate CMX 3600 EDL via opentimelineio."""
    import opentimelineio as otio

    fps = sidecar.edl_frame_rate
    timeline = otio.schema.Timeline(name=sidecar.episode_id)
    track = otio.schema.Track(name="V1", kind=otio.schema.TrackKind.Audio)

    for edit in sidecar.keep_edits:
        duration_frames = int((edit.source_end - edit.source_start) * fps)
        start_frames = int(edit.source_start * fps)

        clip = otio.schema.Clip(
            name=edit.id,
            source_range=otio.opentime.TimeRange(
                start_time=otio.opentime.RationalTime(start_frames, fps),
                duration=otio.opentime.RationalTime(duration_frames, fps),
            ),
        )
        track.append(clip)

    timeline.tracks.append(track)
    otio.adapters.write_to_file(timeline, str(output_path), adapter_name="cmx_3600")


def _write_cmx3600_manual(sidecar: EDLSidecar, output_path: Path) -> None:
    """Generate CMX 3600 EDL manually (no dependencies)."""
    fps = sidecar.edl_frame_rate
    lines = [
        f"TITLE: {sidecar.episode_id}",
        "FCM: NON-DROP FRAME",
        "",
    ]

    for i, edit in enumerate(sidecar.keep_edits, start=1):
        src_in = _seconds_to_tc(edit.source_start, fps)
        src_out = _seconds_to_tc(edit.source_end, fps)
        rec_in = _seconds_to_tc(edit.record_start or 0, fps)
        rec_out = _seconds_to_tc(edit.record_end or 0, fps)

        reel = f"REEL{i:04d}"
        transition = "C" if edit.transition == "cut" else f"D {sidecar.edl_frame_rate:03d}"

        lines.append(
            f"{i:03d}  {reel}  AA/V  {transition}        "
            f"{src_in} {src_out} {rec_in} {rec_out}"
        )
        if edit.description:
            lines.append(f"* COMMENT: {edit.description[:60]}")
        lines.append("")

    output_path.write_text("\n".join(lines))


def _seconds_to_tc(seconds: float, fps: int) -> str:
    """Convert seconds to SMPTE timecode HH:MM:SS:FF."""
    total_frames = int(seconds * fps)
    ff = total_frames % fps
    total_seconds = total_frames // fps
    ss = total_seconds % 60
    mm = (total_seconds // 60) % 60
    hh = total_seconds // 3600
    return f"{hh:02d}:{mm:02d}:{ss:02d}:{ff:02d}"


def _summarize_region(segments: list[Segment]) -> str:
    """Create a short description of a keep region."""
    if not segments:
        return ""
    speakers = sorted(set(s.speaker for s in segments))
    duration = segments[-1].end - segments[0].start if len(segments) > 1 else segments[0].duration
    return f"{', '.join(speakers)} ({duration:.0f}s)"
