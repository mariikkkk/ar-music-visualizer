"""Небольшие проверки: python3 checks.py. Внешних библиотек не требуется."""

import cmath
from copy import deepcopy
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile

from algorithms import calculate_spectrum, extract_features, map_visual_frame
from data import validate_data
from main import create_demo, process_track


def expect_error(function, *args):
    try:
        function(*args)
    except ValueError:
        return
    raise AssertionError("Ожидалась ошибка ValueError")


def check_fft_against_dft():
    # Прямое ДПФ — независимый эталон для коротких непериодических входов.
    for size in (1, 2, 4, 8, 16):
        frame = [math.sin(i * 0.7) + 0.2 * i for i in range(size)]
        actual = calculate_spectrum(frame)
        for k, value in enumerate(actual):
            expected = abs(sum(x * cmath.exp(-2j * math.pi * k * n / size)
                               for n, x in enumerate(frame)))
            assert math.isclose(value, expected, rel_tol=1e-10, abs_tol=1e-10)


def check_fft_invalid_size():
    expect_error(calculate_spectrum, [])
    expect_error(calculate_spectrum, [1, 2, 3])


def check_silence_and_empty():
    assert extract_features([], [], 8000) == {"rms": 0.0, "centroid_hz": 0.0}
    frame = [0.0] * 256
    assert extract_features(frame, calculate_spectrum(frame), 8000) == {
        "rms": 0.0, "centroid_hz": 0.0}


def check_known_tone():
    frame = [0.5 * math.sin(2 * math.pi * 1000 * i / 8000) for i in range(256)]
    result = extract_features(frame, calculate_spectrum(frame), 8000)
    assert math.isclose(result["rms"], 0.5 / math.sqrt(2), abs_tol=1e-10)
    assert math.isclose(result["centroid_hz"], 1000, abs_tol=1e-8)


def check_feature_arguments():
    expect_error(extract_features, [1.0, 0.0], [1.0], 8000)
    expect_error(extract_features, [1.0, 0.0], [1.0, 1.0], 0)


def check_mapping():
    preset = {"smoothing_alpha": 0.25, "brightness_gain": 4.0, "hue_offset": 0.1}
    value = map_visual_frame({"rms": 1.0, "centroid_hz": 1000}, preset,
                             {"brightness": 0.0}, 8000)
    assert value == {"brightness": 0.25, "hue": 0.35}


def check_full_pipeline_and_keys():
    with tempfile.TemporaryDirectory() as directory:
        source = create_demo(directory)
        original = json.loads(source.read_text(encoding="utf-8"))
        data, run_id, session_id = process_track(deepcopy(original), 1, 1, 1, directory)
        assert len(data["frames"]) == len(data["visual_frames"]) == 61
        assert len(data["runs"]) == len(data["sessions"]) == 1
        assert data["sessions"][0]["run_id"] == run_id
        assert data["visual_frames"][0]["session_id"] == session_id
        assert all(math.isclose(f["centroid_hz"], 1000, abs_tol=1) for f in data["frames"])
        # Повтор той же пары трек/профиль — новый анализ без конфликтов PK.
        data, second_run, second_session = process_track(data, 1, 1, 1, directory)
        assert second_run != run_id and second_session != session_id
        assert len(data["frames"]) == 122
        validate_data(data)


def check_integrity_errors():
    with tempfile.TemporaryDirectory() as directory:
        source = create_demo(directory)
        data = json.loads(source.read_text(encoding="utf-8"))
        data, _, _ = process_track(data, 1, 1, 1, directory)
        duplicate = deepcopy(data)
        duplicate["tracks"].append(dict(duplicate["tracks"][0]))
        expect_error(validate_data, duplicate)
        dangling = deepcopy(data)
        dangling["sessions"][0]["preset_id"] = 999
        expect_error(validate_data, dangling)
        nested = deepcopy(data)
        nested["tracks"][0]["title"] = ["список вместо атомарного значения"]
        expect_error(validate_data, nested)
        bad = deepcopy(data)
        bad["presets"][0]["smoothing_alpha"] = float("nan")
        expect_error(validate_data, bad)
        # Существующий кадр другого анализа также нельзя включить в сеанс.
        data, _, _ = process_track(data, 1, 1, 1, directory)
        data["visual_frames"][0]["frame_id"] = data["frames"][-1]["frame_id"]
        expect_error(validate_data, data)


def check_short_audio_and_metadata():
    with tempfile.TemporaryDirectory() as directory:
        source = create_demo(directory)
        data = json.loads(source.read_text(encoding="utf-8"))
        mismatch = deepcopy(data)
        mismatch["tracks"][0]["sample_rate"] = 44100
        expect_error(process_track, mismatch, 1, 1, 1, directory)
        data["profiles"][0]["frame_size"] = 16384
        expect_error(process_track, data, 1, 1, 1, directory)


def check_input_file_is_not_overwritten():
    with tempfile.TemporaryDirectory() as directory:
        source = create_demo(directory)
        original = source.read_bytes()
        folder = Path(directory)
        (folder / "nested").mkdir()
        outputs = [(str(source), 1), ("input.json", 1),
                   ("nested/../input.json", 1), ("result.json", 0),
                   ("fresh/result.json", 0)]
        # Ссылки проверяем там, где их поддерживает файловая система.
        symbolic = folder / "input-link.json"
        try:
            symbolic.symlink_to(source)
        except (OSError, NotImplementedError):
            pass
        else:
            outputs.append((str(symbolic), 1))
        hard_link = folder / "input-hardlink.json"
        try:
            hard_link.hardlink_to(source)
        except (OSError, NotImplementedError):
            pass
        else:
            outputs.append((str(hard_link), 1))
        # Отдельный существующий файл результата можно перезаписывать.
        (folder / "result.json").write_text("старый результат", encoding="utf-8")
        program = Path(__file__).with_name("main.py").resolve()
        for output, expected_code in outputs:
            result = subprocess.run(
                [sys.executable, str(program), "analyze", "--data", "input.json",
                 "--out", output], cwd=directory, capture_output=True, text=True)
            assert result.returncode == expected_code, (output, result.stdout, result.stderr)
            assert source.read_bytes() == original, "Входной JSON изменился"
            if expected_code == 1:
                assert "Входной JSON" in result.stderr
                assert not result.stdout
            else:
                assert not result.stderr
                saved = json.loads((folder / output).read_text(encoding="utf-8"))
                validate_data(saved)
                assert len(saved["frames"]) == len(saved["visual_frames"]) == 61


def main():
    checks = [check_fft_against_dft, check_fft_invalid_size, check_silence_and_empty,
              check_known_tone, check_feature_arguments, check_mapping,
              check_full_pipeline_and_keys, check_integrity_errors,
              check_short_audio_and_metadata, check_input_file_is_not_overwritten]
    for check in checks:
        check()
        print(f"OK {check.__name__}")
    print(f"Пройдено проверок: {len(checks)}")


if __name__ == "__main__":
    main()
