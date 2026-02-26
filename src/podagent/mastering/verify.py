"""Post-mastering loudness verification."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from podagent.utils.progress import log_step, log_success, log_warning


def verify_output(
    mp3_path: Path,
    *,
    target_lufs: float = -16.0,
    target_tp: float = -1.0,
    tolerance_lu: float = 0.5,
) -> dict:
    """Measure the mastered output and verify it meets targets.

    Returns verification results dict.
    """
    log_step("Verify", "Measuring output loudness...")

    result = subprocess.run(
        [
            "ffmpeg", "-hide_banner",
            "-i", str(mp3_path),
            "-af", "ebur128=peak=true",
            "-f", "null", "-",
        ],
        capture_output=True,
        text=True,
    )

    measurements = _parse_ebur128(result.stderr)

    integrated = measurements.get("I", 0.0)
    peak = measurements.get("peak", 0.0)
    lra = measurements.get("LRA", 0.0)

    lufs_ok = abs(integrated - target_lufs) <= tolerance_lu
    tp_ok = peak <= target_tp

    verification = {
        "integrated_lufs": integrated,
        "true_peak_dbtp": peak,
        "loudness_range_lu": lra,
        "lufs_on_target": lufs_ok,
        "tp_within_ceiling": tp_ok,
        "passed": lufs_ok and tp_ok,
    }

    if lufs_ok and tp_ok:
        log_success(
            f"Verification passed: {integrated:.1f} LUFS, "
            f"{peak:.1f} dBTP, LRA {lra:.1f} LU"
        )
    else:
        warnings = []
        if not lufs_ok:
            warnings.append(
                f"Loudness {integrated:.1f} LUFS deviates from "
                f"target {target_lufs} by more than {tolerance_lu} LU"
            )
        if not tp_ok:
            warnings.append(
                f"True peak {peak:.1f} dBTP exceeds ceiling {target_tp} dBTP"
            )
        for w in warnings:
            log_warning(w)
        verification["warnings"] = warnings

    return verification


def _parse_ebur128(stderr: str) -> dict:
    """Parse ebur128 summary from FFmpeg stderr."""
    measurements = {"I": 0.0, "peak": 0.0, "LRA": 0.0}

    # Look for "Summary:" section
    lines = stderr.split("\n")
    in_summary = False

    for line in lines:
        if "Summary:" in line:
            in_summary = True
            continue

        if in_summary:
            # Integrated loudness
            m = re.search(r"I:\s+([-\d.]+)\s+LUFS", line)
            if m:
                measurements["I"] = float(m.group(1))

            # LRA
            m = re.search(r"LRA:\s+([-\d.]+)\s+LU", line)
            if m:
                measurements["LRA"] = float(m.group(1))

            # True peak
            m = re.search(r"Peak:\s+([-\d.]+)\s+dBFS", line)
            if m:
                measurements["peak"] = float(m.group(1))

    return measurements
