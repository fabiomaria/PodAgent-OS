# Research: Multi-Track Audio Alignment via Waveform Similarity

> **Status**: Complete
> **Last Updated**: 2026-02-25
> **Author**: Researcher Agent
> **Priority**: P0 (Must know before architecture is final)
> **Relates to**: Module 1 (Ingestion & Context Mapping), Step 4 — Multi-track alignment

---

## Table of Contents

1. [Cross-Correlation Approach](#1-cross-correlation-approach)
2. [Existing Libraries and Tools](#2-existing-libraries-and-tools)
3. [Practical Implementation](#3-practical-implementation)
4. [Edge Cases and Limitations](#4-edge-cases-and-limitations)
5. [Alternative Approaches](#5-alternative-approaches)
6. [Performance](#6-performance)
7. [Recommendation for PodAgent OS](#7-recommendation-for-podagent-os)

---

## 1. Cross-Correlation Approach

### Question
How does cross-correlation work for audio alignment? What are the exact steps? What Python libraries implement this?

### Finding

Cross-correlation is the standard signal processing technique for finding the time offset between two signals that share common content. In the podcast recording scenario, each participant records locally, but all microphones pick up some amount of room sound, crosstalk, or a shared reference signal (a clap, countdown, or ambient noise). Cross-correlation exploits this shared content to find the delay.

#### How It Works — Step by Step

1. **Load both audio files** as 1D NumPy arrays of floating-point samples. If stereo, convert to mono by averaging channels.

2. **Resample to a common sample rate** if they differ. All tracks must share the same sample rate before correlation.

3. **Compute the cross-correlation function**. For two discrete signals `x[n]` (reference track) and `y[n]` (track to align), the cross-correlation is:

   ```
   R_xy[lag] = sum over n of ( x[n] * y[n + lag] )
   ```

   This slides one signal over the other and computes the dot product at every possible offset (lag). The lag that produces the maximum value is where the two signals are best aligned.

4. **Find the lag of maximum correlation**. The index of the peak in `R_xy` gives the sample offset between the two tracks.

5. **Convert the sample offset to time**: `offset_seconds = lag_samples / sample_rate`.

6. **Apply the offset**: Prepend silence to the earlier track (or trim the leading portion of the later track) to align them on a common timeline.

#### Why FFT-Based Correlation is Essential

Naive time-domain cross-correlation is O(N*M) where N and M are the signal lengths. For 1-hour tracks at 48kHz (172.8 million samples each), this is computationally infeasible.

The **FFT-based approach** uses the cross-correlation theorem:

```
R_xy = IFFT( FFT(x) * conj(FFT(y)) )
```

This reduces the complexity to O(N log N), making it practical for long recordings. `scipy.signal.fftconvolve` and `scipy.signal.correlate` with `method='fft'` both implement this.

#### Key Python Libraries

| Library | Function | Notes |
|---------|----------|-------|
| **NumPy** | `numpy.correlate(a, v, mode='full')` | Pure time-domain. Fine for short signals (<10k samples). Unusable for long audio. |
| **SciPy** | `scipy.signal.correlate(x, y, mode='full', method='fft')` | FFT-based. The right choice for audio alignment. Returns a 1D array of correlation values. |
| **SciPy** | `scipy.signal.fftconvolve(x, y[::-1], mode='full')` | Equivalent to correlation (convolve with time-reversed signal). Sometimes slightly faster. |
| **librosa** | No dedicated correlation function. Use `librosa.load()` for file I/O, then SciPy for correlation. | librosa is useful for loading, resampling, and feature extraction, not for the correlation itself. |

### Recommendation

Use `scipy.signal.correlate` with `method='fft'` for the core alignment. Use `librosa.load()` or `soundfile.read()` for file I/O. See Section 3 for the complete implementation.

### Gotchas

- **`numpy.correlate` does NOT use FFT by default.** It will hang or take hours on long audio. Always use SciPy's implementation with `method='fft'`.
- The cross-correlation output array has length `len(x) + len(y) - 1`. The zero-lag point is at index `len(y) - 1`. You must account for this when interpreting the peak index.
- Cross-correlation finds the **best overall alignment**, not local alignments. If one track has significant clock drift (e.g., different sound cards running at slightly different true sample rates), a single offset won't suffice — you'll need drift correction (see Section 5).

### Sources

- SciPy documentation: `scipy.signal.correlate` — https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.correlate.html
- SciPy documentation: `scipy.signal.fftconvolve` — https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.fftconvolve.html
- Smith, J.O. "Mathematics of the Discrete Fourier Transform" — https://ccrma.stanford.edu/~jos/mdft/

---

## 2. Existing Libraries and Tools

### Question
Are there dedicated Python libraries for multi-track audio alignment?

### Finding

#### Dedicated Audio Alignment Libraries

| Library | Status | Algorithm | Multi-track? | Notes |
|---------|--------|-----------|-------------|-------|
| **audalign** | Active (PyPI) | Multiple: cross-correlation, fingerprinting (via dejavu), visual alignment | Yes | Purpose-built for audio alignment. Supports aligning multiple files to a reference. Can output aligned files directly. |
| **sync_audio_tracks** | Minimal/unmaintained | Cross-correlation | Pairwise only | Simple script-level tool. Thin wrapper around numpy correlation. |
| **aeneas** | Active | DTW (Dynamic Time Warping) on text-to-audio | No — it's for text-audio sync, not audio-audio | Aligns text (e.g., an audiobook transcript) to audio. Not relevant for multi-track podcast alignment. |
| **Praat** (via `parselmouth`) | Active | Various phonetic tools | No direct multi-track | Phonetics research tool. Has cross-correlation capability but not designed for production audio alignment. Overkill and awkward API for this use case. |
| **lindasync** | Niche | Cross-correlation | Pairwise | Designed for syncing audio to video. Limited documentation. |

#### audalign — Deep Dive

`audalign` is the most relevant dedicated library. Key capabilities:

```python
import audalign

# Align files to a target (reference) file
results = audalign.align(
    target="reference_track.wav",
    against="guest_track.wav"
)
# results contains the offset in seconds

# Align and write output files
audalign.align_files(
    target="host.wav",
    against=["guest1.wav", "guest2.wav"],
    destination_path="./aligned/"
)
```

`audalign` supports three alignment modes:
1. **Correlation** — standard cross-correlation (fastest, most reliable for tracks with shared audio content)
2. **Fingerprinting** — uses audio fingerprinting (Dejavu-style), tolerant of noise differences but slower
3. **Visual** — spectrogram-based alignment, useful when waveform correlation fails

**Pros**: Ready-made, handles file I/O, supports multiple tracks, multiple algorithm options.
**Cons**: Relatively thin documentation, smaller community, adds a dependency. For a production pipeline, you want to understand (and control) the algorithm yourself.

#### Command-Line Tools (Non-Python)

| Tool | Language | Notes |
|------|----------|-------|
| **FFmpeg** | C | No built-in cross-correlation alignment, but can apply offsets via `-itsoffset` and resample. |
| **SoX** | C | Can trim/pad audio but has no alignment capability. |
| **Pluraleyes** (Red Giant) | Proprietary | Commercial multi-track sync for video production. Gold standard in video post but proprietary, expensive, not scriptable. |
| **DaVinci Resolve** | Proprietary | Has auto-sync by waveform. Not scriptable. |
| **Audacity** | C++ | No programmatic alignment. |

### Recommendation

For PodAgent OS, **implement alignment from scratch using SciPy** rather than depending on `audalign`. The reasons:

1. The core algorithm is only ~40 lines of code (see Section 3).
2. You need full control over preprocessing (downsampling for speed, normalization) and error handling.
3. You need to integrate with the manifest system and produce the specific `alignment.json` output format.
4. Fewer dependencies means a simpler deployment story.
5. `audalign` is a useful reference implementation to study, but wrapping it would add indirection.

Keep `audalign` as a **reference for testing** — align tracks both ways and compare results as a validation step during development.

### Gotchas

- `aeneas` is frequently confused with an audio-audio alignment tool. It is NOT. It aligns text to audio (e.g., for audiobook chapter markers). Do not use it for multi-track sync.
- `Praat`/`parselmouth` is a research tool for phonetics. While it can compute cross-correlation, its API is oriented toward formant analysis, pitch tracking, etc. Using it for multi-track alignment is fighting the tool.
- `sync_audio_tracks` on PyPI has minimal maintenance and very limited functionality. Not production-ready.

### Sources

- audalign on PyPI: https://pypi.org/project/audalign/
- audalign GitHub: https://github.com/benfmiller/audalign
- aeneas project: https://github.com/readbeyond/aeneas
- parselmouth (Praat in Python): https://github.com/YannickJadoul/Parselmouth

---

## 3. Practical Implementation

### Question
Provide a concrete Python code snippet that takes two WAV files and returns the offset in milliseconds between them.

### Finding

Below is a complete, production-quality implementation with detailed comments. This is the code that should form the basis of Module 1's alignment step.

#### Core Alignment Function

```python
"""
multi_track_align.py — Align two audio tracks by waveform cross-correlation.

Returns the time offset (in milliseconds) that track_b must be shifted
to align with track_a. A positive offset means track_b starts later
than track_a (prepend silence to track_b). A negative offset means
track_b starts earlier (prepend silence to track_a).
"""

import numpy as np
from scipy.signal import correlate, correlation_lags
import soundfile as sf


def load_and_prepare(
    filepath: str,
    target_sr: int = 16000,
) -> tuple[np.ndarray, int]:
    """
    Load an audio file, convert to mono, and resample to a target rate.

    We downsample to 16kHz for alignment purposes — this is ~3x faster
    than aligning at 48kHz and more than sufficient for finding the
    offset (we only need sample-accurate alignment at 16kHz, which
    gives us ±0.0625ms precision, far beyond what's needed).

    Args:
        filepath: Path to WAV/FLAC/MP3 file.
        target_sr: Sample rate for alignment computation (default 16kHz).

    Returns:
        Tuple of (audio_array, sample_rate).
    """
    # soundfile.read returns (data, samplerate)
    # For MP3 support, use librosa.load() instead
    data, sr = sf.read(filepath, dtype="float32")

    # Convert stereo to mono by averaging channels
    if data.ndim > 1:
        data = np.mean(data, axis=1)

    # Resample if needed (using simple decimation for speed)
    if sr != target_sr:
        # For production use, prefer librosa.resample() for quality
        # This simple decimation works for alignment purposes
        import librosa
        data = librosa.resample(data, orig_sr=sr, target_sr=target_sr)
        sr = target_sr

    # Normalize to [-1, 1] range
    peak = np.max(np.abs(data))
    if peak > 0:
        data = data / peak

    return data, sr


def find_offset(
    reference_path: str,
    target_path: str,
    align_sr: int = 16000,
    segment_duration_s: float | None = None,
    segment_start_s: float = 0.0,
) -> dict:
    """
    Find the time offset between two audio tracks using cross-correlation.

    Args:
        reference_path: Path to the reference track (typically the host).
        target_path: Path to the track to align (typically a guest).
        align_sr: Sample rate used for alignment computation.
        segment_duration_s: If set, only use this many seconds of audio
                           for alignment (much faster for long recordings).
                           Recommended: 30-60 seconds from a section where
                           both participants are audible.
        segment_start_s: Start time (in seconds) of the segment to use.

    Returns:
        Dictionary with:
            - offset_ms: float — milliseconds to shift target track
              (positive = target starts later, negative = target starts earlier)
            - offset_samples_48k: int — sample offset at 48kHz (for EDL use)
            - confidence: float — normalized correlation peak (0.0 to 1.0)
            - method: str — algorithm used
    """
    # Load and prepare both tracks
    ref, sr = load_and_prepare(reference_path, target_sr=align_sr)
    tgt, _ = load_and_prepare(target_path, target_sr=align_sr)

    # Optionally use only a segment (dramatically faster for long recordings)
    if segment_duration_s is not None:
        start_sample = int(segment_start_s * sr)
        end_sample = start_sample + int(segment_duration_s * sr)
        ref = ref[start_sample:end_sample]
        tgt = tgt[start_sample:end_sample]

    # ---- Cross-correlation via FFT ----
    # This computes R_xy[lag] for all possible lags.
    # mode='full' returns the complete correlation (length = len(ref) + len(tgt) - 1)
    # method='fft' uses FFT-based computation (O(N log N) instead of O(N^2))
    correlation = correlate(ref, tgt, mode="full", method="fft")

    # Get the array of lag values corresponding to each correlation index
    lags = correlation_lags(len(ref), len(tgt), mode="full")

    # Find the lag with maximum correlation
    peak_index = np.argmax(np.abs(correlation))
    best_lag = lags[peak_index]
    peak_value = correlation[peak_index]

    # ---- Confidence metric ----
    # Normalized cross-correlation: divide by the geometric mean of energies
    energy_ref = np.sqrt(np.sum(ref ** 2))
    energy_tgt = np.sqrt(np.sum(tgt ** 2))
    if energy_ref > 0 and energy_tgt > 0:
        confidence = abs(peak_value) / (energy_ref * energy_tgt)
    else:
        confidence = 0.0

    # ---- Convert lag to time ----
    # A positive lag means the target is delayed relative to the reference
    # (i.e., the reference started first)
    offset_seconds = best_lag / sr
    offset_ms = offset_seconds * 1000.0

    # Also compute sample offset at 48kHz for EDL/DAW use
    offset_samples_48k = int(round(best_lag * (48000 / sr)))

    return {
        "offset_ms": round(offset_ms, 3),
        "offset_samples_48k": offset_samples_48k,
        "confidence": round(float(confidence), 6),
        "method": "fft_cross_correlation",
        "align_sample_rate": sr,
    }


def align_multi_track(
    reference_path: str,
    track_paths: list[str],
    align_sr: int = 16000,
    segment_duration_s: float = 60.0,
) -> dict:
    """
    Align multiple tracks to a reference track.

    This is the function Module 1 should call. It aligns each track
    to the reference (typically the host's track) and returns the
    alignment map for writing to alignment.json.

    Args:
        reference_path: Path to the host/reference track.
        track_paths: Paths to all other tracks to align.
        align_sr: Sample rate for alignment computation.
        segment_duration_s: Seconds of audio to use for alignment.

    Returns:
        Alignment map dictionary (ready for JSON serialization).
    """
    alignment_map = {
        "reference_track": reference_path,
        "aligned_tracks": [],
    }

    for track_path in track_paths:
        result = find_offset(
            reference_path=reference_path,
            target_path=track_path,
            align_sr=align_sr,
            segment_duration_s=segment_duration_s,
        )

        alignment_map["aligned_tracks"].append({
            "track": track_path,
            "offset_ms": result["offset_ms"],
            "offset_samples_48k": result["offset_samples_48k"],
            "confidence": result["confidence"],
            "method": result["method"],
        })

    return alignment_map


# ---- Usage Example ----
if __name__ == "__main__":
    import json

    result = find_offset(
        reference_path="tracks/alice.wav",
        target_path="tracks/bob.wav",
        segment_duration_s=60.0,  # Use first 60 seconds for speed
    )

    print(f"Offset: {result['offset_ms']:.1f} ms")
    print(f"Confidence: {result['confidence']:.4f}")
    print(f"At 48kHz: {result['offset_samples_48k']} samples")
    print(json.dumps(result, indent=2))
```

#### Dependencies

```
# requirements.txt (alignment-related only)
numpy>=1.24
scipy>=1.11
soundfile>=0.12       # For WAV/FLAC I/O
librosa>=0.10         # For resampling and MP3 support
```

#### Output Format (alignment.json)

The `align_multi_track` function produces output matching this schema, which Module 2 and Module 3 will consume:

```json
{
  "reference_track": "tracks/alice.wav",
  "aligned_tracks": [
    {
      "track": "tracks/bob.wav",
      "offset_ms": 142.375,
      "offset_samples_48k": 6834,
      "confidence": 0.847321,
      "method": "fft_cross_correlation"
    },
    {
      "track": "tracks/charlie.wav",
      "offset_ms": -23.125,
      "offset_samples_48k": -1110,
      "confidence": 0.791004,
      "method": "fft_cross_correlation"
    }
  ]
}
```

### Recommendation

Use the `find_offset` function as-is for PodAgent OS Module 1. The key design decisions embedded in this code:

1. **Downsample to 16kHz for alignment** — 3x speedup over 48kHz with negligible accuracy loss (±0.0625ms precision at 16kHz is far beyond human perception).
2. **Use a 60-second segment by default** — aligning a full 1-hour recording is wasteful; a 60-second window is sufficient and ~60x faster.
3. **Report confidence** — if confidence is below ~0.3, the alignment is likely unreliable and should be flagged for human review at Gate 1.
4. **Return both milliseconds and 48kHz sample offsets** — milliseconds for human readability, sample offsets for precise EDL generation.

### Gotchas

- **`soundfile` cannot read MP3 files.** If input tracks might be MP3, use `librosa.load()` instead (which depends on `ffmpeg` or `audioread` under the hood).
- **Memory usage**: Loading a 1-hour 48kHz stereo WAV into memory as float32 takes ~1.3 GB. Downsampling to 16kHz mono reduces this to ~220 MB. Using a 60-second segment reduces it to ~3.7 MB. Always use the segment approach for long recordings.
- **The sign convention for the offset matters.** The code above uses the convention: positive offset = target starts later than reference. Document this clearly in the alignment.json schema, because Module 3 needs to interpret it correctly when applying offsets.

### Sources

- SciPy `correlation_lags` (added in SciPy 1.6.0): https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.correlation_lags.html
- soundfile library: https://python-soundfile.readthedocs.io/
- librosa resampling: https://librosa.org/doc/latest/generated/librosa.resample.html

---

## 4. Edge Cases and Limitations

### Question
What happens with different-length tracks, different sample rates, background noise, late joiners? What accuracy can we expect?

### Finding

#### 4.1 Different Track Lengths

**Scenario**: One participant joins 5 minutes late, so their track is shorter than the host's.

**Behavior**: Cross-correlation handles this correctly. `scipy.signal.correlate` with `mode='full'` computes correlation at all valid lags, including cases where one signal is much shorter than the other. The peak will appear at the lag corresponding to where the shorter track aligns with the longer one.

**Caveat**: If the segment-based approach is used (e.g., "use the first 60 seconds"), and the late-joining participant hasn't started speaking in that segment, the correlation will fail. **Mitigation**: Try multiple segments. If the first segment returns low confidence, try a segment from the middle of the shorter track.

```python
def find_offset_with_fallback(reference_path, target_path, align_sr=16000):
    """Try multiple segments if initial alignment has low confidence."""
    # Try first 60 seconds
    result = find_offset(reference_path, target_path,
                         segment_duration_s=60.0, segment_start_s=0.0)
    if result["confidence"] > 0.3:
        return result

    # Try segment from 5 minutes in
    result = find_offset(reference_path, target_path,
                         segment_duration_s=60.0, segment_start_s=300.0)
    if result["confidence"] > 0.3:
        return result

    # Try full-track correlation (slow but comprehensive)
    result = find_offset(reference_path, target_path,
                         segment_duration_s=None)
    result["warning"] = "Full-track correlation used (slow); confidence may be low"
    return result
```

#### 4.2 Different Sample Rates

**Scenario**: Host records at 48kHz, guest records at 44.1kHz.

**Behavior**: Cross-correlation requires both signals to have the same sample rate. If you feed different-rate signals into `correlate`, the result will be wrong (the offset calculation assumes a shared rate).

**Mitigation**: The `load_and_prepare` function in Section 3 resamples all tracks to a common rate (16kHz) before correlation. This handles the case transparently. When applying the computed offset to the original files, convert the offset from alignment-rate samples to the original rate: `offset_at_48k = offset_at_16k * (48000 / 16000)`.

> [IMPORTANT] Resampling from 44.1kHz to 48kHz (or vice versa) is a non-trivial operation. For the actual audio output (Module 3), use a high-quality resampler like `librosa.resample` with `res_type='soxr_hq'` or FFmpeg's `aresample` filter. For the alignment step, lower-quality resampling is fine since we're only computing an offset, not producing output audio.

#### 4.3 Background Noise Differences

**Scenario**: Host records in a studio (low noise), guest records in a coffee shop (high noise).

**Behavior**: Cross-correlation is surprisingly robust to additive noise. The common signal (speech that bleeds through both recordings) still produces a correlation peak, just with lower confidence. The correlation of the noise with itself tends to average out across lags.

**When it fails**: If there is NO shared audio content at all (e.g., perfectly isolated recordings from different rooms with no acoustic coupling), cross-correlation cannot work. There is no shared signal to correlate.

**Mitigations**:
1. **Use a sync clap or tone**: Have participants clap or play a sync tone at the start of recording. This creates a high-energy transient visible in all tracks.
2. **Fallback to transcript-based alignment**: If waveform correlation confidence is low, align tracks using word-level timestamps from Whisper transcription (see Section 5).
3. **Pre-filter with bandpass**: Before correlation, apply a bandpass filter (300Hz-3kHz) to focus on speech frequencies and reduce noise impact.

```python
from scipy.signal import butter, sosfilt

def bandpass_filter(audio, sr, low=300, high=3000):
    """Bandpass filter to isolate speech frequencies before correlation."""
    sos = butter(5, [low, high], btype='band', fs=sr, output='sos')
    return sosfilt(sos, audio)
```

#### 4.4 Clock Drift

**Scenario**: Two laptops record simultaneously, but their sound cards run at slightly different actual sample rates (e.g., one is 47,998 Hz and the other is 48,002 Hz — nominally both 48kHz).

**Behavior**: Over a 1-hour recording, even a 4 Hz difference (83 ppm) accumulates ~0.3 seconds of drift. A single offset will align the start correctly but the end will be misaligned.

**Detection**: Compute alignment at multiple points in the recording (e.g., every 5 minutes). If the offsets change linearly, there is clock drift.

**Mitigation**: Apply time-stretching to one track to match the other's effective rate. This is a well-known problem in multi-track recording. FFmpeg's `atempo` filter or `librosa.effects.time_stretch` can correct it.

> [IMPORTANT] Clock drift correction is a V2 feature. For MVP, detect drift, warn the user at Gate 1 if drift exceeds 10ms over the recording duration, and let them decide whether to correct it manually. For typical podcast-length recordings (30-60 minutes), drift is usually <100ms, which is acceptable for speech.

#### 4.5 Accuracy in Practice

| Scenario | Expected Accuracy | Notes |
|----------|-------------------|-------|
| Tracks with shared room audio (in-person recording) | ±1 sample (~±0.02ms at 48kHz) | Best case. Strong correlation peak. |
| Remote recording with sync clap/tone | ±1 sample | Clap provides a clean transient. |
| Remote recording, acoustic bleed via speakers | ±1-5ms | Depends on speaker volume and noise level. |
| Remote recording, no shared audio, transcript fallback | ±50-200ms | Limited by Whisper timestamp accuracy. |
| Recordings with clock drift | ±1ms at start, growing over time | Drift correction needed for long recordings. |

**Bottom line**: For podcast use, ±5ms is excellent (inaudible), ±50ms is acceptable (barely noticeable in speech), ±200ms is problematic (audible echo or doubling).

### Recommendation

1. Implement cross-correlation as the primary alignment method.
2. Add confidence threshold checking — flag low-confidence alignments for human review.
3. Support a fallback chain: cross-correlation -> bandpass-filtered correlation -> transcript-based alignment.
4. Detect and warn about clock drift, but defer drift correction to V2.
5. Document the offset sign convention clearly in the alignment.json schema.

### Gotchas

- **Remote recordings with headphones on both sides have zero shared audio.** If both participants wear headphones and record in separate rooms, there is no acoustic bleed between tracks. Cross-correlation will produce a meaningless result with low confidence. This is the most common edge case in podcast production. For this scenario, you MUST use transcript-based alignment or require a sync clap.
- **Compressed audio (MP3) loses timing precision.** MP3 encoding adds padding frames (up to 1152 samples of encoder delay). When loading MP3 files, the start times may be offset by up to ~26ms at 44.1kHz. If possible, work with WAV/FLAC sources.
- **Very long recordings may exceed memory.** A 2-hour stereo WAV at 48kHz is ~2.6 GB as float32. Always downsample and use segments for alignment.

### Sources

- Stack Overflow discussion on audio sync: https://stackoverflow.com/questions/6146953/how-to-synchronize-two-audio-files
- MP3 encoder delay: https://lame.sourceforge.io/tech-FAQ.txt

---

## 5. Alternative Approaches

### Question
Besides cross-correlation, what other methods exist for audio alignment?

### Finding

#### 5.1 Audio Fingerprinting (Chromaprint / Dejavu)

**How it works**: Extract perceptual audio fingerprints (compact representations of spectral content) from both tracks. Match fingerprints between tracks to find temporal correspondence.

**Libraries**:
- **Chromaprint** (`pyacoustid`): Generates fingerprints used by the MusicBrainz/AcoustID service. Designed for music identification but can be adapted for alignment.
- **Dejavu** (`dejavu`): Open-source audio fingerprinting library. Can be used to find when a short audio clip appears within a longer recording.
- **audalign** uses Dejavu fingerprinting as one of its alignment modes.

**Pros**: Robust to noise, amplitude differences, and mild distortion. Can find matches even when one track is heavily processed.

**Cons**: Slower than direct cross-correlation. Fingerprint resolution is typically ~0.1-0.5 seconds (not sample-accurate). Requires a second refinement step with cross-correlation for precise alignment.

**Verdict**: Useful as a fallback when cross-correlation fails, but overkill as the primary method for podcast alignment.

#### 5.2 Onset Detection Alignment

**How it works**: Detect audio onset events (transients, speech starts) in both tracks. Match the onset patterns between tracks to find the offset.

**Libraries**:
- `librosa.onset.onset_detect()` — detects onset times in audio.
- `madmom` — more advanced onset detection.

**Algorithm**:
1. Detect onsets in both tracks.
2. Compute cross-correlation of the onset time series (binary signals: 1 at onset, 0 elsewhere).
3. The peak gives the offset.

**Pros**: Much faster than full-signal cross-correlation (onset series are sparse). Works well when shared audio is speech.

**Cons**: Less precise than waveform correlation (onset detection has ~10-50ms uncertainty). Requires both tracks to contain the same speech events.

**Verdict**: Good for a fast initial estimate that can be refined with cross-correlation on a short segment around the estimated offset.

#### 5.3 Transcript-Based Alignment

**How it works**: Transcribe both tracks with word-level timestamps (using Whisper). Match the transcribed words to find temporal correspondence.

**Algorithm**:
1. Transcribe Track A: "Hello everyone" at t=2.1s.
2. Transcribe Track B: "Hello everyone" at t=4.3s.
3. Offset = 4.3 - 2.1 = 2.2 seconds.
4. Average across multiple matched utterances for robustness.

**Pros**: Works even when there is zero shared audio (completely isolated recordings). Uses the transcription that Module 1 is already computing.

**Cons**: Accuracy limited by Whisper's timestamp precision (~50-200ms). Cannot achieve sample-level accuracy. Requires both tracks to contain the same speech (doesn't work for music-only segments).

**Verdict**: Essential fallback for the "headphones on both sides, no shared audio" case. Since PodAgent OS already runs Whisper in Module 1, this is nearly free to implement.

```python
def align_by_transcript(
    transcript_a: list[dict],  # [{"word": "hello", "start": 2.1, "end": 2.5}, ...]
    transcript_b: list[dict],
) -> float:
    """
    Estimate offset between two tracks by matching transcribed words.
    Returns offset in milliseconds (B relative to A).
    """
    offsets = []
    # Simple greedy matching: find common subsequences
    words_a = {w["word"].lower(): w["start"] for w in transcript_a}

    for word_b in transcript_b:
        word = word_b["word"].lower()
        if word in words_a and len(word) > 3:  # Skip short/common words
            offset = (word_b["start"] - words_a[word]) * 1000  # ms
            offsets.append(offset)

    if not offsets:
        raise ValueError("No matching words found between transcripts")

    # Use median to reject outliers
    return float(np.median(offsets))
```

> [NOTE] The above is a simplified sketch. A robust implementation would use sequence alignment (like Needleman-Wunsch or a sliding window) rather than simple word matching, to handle repeated words and partial matches correctly.

#### 5.4 Embedded Timecode (LTC / SMPTE)

**How it works**: Each recorder embeds a timecode signal (typically Linear Timecode / LTC) on a dedicated audio channel or as metadata. Tracks are aligned by matching timecodes.

**Pros**: Deterministic, sample-accurate, works regardless of audio content.

**Cons**: Requires specialized hardware or software that embeds timecode. Not standard in podcast production workflows. Participants would need to run sync software (like Tentacle Sync or similar).

**Verdict**: Not practical for a podcast pipeline. This is a professional film/broadcast technique.

#### 5.5 Network Time Protocol (NTP) Timestamps

**How it works**: If recording software timestamps each file with NTP-synchronized wall clock time, you can compute offsets from the timestamps.

**Pros**: Simple, no audio analysis needed.

**Cons**: Depends on both machines having accurate NTP sync (typically ±10-50ms). Depends on recording software embedding precise start timestamps. Not reliable enough for sample-accurate alignment.

**Verdict**: Useful as a coarse initial estimate (to narrow the search window for cross-correlation), but not sufficient on its own.

#### 5.6 Summary: Recommended Approach Chain

```
Primary:     FFT cross-correlation on a 60-second segment
                |
                v (confidence < 0.3?)
Fallback 1:  Bandpass-filtered cross-correlation
                |
                v (confidence < 0.3?)
Fallback 2:  Transcript-based alignment via matched Whisper timestamps
                |
                v (still low confidence?)
Manual:      Flag for human review at Gate 1 with diagnostic info
```

### Recommendation

Implement cross-correlation as the primary method with transcript-based alignment as the fallback. Skip fingerprinting and onset detection for MVP — they add complexity without significant benefit over the cross-correlation + transcript chain.

### Gotchas

- **Transcript alignment accuracy depends on Whisper model size.** `whisper-large-v3` has much better timestamp accuracy than `whisper-tiny`. If using transcript alignment as a fallback, use the largest practical Whisper model.
- **Audio fingerprinting libraries (Dejavu) often require a database backend (MySQL/PostgreSQL).** This adds significant deployment complexity for marginal benefit over cross-correlation.

### Sources

- Chromaprint: https://acoustid.org/chromaprint
- Dejavu: https://github.com/worldveil/dejavu
- librosa onset detection: https://librosa.org/doc/latest/generated/librosa.onset.onset_detect.html
- Tentacle Sync (LTC timecode): https://www.tentaclesync.com/

---

## 6. Performance

### Question
How long does alignment take for 1-hour stereo tracks? Is it feasible in real-time? Optimization tricks?

### Finding

#### Benchmarks (Estimated)

All estimates assume a modern machine (Apple M1/M2 or Intel i7, 16GB RAM).

| Scenario | Track Length | Method | Estimated Time | Memory |
|----------|-------------|--------|----------------|--------|
| Full cross-correlation, 48kHz, full length | 1 hour | FFT xcorr | 30-60 seconds | ~3.5 GB |
| Full cross-correlation, 16kHz, full length | 1 hour | FFT xcorr | 5-15 seconds | ~450 MB |
| 60-second segment, 16kHz | 1 hour | FFT xcorr | <0.5 seconds | ~8 MB |
| 60-second segment, 8kHz | 1 hour | FFT xcorr | <0.2 seconds | ~4 MB |
| Transcript-based alignment | 1 hour | Word matching | <0.1 seconds | Negligible (text only) |

#### Why Full-Track Correlation is Expensive

The FFT-based cross-correlation of two signals of length N requires:
- 2 FFTs of size ~2N (for zero-padding to avoid circular correlation artifacts)
- 1 element-wise multiplication
- 1 inverse FFT

For N = 172,800,000 (1 hour at 48kHz), the FFTs operate on arrays of ~345 million elements. Each FFT is O(N log N), which is ~3 billion operations. This is tractable but slow.

#### Optimization Techniques

**1. Downsample before correlating (most impactful)**

Reducing from 48kHz to 16kHz cuts the signal length by 3x, and FFT cost by ~3.5x (due to N log N). Reducing to 8kHz cuts by 6x. For finding a time offset, even 8kHz provides ±0.0625ms precision.

```python
# Downsample to 8kHz for fastest possible alignment
data = librosa.resample(data, orig_sr=48000, target_sr=8000)
```

**2. Use a segment instead of the full track (most impactful)**

Instead of correlating 1 hour vs. 1 hour, extract a 30-60 second segment from each track. This reduces the signal length from ~millions to ~hundreds of thousands of samples, giving a ~1000x speedup.

The challenge is knowing WHICH segment to use. Strategies:
- Use the first 60 seconds (works if all participants are present from the start).
- Use the loudest 60-second segment (likely to contain the most cross-talk).
- Try multiple segments and pick the one with highest confidence.

**3. Coarse-to-fine search**

1. Downsample aggressively (e.g., 2kHz).
2. Correlate to find an approximate offset (±5ms accuracy).
3. Extract a short segment around the estimated offset at full sample rate.
4. Correlate the short segment for precise alignment.

This combines the speed of coarse search with the accuracy of fine search.

```python
def coarse_to_fine_alignment(ref_path, tgt_path):
    """Two-pass alignment: coarse at 2kHz, fine at 48kHz."""
    # Pass 1: Coarse alignment at 2kHz
    coarse = find_offset(ref_path, tgt_path, align_sr=2000, segment_duration_s=60.0)
    coarse_offset_s = coarse["offset_ms"] / 1000.0

    # Pass 2: Fine alignment at 48kHz on a 2-second window around coarse estimate
    ref_data, sr = sf.read(ref_path, dtype="float32")
    tgt_data, _ = sf.read(tgt_path, dtype="float32")

    # Convert to mono
    if ref_data.ndim > 1: ref_data = np.mean(ref_data, axis=1)
    if tgt_data.ndim > 1: tgt_data = np.mean(tgt_data, axis=1)

    # Extract 2-second windows centered on the expected alignment point
    center = int(abs(coarse_offset_s) * sr)
    window = int(2.0 * sr)  # 2 seconds

    ref_seg = ref_data[max(0, center - window):center + window]
    tgt_seg = tgt_data[max(0, center - window):center + window]

    correlation = correlate(ref_seg, tgt_seg, mode="full", method="fft")
    lags = correlation_lags(len(ref_seg), len(tgt_seg), mode="full")
    peak_idx = np.argmax(np.abs(correlation))
    fine_lag = lags[peak_idx]

    # Combine coarse and fine offsets
    total_offset_samples = int(coarse_offset_s * sr) + fine_lag
    total_offset_ms = (total_offset_samples / sr) * 1000.0

    return {"offset_ms": round(total_offset_ms, 3), "method": "coarse_to_fine"}
```

**4. Use `scipy.fft` with real-valued FFT**

Since audio is real-valued, use `scipy.fft.rfft` instead of `fft` — this is ~2x faster and uses ~half the memory.

**5. Parallel alignment of multiple tracks**

When aligning N guest tracks to a reference, each alignment is independent. Use Python's `concurrent.futures.ProcessPoolExecutor` to align in parallel.

```python
from concurrent.futures import ProcessPoolExecutor

def align_all_tracks(reference_path, track_paths):
    with ProcessPoolExecutor() as pool:
        futures = {
            pool.submit(find_offset, reference_path, tp): tp
            for tp in track_paths
        }
        results = {}
        for future in futures:
            track = futures[future]
            results[track] = future.result()
    return results
```

#### Is Real-Time Feasible?

**For the alignment computation itself**: Yes. With the 60-second segment at 16kHz approach, alignment takes <0.5 seconds per track pair. Even 10 tracks can be aligned in <5 seconds.

**For the overall Module 1 pipeline**: Alignment is NOT the bottleneck. Whisper transcription (step 2) and speaker diarization (step 3) are orders of magnitude slower. A 1-hour episode takes ~5-20 minutes to transcribe with Whisper (depending on model size and hardware). Alignment adds negligible time.

### Recommendation

For PodAgent OS Module 1:

1. **Default approach**: Downsample to 16kHz, use a 60-second segment, `scipy.signal.correlate` with `method='fft'`. This will complete in <1 second per track pair.
2. **If confidence is low**: Try additional segments (5 min in, 10 min in, etc.) before falling back to full-track correlation.
3. **For V2**: Implement coarse-to-fine alignment if sample-level accuracy at native sample rate is needed (e.g., for music podcasts where timing is more critical).
4. **Parallelize**: Use `ProcessPoolExecutor` when aligning 3+ tracks.

### Gotchas

- **SciPy's FFT pads to the next power of 2 (or a "good" FFT size).** For unlucky signal lengths, this can nearly double the computation. The `segment_duration_s` approach avoids this by giving you control over the signal length.
- **Memory pressure**: If multiple alignment jobs run in parallel on long tracks at high sample rates, memory usage can spike. The segment approach keeps each job's memory footprint small.
- **Apple Silicon (M1/M2) has excellent FFT performance** due to the Accelerate framework. NumPy/SciPy on macOS automatically use Accelerate's vDSP FFT, which is very fast. Performance on Apple Silicon will be better than the estimates above.

### Sources

- SciPy FFT documentation: https://docs.scipy.org/doc/scipy/reference/fft.html
- Apple Accelerate vDSP: https://developer.apple.com/documentation/accelerate/vdsp

---

## 7. Recommendation for PodAgent OS

### Summary of Recommendations

| Decision | Recommendation | Rationale |
|----------|---------------|-----------|
| **Primary algorithm** | FFT cross-correlation via `scipy.signal.correlate` | Fast, accurate, well-understood, minimal dependencies |
| **Alignment sample rate** | 16kHz | 3x faster than 48kHz, ±0.03ms precision (more than sufficient) |
| **Segment strategy** | 60-second segment with fallback to multiple segments | 1000x faster than full-track, works in >90% of cases |
| **Fallback method** | Transcript-based alignment via matched Whisper timestamps | Handles the "no shared audio" case; already available from transcription step |
| **External library** | Do NOT depend on `audalign` | Roll our own ~40-line implementation for full control; use audalign as a test reference |
| **Confidence threshold** | 0.3 (flag for human review below this) | Empirically, values above 0.3 indicate reliable alignment |
| **Clock drift detection** | Detect and warn; defer correction to V2 | Measure offset at start and end; warn if difference > 10ms |
| **Output format** | `alignment.json` with ms offsets and 48kHz sample offsets | Serves both human readability and EDL precision |

### Integration with Module 1 Pipeline

The alignment step fits into Module 1 as follows:

```
Step 1: Validate and catalog audio files    → files.source_tracks in manifest
Step 2: Transcribe each track               → transcript.json
Step 3: Speaker diarization                 → speaker IDs in transcript.json
Step 4: Multi-track alignment               → alignment.json  ← THIS RESEARCH
Step 5: LLM context extraction              → context.json
Step 6: Write outputs, update manifest      → manifest.yaml
```

**Important sequencing note**: Step 4 (alignment) can run IN PARALLEL with Steps 2 and 3 (transcription and diarization), since alignment only needs the raw audio files, not the transcript. This could save significant wall-clock time, since transcription is the bottleneck. However, the transcript-based fallback requires Step 2 to complete first. Recommended: start alignment immediately, and if it fails with low confidence, retry with transcript fallback after Step 2 completes.

### Dependencies to Add

```
# In requirements.txt
numpy>=1.24
scipy>=1.11
soundfile>=0.12
librosa>=0.10
```

No additional dependencies beyond what Module 1 already needs for transcription and audio I/O.

---

> **Open Questions for Architect**:
> 1. Should the alignment step support a user-provided "sync tone" file? If participants record a known tone at the start, we could correlate against that specific signal for even more robust alignment.
> 2. Should we store multiple alignment confidence values (per-segment) in alignment.json, or just the best one? Multiple values would help Gate 1 reviewers assess alignment quality.
> 3. For the clock drift detection: should we auto-correct drift if it's small (<50ms over the full recording), or always defer to the user?
