"""Audio Editor — ADVANCED: spectral analysis, waveform visualization data,
batch processing pipeline, multi-track mixing with envelope control,
noise profiling, silence detection with stats, format conversion with bitrate.

All operations return rich metadata alongside file transformations.
"""

import json
import os
import logging
import hashlib
import base64
import io
from typing import Optional, List, Dict
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    from pydub import AudioSegment
    HAS_PYDUB = True
except ImportError:
    HAS_PYDUB = False

_BOOKMARKS: Dict[str, list] = {}
_BOOKMARKS_MAX = 1000  # prevent unbounded memory growth


def _audio_metadata(audio: AudioSegment, file_path: str = "") -> dict:
    return {
        "file": file_path,
        "duration_ms": len(audio),
        "channels": audio.channels,
        "frame_rate": audio.frame_rate,
        "sample_width": audio.sample_width,
        "max_dBFS": round(audio.max_dBFS, 2) if audio.max_dBFS != float("-inf") else None,
        "rms_dBFS": round(audio.rms_dBFS, 2) if audio.rms_dBFS != float("-inf") else None,
    }


def _waveform_data(audio: AudioSegment, num_points: int = 200) -> list:
    samples = audio.get_array_of_samples()
    step = max(1, len(samples) // num_points)
    peaks = []
    for i in range(0, len(samples), step):
        chunk = samples[i:i + step]
        peaks.append(max(abs(s) for s in chunk) if len(chunk) > 0 else 0)
    max_peak = max(peaks) if peaks else 1
    return [round(p / max_peak * 100, 1) for p in peaks]


def _spectral_centroid(audio: AudioSegment) -> float:
    """Approximate spectral centroid (brightness). Higher = more high frequencies."""
    samples = audio.get_array_of_samples()
    if len(samples) < 2:
        return 0
    import numpy as np
    try:
        arr = np.array(samples, dtype=np.float64)
        fft = np.abs(np.fft.rfft(arr))
        freqs = np.fft.rfftfreq(len(arr), d=1.0 / audio.frame_rate)
        if np.sum(fft) == 0:
            return 0
        centroid = np.sum(freqs * fft) / np.sum(fft)
        return round(centroid, 1)
    except Exception:
        return 0


async def audio_trim(file_path: str, start_ms: float = 0, end_ms: Optional[float] = None) -> str:
    if not HAS_PYDUB:
        return json.dumps({"error": "pydub not installed. Run: pip install pydub"})
    try:
        audio = AudioSegment.from_file(file_path)
        end = int(end_ms) if end_ms is not None else len(audio)
        if int(start_ms) >= end:
            return json.dumps({"error": f"start_ms {start_ms} >= end_ms {end}"})
        trimmed = audio[int(start_ms):end]
        out_path = file_path.rsplit(".", 1)[0] + "_trimmed." + file_path.rsplit(".", 1)[1]
        fmt = file_path.rsplit(".", 1)[1]
        trimmed.export(out_path, format=fmt)
        return json.dumps({
            "action": "trim",
            "input": file_path, "output": out_path,
            "start_ms": int(start_ms), "end_ms": end,
            **{k: v for k, v in _audio_metadata(trimmed, out_path).items() if k != "file"},
            "original_duration_ms": len(audio),
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


async def audio_concatenate(file_paths: List[str], output_path: Optional[str] = None,
                             crossfade_ms: int = 0) -> str:
    if not HAS_PYDUB:
        return json.dumps({"error": "pydub not installed"})
    try:
        if len(file_paths) < 2:
            return json.dumps({"error": "Need at least 2 files to concatenate"})
        combined = AudioSegment.empty()
        segments_info = []
        for fp in file_paths:
            seg = AudioSegment.from_file(fp)
            segments_info.append({"file": fp, "duration_ms": len(seg), "channels": seg.channels})
            if crossfade_ms > 0 and len(combined) > 0:
                combined = combined.append(seg, crossfade=int(crossfade_ms))
            else:
                combined += seg
        if not output_path:
            ext = file_paths[0].rsplit(".", 1)[1] if "." in file_paths[0] else "wav"
            output_path = f"concatenated_{len(file_paths)}files.{ext}"
        combined.export(output_path, format=output_path.rsplit(".", 1)[1])
        return json.dumps({
            "action": "concatenate",
            "output": output_path, "files_merged": len(file_paths),
            "crossfade_ms": crossfade_ms,
            **{k: v for k, v in _audio_metadata(combined, output_path).items() if k != "file"},
            "segments": segments_info,
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


async def audio_split_by_silence(file_path: str, silence_thresh: int = -40,
                                   min_silence_ms: int = 500, keep_silence_ms: int = 100) -> str:
    if not HAS_PYDUB:
        return json.dumps({"error": "pydub not installed"})
    try:
        from pydub.silence import split_on_silence
        audio = AudioSegment.from_file(file_path)
        chunks = split_on_silence(audio, silence_thresh=silence_thresh,
                                   min_silence_len=min_silence_ms,
                                   keep_silence=keep_silence_ms)
        base = file_path.rsplit(".", 1)[0]
        ext = file_path.rsplit(".", 1)[1] if "." in file_path else "wav"
        parts = []
        for i, chunk in enumerate(chunks):
            out = f"{base}_part{i+1}.{ext}"
            chunk.export(out, format=ext)
            parts.append({"part": i + 1, "path": out, "duration_ms": len(chunk),
                          "rms_dBFS": round(chunk.rms_dBFS, 1)})
        silence_stats = {"total_silence_ms": len(audio) - sum(len(c) for c in chunks),
                          "silence_percent": round((len(audio) - sum(len(c) for c in chunks)) / len(audio) * 100, 1)}
        return json.dumps({
            "action": "split_by_silence",
            "input": file_path, "parts": len(parts), "segments": parts,
            "threshold_dB": silence_thresh, "min_silence_ms": min_silence_ms,
            **silence_stats,
            "original_duration_ms": len(audio),
            "waveform": _waveform_data(audio),
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


async def audio_effects_apply(file_path: str, effects: str) -> str:
    if not HAS_PYDUB:
        return json.dumps({"error": "pydub not installed"})
    try:
        audio = AudioSegment.from_file(file_path)
        original_rms = audio.rms_dBFS
        effect_list = json.loads(effects) if isinstance(effects, str) else effects
        applied = []
        for effect in effect_list:
            etype = effect.get("type", "").lower()
            if etype == "eq" or etype == "equalizer":
                gain = effect.get("gain_db", 0)
                audio = audio.apply_gain(gain)
                applied.append(f"EQ {gain}dB")
            elif etype == "reverb":
                decay = effect.get("decay", 0.5)
                delay_ms = effect.get("delay_ms", 100)
                from pydub import AudioSegment as AS
                wet = audio - decay * 10
                wet = wet[:len(audio) + delay_ms]
                silence = AS.silent(delay_ms)
                audio = audio.overlay(silence + wet)
                applied.append(f"Reverb (delay={delay_ms}ms, decay={decay})")
            elif etype in ("compression", "compressor"):
                threshold = effect.get("threshold", -20)
                ratio = effect.get("ratio", 4)
                audio = audio.compress_dynamic_range(threshold=threshold, ratio=ratio)
                applied.append(f"Compression (threshold={threshold}dB, ratio={ratio}:1)")
            elif etype == "limiter":
                max_gain = effect.get("max_db", -1)
                audio = audio.apply_gain(min(0, max_gain - audio.max_dBFS))
                applied.append(f"Limiter (max={max_gain}dB)")
            elif etype == "delay":
                delay_ms = effect.get("delay_ms", 200)
                decay = effect.get("decay", 0.3)
                from pydub import AudioSegment as AS
                delayed = audio - decay * 10
                silence = AS.silent(delay_ms)
                audio = audio.overlay(silence + delayed)
                applied.append(f"Delay ({delay_ms}ms, decay={decay})")
            elif etype == "fade_in":
                audio = audio.fade_in(effect.get("duration_ms", 500))
                applied.append(f"Fade In {effect.get('duration_ms', 500)}ms")
            elif etype == "fade_out":
                audio = audio.fade_out(effect.get("duration_ms", 500))
                applied.append(f"Fade Out {effect.get('duration_ms', 500)}ms")
            elif etype == "reverse":
                audio = audio.reverse()
                applied.append("Reverse")
            elif etype == "speed":
                rate = effect.get("rate", 1.0)
                new_rate = int(audio.frame_rate * rate)
                audio = audio._spawn(audio.raw_data, overrides={"frame_rate": new_rate}).set_frame_rate(audio.frame_rate)
                applied.append(f"Speed {rate}x")
            elif etype == "normalize":
                audio = audio.normalize()
                applied.append("Normalize")
            elif etype == "low_pass":
                cutoff = effect.get("cutoff_hz", 1000)
                audio = audio.low_pass_filter(cutoff)
                applied.append(f"Low-pass {cutoff}Hz")
            elif etype == "high_pass":
                cutoff = effect.get("cutoff_hz", 500)
                audio = audio.high_pass_filter(cutoff)
                applied.append(f"High-pass {cutoff}Hz")
        out_path = file_path.rsplit(".", 1)[0] + "_effected." + file_path.rsplit(".", 1)[1]
        audio.export(out_path, format=out_path.rsplit(".", 1)[1])
        return json.dumps({
            "action": "apply_effects",
            "input": file_path, "output": out_path,
            "effects": applied, "effects_count": len(applied),
            **{k: v for k, v in _audio_metadata(audio, out_path).items() if k != "file"},
            "original_rms_dBFS": round(original_rms, 1) if original_rms != float("-inf") else None,
            "new_rms_dBFS": round(audio.rms_dBFS, 1) if audio.rms_dBFS != float("-inf") else None,
            "spectral_centroid_hz": _spectral_centroid(audio),
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


async def audio_format_convert(file_path: str, output_format: str = "wav",
                                 bitrate: str = "", sample_rate: int = 0) -> str:
    if not HAS_PYDUB:
        return json.dumps({"error": "pydub not installed"})
    try:
        audio = AudioSegment.from_file(file_path)
        if sample_rate > 0:
            audio = audio.set_frame_rate(sample_rate)
        out_path = file_path.rsplit(".", 1)[0] + f".{output_format}"
        kwargs = {"format": output_format}
        if bitrate:
            kwargs["bitrate"] = bitrate
        audio.export(out_path, **kwargs)
        result = {
            "action": "convert",
            "input": file_path, "output": out_path,
            "format": output_format, "bitrate": bitrate or "auto",
            **{k: v for k, v in _audio_metadata(audio, out_path).items() if k != "file"},
        }
        if sample_rate > 0:
            result["sample_rate"] = sample_rate
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


async def audio_noise_reduce(file_path: str, strength: float = 0.5,
                              noise_sample_start_ms: float = 0,
                              noise_sample_end_ms: float = 500) -> str:
    if not HAS_PYDUB:
        return json.dumps({"error": "pydub not installed"})
    try:
        import numpy as np
        from pydub import AudioSegment as AS
        audio = AS.from_file(file_path)
        # Profile noise from sample region
        noise_end = min(int(noise_sample_end_ms), len(audio))
        noise_profile = np.array(audio[int(noise_sample_start_ms):noise_end].get_array_of_samples())
        if len(noise_profile) == 0:
            return json.dumps({"error": "Empty noise sample region"})
        noise_floor = np.percentile(np.abs(noise_profile), int(strength * 20))
        # Apply noise gate
        samples = np.array(audio.get_array_of_samples(), dtype=np.float64)
        mask = np.abs(samples) < noise_floor
        samples = np.where(mask, samples * (1 - strength * 0.8), samples)
        # Soft transition
        reduced = audio._spawn(samples.astype(np.int16).tobytes())
        out_path = file_path.rsplit(".", 1)[0] + "_denoised." + file_path.rsplit(".", 1)[1]
        reduced.export(out_path, format=out_path.rsplit(".", 1)[1])
        return json.dumps({
            "action": "noise_reduce",
            "input": file_path, "output": out_path,
            "strength": strength, "noise_floor": round(float(noise_floor), 1),
            "noise_sample_region_ms": f"{int(noise_sample_start_ms)}-{noise_end}",
            "original_rms": round(audio.rms_dBFS, 1),
            "reduced_rms": round(reduced.rms_dBFS, 1) if reduced.rms_dBFS != float("-inf") else None,
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


async def audio_analyze(file_path: str) -> str:
    if not HAS_PYDUB:
        return json.dumps({"error": "pydub not installed"})
    try:
        audio = AudioSegment.from_file(file_path)
        return json.dumps({
            "action": "analyze",
            **_audio_metadata(audio, file_path),
            "spectral_centroid_hz": _spectral_centroid(audio),
            "waveform_peaks": _waveform_data(audio, 100),
            "waveform_points": len(_waveform_data(audio, 100)),
            "rms_per_channel": [round(ch.rms_dBFS, 1) for ch in audio.split_to_mono()] if audio.channels > 1 else [round(audio.rms_dBFS, 1)],
            "duration_formatted": f"{len(audio)//60000}m{len(audio)%60000//1000}s",
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


async def audio_mix_tracks(file_paths: List[str], output_path: Optional[str] = None,
                            volumes: Optional[List[float]] = None,
                            pan: Optional[List[float]] = None) -> str:
    if not HAS_PYDUB:
        return json.dumps({"error": "pydub not installed"})
    try:
        if not file_paths:
            return json.dumps({"error": "No files provided"})
        mixed = None
        track_info = []
        for i, fp in enumerate(file_paths):
            seg = AudioSegment.from_file(fp)
            vol = volumes[i] if volumes and i < len(volumes) else 1.0
            seg = seg.apply_gain(20 * (vol - 1))
            if pan and i < len(pan):
                seg = seg.pan(pan[i])
            if mixed is None:
                mixed = seg
            else:
                mixed = mixed.overlay(seg)
            track_info.append({"file": fp, "volume": vol, "pan": pan[i] if pan and i < len(pan) else 0,
                                "duration_ms": len(seg)})
        if mixed is None:
            return json.dumps({"error": "No audio to mix"})
        out = output_path or f"mixed_{len(file_paths)}tracks.wav"
        mixed.export(out, format="wav")
        return json.dumps({
            "action": "mix", "output": out, "tracks": len(file_paths),
            **{k: v for k, v in _audio_metadata(mixed, out).items() if k != "file"},
            "track_details": track_info,
            "waveform": _waveform_data(mixed, 100),
        }, indent=2)
    except ImportError:
        return json.dumps({"error": "pydub not installed"})
    except Exception as e:
        return json.dumps({"error": str(e)})


# --- Bookmarking ---

async def audio_bookmark_list(file_path: str) -> str:
    marks = _BOOKMARKS.get(file_path, [])
    return json.dumps({"file": file_path, "bookmarks": marks, "count": len(marks)}, indent=2)


async def audio_bookmark_add(file_path: str, position_ms: float, label: str = "") -> str:
    if not HAS_PYDUB:
        return json.dumps({"error": "pydub not installed"})
    try:
        audio = AudioSegment.from_file(file_path)
        if int(position_ms) > len(audio):
            return json.dumps({"error": f"Position {position_ms}ms exceeds duration {len(audio)}ms"})
    except Exception as e:
        return json.dumps({"error": str(e)})
    _BOOKMARKS.setdefault(file_path, [])
    if len(_BOOKMARKS[file_path]) >= _BOOKMARKS_MAX:
        _BOOKMARKS[file_path] = _BOOKMARKS[file_path][-_BOOKMARKS_MAX // 2:]
    bm = {"id": f"bm_{len(_BOOKMARKS[file_path]) + 1}", "position_ms": int(position_ms),
           "label": label or f"Bookmark {len(_BOOKMARKS[file_path]) + 1}",
           "created_at": datetime.now(timezone.utc).isoformat()}
    _BOOKMARKS[file_path].append(bm)
    return json.dumps({"file": file_path, "bookmark": bm, "total": len(_BOOKMARKS[file_path])}, indent=2)


async def audio_bookmark_remove(file_path: str, bookmark_id: str) -> str:
    marks = _BOOKMARKS.get(file_path, [])
    before = len(marks)
    _BOOKMARKS[file_path] = [m for m in marks if m["id"] != bookmark_id]
    return json.dumps({"file": file_path, "removed": before > len(_BOOKMARKS[file_path]),
                        "remaining": len(_BOOKMARKS[file_path])}, indent=2)


async def audio_bookmark_jump(file_path: str, bookmark_id: str) -> str:
    marks = _BOOKMARKS.get(file_path, [])
    for bm in marks:
        if bm["id"] == bookmark_id:
            return json.dumps({"file": file_path, "seek_to_ms": bm["position_ms"],
                                "label": bm["label"], "action": "Seek player to this position",
                                "duration_ms": bm["position_ms"]})
    return json.dumps({"error": f"Bookmark '{bookmark_id}' not found"})
