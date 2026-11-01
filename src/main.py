"""Консольный прототип КТ2: WAV → анализ → параметры визуализации → JSON."""

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import struct
import sys
import wave

from algorithms import calculate_spectrum, extract_features, map_visual_frame
from data import find_record, next_id, require, validate_data


def read_wav(path):
    with wave.open(str(path), "rb") as audio:
        require(audio.getnchannels() == 1 and audio.getsampwidth() == 2,
                "Нужен WAV PCM: один канал, 16 бит")
        require(audio.getcomptype() == "NONE", "Сжатый WAV не поддерживается")
        count = audio.getnframes()
        sample_rate = audio.getframerate()
        raw = audio.readframes(count)
    require(count > 0 and len(raw) == count * 2, "Аудиоданные пусты или обрезаны")
    return [v[0] / 32768 for v in struct.iter_unpack("<h", raw)], sample_rate


def process_track(data, track_id, profile_id, preset_id, base_dir):
    """Добавляет один анализ и один сеанс в копию набора, загруженного из JSON."""
    validate_data(data)
    track = find_record(data["tracks"], "track_id", track_id)
    profile = find_record(data["profiles"], "profile_id", profile_id)
    preset = find_record(data["presets"], "preset_id", preset_id)
    samples, sample_rate = read_wav(Path(base_dir) / track["source_uri"])
    require(sample_rate == track["sample_rate"] and len(samples) == track["sample_count"],
            "Метаданные трека не совпадают с WAV")
    size, hop = profile["frame_size"], profile["hop_size"]
    require(len(samples) >= size, "Трек короче одного кадра анализа")

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    run_id = next_id(data["runs"], "run_id")
    session_id = next_id(data["sessions"], "session_id")
    frame_id = next_id(data["frames"], "frame_id")
    data["runs"].append({"run_id": run_id, "track_id": track_id,
                         "profile_id": profile_id, "analyzer_version": "1.0",
                         "started_at": now})
    data["sessions"].append({"session_id": session_id, "run_id": run_id,
                             "preset_id": preset_id, "started_at": now})
    previous = {"brightness": 0.0}
    for index, start in enumerate(range(0, len(samples) - size + 1, hop)):
        frame = samples[start:start + size]
        spectrum = calculate_spectrum(frame)
        features = extract_features(frame, spectrum, sample_rate)
        data["frames"].append({"frame_id": frame_id, "run_id": run_id,
                               "frame_index": index, **features})
        visual = map_visual_frame(features, preset, previous, sample_rate)
        data["visual_frames"].append({"session_id": session_id,
                                      "frame_id": frame_id, **visual})
        previous = visual
        frame_id += 1
    validate_data(data)
    return data, run_id, session_id


def create_demo(directory):
    """Синус 1000 Гц, амплитуда 0,5, одна секунда при 8000 Гц."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    samples = [round(0.5 * 32767 * math.sin(2 * math.pi * 1000 * i / 8000))
               for i in range(8000)]
    with wave.open(str(directory / "demo.wav"), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(8000)
        audio.writeframes(struct.pack("<" + "h" * len(samples), *samples))
    data = {
        "tracks": [{"track_id": 1, "title": "Синус 1000 Гц", "source_uri": "demo.wav",
                    "sample_rate": 8000, "sample_count": 8000}],
        "profiles": [{"profile_id": 1, "name": "Кадр 256", "frame_size": 256,
                      "hop_size": 128}],
        "presets": [{"preset_id": 1, "name": "Спокойный", "smoothing_alpha": 0.25,
                     "brightness_gain": 2.0, "hue_offset": 0.0}],
        "runs": [], "frames": [], "sessions": [], "visual_frames": [],
    }
    path = directory / "input.json"
    save_json(path, data)
    return path


def save_json(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2,
                                    allow_nan=False) + "\n", encoding="utf-8")


def print_summary(data, run_id, session_id, out):
    frames = [r for r in data["frames"] if r["run_id"] == run_id]
    visuals = [r for r in data["visual_frames"] if r["session_id"] == session_id]
    first, last = frames[0], visuals[-1]
    print(f"Анализ: {run_id}; сеанс: {session_id}; кадров: {len(frames)}")
    print(f"Первый кадр: RMS={first['rms']:.4f}; центроид={first['centroid_hz']:.2f} Гц")
    print(f"Последний кадр: яркость={last['brightness']:.4f}; "
          f"оттенок={last['hue']:.4f}; масштаб={1 + last['brightness']:.4f}")
    print(f"Результат: {out}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    demo = sub.add_parser("demo", help="Создать пример и обработать его")
    demo.add_argument("--out-dir", default="output/demo")
    analyze = sub.add_parser("analyze", help="Обработать трек из JSON")
    analyze.add_argument("--data", required=True)
    analyze.add_argument("--track", type=int, default=1)
    analyze.add_argument("--profile", type=int, default=1)
    analyze.add_argument("--preset", type=int, default=1)
    analyze.add_argument("--out", default="output/result.json")
    args = parser.parse_args(argv)
    try:
        if args.command == "demo":
            input_path = create_demo(args.out_dir)
            output_path = Path(args.out_dir) / "result.json"
            ids = (1, 1, 1)
        else:
            input_path, output_path = Path(args.data), Path(args.out)
            ids = (args.track, args.profile, args.preset)
        data = json.loads(input_path.read_text(encoding="utf-8"))
        data, run_id, session_id = process_track(data, *ids, input_path.parent)
        save_json(output_path, data)
        print_summary(data, run_id, session_id, output_path)
    except (ValueError, OSError, wave.Error, EOFError, struct.error) as error:
        print(f"Ошибка: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
