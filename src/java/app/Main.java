import java.nio.file.*;
import com.google.gson.*;

public class Main {
    public static void main(String[] args) {
        try {
            if (args.length != 2 && args.length != 5)
                throw new IllegalArgumentException("Main input.json result.json [track_id profile_id preset_id]");
            Path input = Path.of(args[0]).toRealPath();
            Path output = Path.of(args[1]).toAbsolutePath().normalize();
            if (Files.exists(output) && Files.isSameFile(input, output))
                throw new IllegalArgumentException("Входной JSON и результат должны быть разными файлами");
            Gson gson = new GsonBuilder().setPrettyPrinting().create();
            Dataset data = InputJson.read(input, gson);
            int trackId = 1;
            int profileId = 1;
            int presetId = 1;
            if (args.length == 5) {
                trackId = Integer.parseInt(args[2]);
                profileId = Integer.parseInt(args[3]);
                presetId = Integer.parseInt(args[4]);
            }
            String summary = data.process(input.getParent(), trackId, profileId, presetId);
            Files.createDirectories(output.getParent());
            Files.writeString(output, gson.toJson(data) + System.lineSeparator());
            System.out.println(summary);
            System.out.println("Результат: " + output);
        } catch (Exception error) {
            System.err.println("Ошибка: " + error.getMessage());
            System.exit(1);
        }
    }
}
