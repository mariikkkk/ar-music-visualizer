"""Расчёт спектра, признаков звука и параметров визуализации."""

import cmath
import math


def _fft(values):
    """Рекурсивное БПФ. Размер заранее проверяется в calculate_spectrum."""
    size = len(values)
    if size == 1:
        return [complex(values[0])]

    even = _fft(values[::2])
    odd = _fft(values[1::2])
    result = [0j] * size
    for k in range(size // 2):
        term = cmath.exp(-2j * math.pi * k / size) * odd[k]
        result[k] = even[k] + term
        result[k + size // 2] = even[k] - term
    return result


def calculate_spectrum(frame):
    """Модули N/2 + 1 частотных составляющих вещественного кадра."""
    size = len(frame)
    if size == 0 or size & (size - 1):
        raise ValueError("Размер кадра должен быть положительной степенью двойки")
    transformed = _fft(frame)
    spectrum = []
    for k in range(size // 2 + 1):
        spectrum.append(abs(transformed[k]))
    return spectrum


def extract_features(frame, spectrum, sample_rate):
    """RMS и спектральный центроид. Готовый спектр поступает на вход."""
    size = len(frame)
    if size == 0:
        return {"rms": 0.0, "centroid_hz": 0.0}
    if sample_rate <= 0 or len(spectrum) != size // 2 + 1:
        raise ValueError("Неверная частота дискретизации или длина спектра")

    square_sum = 0.0
    for value in frame:
        square_sum += value * value

    magnitude_sum = 0.0
    weighted_sum = 0.0
    for k in range(len(spectrum)):
        magnitude_sum += spectrum[k]
        weighted_sum += k * sample_rate / size * spectrum[k]

    if magnitude_sum <= 1e-12:
        centroid = 0.0
    else:
        centroid = weighted_sum / magnitude_sum
    return {"rms": math.sqrt(square_sum / size), "centroid_hz": centroid}


def map_visual_frame(features, preset, previous, sample_rate):
    """Пресет задаёт усиление, сдвиг оттенка и коэффициент сглаживания."""
    target_brightness = min(1.0, features["rms"] * preset["brightness_gain"])
    target_hue = (features["centroid_hz"] / (sample_rate / 2)
                  + preset["hue_offset"]) % 1.0
    alpha = preset["smoothing_alpha"]
    brightness = previous["brightness"] + alpha * (
        target_brightness - previous["brightness"])
    # Сглаживается яркость; оттенок задаётся центроидом без интерполяции по кругу.
    return {"brightness": brightness, "hue": target_hue}
