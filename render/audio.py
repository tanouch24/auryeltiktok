"""
render/audio.py — Numpy-based WAV generator for WhatsApp notification ping.
No scipy required. Writes raw PCM int16 stereo WAV.
"""

import struct
import math
from pathlib import Path


def _make_ping(sample_rate: int = 44100, duration: float = 0.18) -> list[float]:
    """Two-tone soft ping: 880 Hz + 1108 Hz, quick attack, exponential decay."""
    n = int(sample_rate * duration)
    samples = []
    for i in range(n):
        t       = i / sample_rate
        attack  = min(1.0, t / 0.008)            # 8ms attack
        decay   = math.exp(-t * 22.0)            # fast exponential decay
        env     = attack * decay
        tone    = 0.55 * math.sin(2 * math.pi * 880  * t)
        tone   += 0.45 * math.sin(2 * math.pi * 1108 * t)
        samples.append(tone * env * 0.72)        # 72% amplitude — soft
    return samples


def _write_wav(path: str, samples: list[float], sample_rate: int = 44100) -> None:
    """Write stereo int16 WAV without external dependencies."""
    n_samples = len(samples)
    n_channels = 2
    bits = 16
    byte_rate = sample_rate * n_channels * bits // 8
    block_align = n_channels * bits // 8
    data_size = n_samples * n_channels * bits // 8

    with open(path, "wb") as f:
        # RIFF header
        f.write(b"RIFF")
        f.write(struct.pack("<I", 36 + data_size))
        f.write(b"WAVE")
        # fmt chunk
        f.write(b"fmt ")
        f.write(struct.pack("<I", 16))              # chunk size
        f.write(struct.pack("<H", 1))               # PCM
        f.write(struct.pack("<H", n_channels))
        f.write(struct.pack("<I", sample_rate))
        f.write(struct.pack("<I", byte_rate))
        f.write(struct.pack("<H", block_align))
        f.write(struct.pack("<H", bits))
        # data chunk
        f.write(b"data")
        f.write(struct.pack("<I", data_size))
        for s in samples:
            v = int(max(-1.0, min(1.0, s)) * 32767)
            packed = struct.pack("<h", v)
            f.write(packed)   # left
            f.write(packed)   # right (identical — mono ping)


def generate_notification_wav(
    total_duration: float,
    ping_at: float,
    output_path: str,
    sample_rate: int = 44100,
) -> str:
    """
    Generate a WAV file: silence until ping_at, then the notification ping.

    Args:
        total_duration: total length in seconds (should match video length)
        ping_at:        when the ping fires (seconds from start)
        output_path:    destination .wav path
        sample_rate:    default 44100 Hz

    Returns:
        output_path (for chaining)
    """
    ping_samples   = _make_ping(sample_rate)
    silence_count  = max(0, int(ping_at * sample_rate))
    total_samples  = int(total_duration * sample_rate)

    # Build full timeline
    audio: list[float] = [0.0] * silence_count
    audio.extend(ping_samples)
    # Pad or trim to exact total length
    if len(audio) < total_samples:
        audio.extend([0.0] * (total_samples - len(audio)))
    else:
        audio = audio[:total_samples]

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    _write_wav(output_path, audio, sample_rate)
    return output_path
