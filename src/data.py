"""Проверка записей логической модели. Данные хранятся в списках словарей."""

import math


def require(condition, message):
    if not condition:
        raise ValueError(message)


def number(value):
    return type(value) in (int, float) and math.isfinite(value)


def positive_id(value):
    return type(value) is int and value > 0


def find_record(records, key, value):
    for record in records:
        if record[key] == value:
            return record
    raise ValueError(f"Запись {key}={value} не найдена")


def validate_data(data):
    """PK, FK, уникальность и предметные ограничения семи сущностей."""
    fields = {
        "tracks": {"track_id", "title", "source_uri", "sample_rate", "sample_count"},
        "profiles": {"profile_id", "name", "frame_size", "hop_size"},
        "runs": {"run_id", "track_id", "profile_id", "analyzer_version", "started_at"},
        "frames": {"frame_id", "run_id", "frame_index", "rms", "centroid_hz"},
        "presets": {"preset_id", "name", "smoothing_alpha", "brightness_gain", "hue_offset"},
        "sessions": {"session_id", "run_id", "preset_id", "started_at"},
        "visual_frames": {"session_id", "frame_id", "brightness", "hue"},
    }
    primary_keys = {
        "tracks": ("track_id",), "profiles": ("profile_id",),
        "runs": ("run_id",), "frames": ("frame_id",),
        "presets": ("preset_id",), "sessions": ("session_id",),
        "visual_frames": ("session_id", "frame_id"),
    }
    require(isinstance(data, dict) and set(data) == set(fields),
            "JSON должен содержать семь коллекций логической модели")
    for name, expected in fields.items():
        require(isinstance(data[name], list), f"{name}: ожидается список")
        seen = set()
        for row in data[name]:
            require(isinstance(row, dict) and set(row) == expected,
                    f"{name}: набор полей не совпадает с моделью")
            require(all(isinstance(v, (str, int, float)) and not isinstance(v, bool)
                        for v in row.values()), f"{name}: нужны атомарные значения")
            require(all(positive_id(v) for k, v in row.items() if k.endswith('_id')),
                    f"{name}: идентификаторы должны быть положительными целыми")
            require(all(isinstance(v, str) and bool(v.strip()) for k, v in row.items()
                        if k in {"title", "source_uri", "name", "analyzer_version", "started_at"}),
                    f"{name}: текстовые поля должны быть непустыми строками")
            key = tuple(row[k] for k in primary_keys[name])
            require(key not in seen, f"{name}: повтор первичного ключа {key}")
            seen.add(key)

    for track in data["tracks"]:
        require(positive_id(track["sample_rate"]) and positive_id(track["sample_count"]),
                "Трек: частота и число отсчётов должны быть положительными")
    for profile in data["profiles"]:
        n, hop = profile["frame_size"], profile["hop_size"]
        require(positive_id(n) and n & (n - 1) == 0, "Размер кадра — степень двойки")
        require(positive_id(hop) and hop <= n, "Шаг кадра должен быть от 1 до N")
    for preset in data["presets"]:
        require(number(preset["smoothing_alpha"]) and 0 < preset["smoothing_alpha"] <= 1,
                "Коэффициент сглаживания должен быть в (0; 1]")
        require(number(preset["brightness_gain"]) and preset["brightness_gain"] >= 0,
                "Усиление яркости должно быть неотрицательным")
        require(number(preset["hue_offset"]) and 0 <= preset["hue_offset"] < 1,
                "Сдвиг оттенка должен быть в [0; 1)")

    for run in data["runs"]:
        find_record(data["tracks"], "track_id", run["track_id"])
        find_record(data["profiles"], "profile_id", run["profile_id"])
    frame_positions = set()
    for frame in data["frames"]:
        run = find_record(data["runs"], "run_id", frame["run_id"])
        track = find_record(data["tracks"], "track_id", run["track_id"])
        require(type(frame["frame_index"]) is int and frame["frame_index"] >= 0,
                "Индекс кадра должен быть неотрицательным целым")
        position = (frame["run_id"], frame["frame_index"])
        require(position not in frame_positions, "Повтор индекса кадра внутри анализа")
        frame_positions.add(position)
        require(number(frame["rms"]) and 0 <= frame["rms"] <= 1,
                "RMS нормализованного PCM должен быть в [0; 1]")
        require(number(frame["centroid_hz"]) and
                0 <= frame["centroid_hz"] <= track["sample_rate"] / 2,
                "Центроид должен лежать в диапазоне частот трека")
    for session in data["sessions"]:
        find_record(data["runs"], "run_id", session["run_id"])
        find_record(data["presets"], "preset_id", session["preset_id"])
    for row in data["visual_frames"]:
        session = find_record(data["sessions"], "session_id", row["session_id"])
        frame = find_record(data["frames"], "frame_id", row["frame_id"])
        require(frame["run_id"] == session["run_id"], "Кадр относится к другому анализу")
        require(number(row["brightness"]) and 0 <= row["brightness"] <= 1,
                "Яркость должна быть в [0; 1]")
        require(number(row["hue"]) and 0 <= row["hue"] < 1,
                "Оттенок должен быть в [0; 1)")
    return data


def next_id(records, field):
    return max((row[field] for row in records), default=0) + 1
