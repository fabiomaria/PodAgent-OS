"""Per-track audio processing: noise reduction, compression, de-essing."""

from __future__ import annotations

from pathlib import Path

from podagent.models.config import MixingConfig
from podagent.utils.ffmpeg import apply_filter
from podagent.utils.progress import log_step, log_warning


def process_region(
    input_path: Path,
    output_path: Path,
    config: MixingConfig,
) -> list[dict]:
    """Apply the processing chain to a single audio region.

    Returns a list of processing step records for the mixing log.
    """
    steps: list[dict] = []
    current_path = input_path

    # Step 1: Noise reduction
    if config.noise_reduction_provider != "none":
        nr_output = output_path.parent / f"{output_path.stem}_nr{output_path.suffix}"
        try:
            _apply_noise_reduction(current_path, nr_output, config)
            steps.append({
                "step": "noise_reduction",
                "provider": config.noise_reduction_provider,
                "filter": f"afftdn=nf={config.noise_floor_db}",
                "parameters": {"noise_floor_db": config.noise_floor_db},
            })
            current_path = nr_output
        except Exception as e:
            log_warning(f"Noise reduction failed: {e}. Skipping.")
            steps.append({
                "step": "noise_reduction",
                "provider": config.noise_reduction_provider,
                "skipped": True,
                "error": str(e),
            })

    # Step 2: Compression
    if config.compression_enabled:
        comp_output = output_path.parent / f"{output_path.stem}_comp{output_path.suffix}"
        threshold = config.compression_threshold_db
        ratio = config.compression_ratio
        attack = config.compression_attack_ms
        release = config.compression_release_ms

        filter_str = (
            f"acompressor=threshold={threshold}dB"
            f":ratio={ratio}"
            f":attack={attack}"
            f":release={release}"
            f":makeup=2dB"
        )

        try:
            apply_filter(current_path, comp_output, filter_str)
            steps.append({
                "step": "compression",
                "filter": filter_str,
                "parameters": {
                    "threshold_db": threshold,
                    "ratio": f"{ratio}:1",
                    "attack_ms": attack,
                    "release_ms": release,
                },
            })
            current_path = comp_output
        except Exception as e:
            log_warning(f"Compression failed: {e}. Skipping.")
            steps.append({"step": "compression", "skipped": True, "error": str(e)})

    # Step 3: De-essing (optional)
    if config.de_essing_enabled:
        de_ess_output = output_path.parent / f"{output_path.stem}_deess{output_path.suffix}"
        filter_str = "equalizer=f=7000:t=q:w=2:g=-6"
        try:
            apply_filter(current_path, de_ess_output, filter_str)
            steps.append({
                "step": "de_essing",
                "enabled": True,
                "filter": filter_str,
            })
            current_path = de_ess_output
        except Exception as e:
            log_warning(f"De-essing failed: {e}. Skipping.")
            steps.append({"step": "de_essing", "skipped": True, "error": str(e)})
    else:
        steps.append({"step": "de_essing", "enabled": False})

    # Copy final result to output path
    if current_path != output_path:
        import shutil
        shutil.copy2(current_path, output_path)

    return steps


def _apply_noise_reduction(
    input_path: Path,
    output_path: Path,
    config: MixingConfig,
) -> None:
    """Apply noise reduction using the configured provider."""
    if config.noise_reduction_provider == "ffmpeg":
        from podagent.mixing.providers.ffmpeg_nr import FFmpegNoiseReduction
        provider = FFmpegNoiseReduction()
        provider.process(
            str(input_path),
            str(output_path),
            noise_floor_db=config.noise_floor_db,
        )
    elif config.noise_reduction_provider == "auphonic":
        from podagent.mixing.providers.auphonic import AuphonicNoiseReduction
        provider = AuphonicNoiseReduction()
        provider.process(str(input_path), str(output_path))
    elif config.noise_reduction_provider == "dolby":
        from podagent.mixing.providers.dolby import DolbyNoiseReduction
        provider = DolbyNoiseReduction()
        provider.process(str(input_path), str(output_path))
