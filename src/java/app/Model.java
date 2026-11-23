import java.util.*;
import javax.sound.sampled.*;
import java.nio.file.Path;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.io.IOException;

record Track(int track_id, String title, String source_uri, int sample_rate, int sample_count) {
    double[] read(Path directory) throws IOException, UnsupportedAudioFileException {
        var file = directory.resolve(source_uri).toFile();
        if (!AudioSystem.getAudioFileFormat(file).getType().equals(AudioFileFormat.Type.WAVE))
            throw new IOException("Нужен WAV");
        try (var audio = AudioSystem.getAudioInputStream(file)) {
            var fmt = audio.getFormat();
            if (!fmt.getEncoding().equals(AudioFormat.Encoding.PCM_SIGNED) || fmt.isBigEndian()
                    || fmt.getChannels() != 1 || fmt.getSampleSizeInBits() != 16
                    || fmt.getSampleRate() != sample_rate || audio.getFrameLength() != sample_count)
                throw new IOException("Проверьте формат WAV и метаданные трека");
            byte[] bytes = audio.readAllBytes();
            if (sample_count <= 0 || bytes.length != 2L * sample_count) throw new IOException("Неполный WAV");
            double[] samples = new double[sample_count];
            ByteBuffer pcm = ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN);
            for (int i = 0; i < samples.length; i++) {
                samples[i] = pcm.getShort() / 32768.0;
            }
            return samples;
        }
    }
}

record AnalysisProfile(int profile_id, String name, int frame_size, int hop_size) {
    AnalysisProfile {
        if (Integer.bitCount(frame_size) != 1 || frame_size <= 0 || hop_size <= 0 || hop_size > frame_size)
            throw new IllegalArgumentException("Неверные размер или шаг кадра");
    }
}

record AnalysisFrame(int frame_id, int run_id, int frame_index, double rms, double centroid_hz) {}
record VisualFrame(int session_id, int frame_id, double brightness, double hue) {}
record VisualizationSession(int session_id, int run_id, int preset_id, String started_at) {}
record AnalysisRun(int run_id, int track_id, int profile_id, String analyzer_version, String started_at) {
    List<AnalysisFrame> analyze(double[] samples, AnalysisProfile profile, int rate, int firstId) {
        var frames = new ArrayList<AnalysisFrame>();
        var spectrum = new Spectrum();
        Feature rms = new Rms();
        Feature centroid = new Centroid();
        int size = profile.frame_size();
        if (samples.length < size) throw new IllegalArgumentException("Трек короче кадра");
        int lastIndex = (samples.length - size) / profile.hop_size();
        if (lastIndex > Integer.MAX_VALUE - firstId) {
            throw new IllegalArgumentException("Недостаточно свободных идентификаторов кадров");
        }
        for (int start = 0; start <= samples.length - size; start += profile.hop_size()) {
            double[] frame = Arrays.copyOfRange(samples, start, start + size);
            double[] magnitudes = spectrum.calculate(frame);
            int index = frames.size();
            frames.add(new AnalysisFrame(firstId + index, run_id, index,
                    rms.measure(frame, magnitudes, rate), centroid.measure(frame, magnitudes, rate)));
        }
        return frames;
    }
}

record VisualPreset(int preset_id, String name, double smoothing_alpha, double brightness_gain, double hue_offset) {
    VisualPreset {
        if (!(smoothing_alpha > 0 && smoothing_alpha <= 1 && brightness_gain >= 0
                && Double.isFinite(brightness_gain) && hue_offset >= 0 && hue_offset < 1))
            throw new IllegalArgumentException("Некорректные коэффициенты пресета");
    }

    VisualFrame map(VisualizationSession session, AnalysisFrame frame, double previous, int rate) {
        double target = Math.min(1, frame.rms() * brightness_gain);
        double brightness = previous + smoothing_alpha * (target - previous);
        return new VisualFrame(session.session_id(), frame.frame_id(), brightness,
                (frame.centroid_hz() / (rate / 2.0) + hue_offset) % 1);
    }
}
