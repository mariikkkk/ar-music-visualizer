import com.google.gson.Gson;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.google.gson.JsonPrimitive;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Set;

final class InputJson {
    static Dataset read(Path path, Gson gson) throws IOException {
        JsonObject root = JsonParser.parseString(Files.readString(path)).getAsJsonObject();
        if (root.size() != 7) {
            throw new IllegalArgumentException("В JSON должно быть семь коллекций");
        }
        checkTable(root, "tracks", "track_id", "title", "source_uri", "sample_rate", "sample_count");
        checkTable(root, "profiles", "profile_id", "name", "frame_size", "hop_size");
        checkTable(root, "presets", "preset_id", "name", "smoothing_alpha", "brightness_gain", "hue_offset");
        checkTable(root, "runs", "run_id", "track_id", "profile_id", "analyzer_version", "started_at");
        checkTable(root, "frames", "frame_id", "run_id", "frame_index", "rms", "centroid_hz");
        checkTable(root, "sessions", "session_id", "run_id", "preset_id", "started_at");
        checkTable(root, "visual_frames", "session_id", "frame_id", "brightness", "hue");
        return gson.fromJson(root, Dataset.class);
    }

    private static void checkTable(JsonObject root, String name, String... fields) {
        JsonElement rows = root.get(name);
        if (rows == null || !rows.isJsonArray()) {
            throw new IllegalArgumentException("Ожидается список: " + name);
        }
        Set<String> expected = Set.of(fields);
        for (JsonElement item : rows.getAsJsonArray()) {
            if (!item.isJsonObject() || !item.getAsJsonObject().keySet().equals(expected)) {
                throw new IllegalArgumentException("Неверные поля в коллекции " + name);
            }
            JsonObject row = item.getAsJsonObject();
            for (String field : fields) {
                checkValue(field, row.get(field));
            }
        }
    }

    private static void checkValue(String field, JsonElement element) {
        if (!element.isJsonPrimitive()) {
            throw new IllegalArgumentException("Ожидается число или строка: " + field);
        }
        JsonPrimitive value = element.getAsJsonPrimitive();
        switch (field) {
            case "name", "title", "source_uri", "started_at", "analyzer_version" -> {
                if (!value.isString() || value.getAsString().isBlank()) {
                    throw new IllegalArgumentException("Ожидается непустая строка: " + field);
                }
            }
            case "rms", "centroid_hz", "brightness", "hue", "smoothing_alpha", "brightness_gain", "hue_offset" -> {
                if (!value.isNumber() || !Double.isFinite(value.getAsDouble())) {
                    throw new IllegalArgumentException("Ожидается конечное число: " + field);
                }
            }
            default -> {
                if (!value.isNumber()) throw new IllegalArgumentException("Ожидается целое число: " + field);
                int number;
                try {
                    number = Integer.parseInt(value.getAsString());
                } catch (NumberFormatException error) {
                    throw new IllegalArgumentException("Ожидается целое число в диапазоне int: " + field);
                }
                int minimum = field.equals("frame_index") ? 0 : 1;
                if (number < minimum) throw new IllegalArgumentException("Недопустимое значение: " + field);
            }
        }
    }
}
