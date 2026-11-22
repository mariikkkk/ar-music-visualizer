import java.nio.file.Path;
import java.time.Instant;
import java.util.*;
import javax.sound.sampled.UnsupportedAudioFileException;
import java.io.IOException;

final class Dataset {
    private List<Track> tracks;
    private List<AnalysisProfile> profiles;
    private List<VisualPreset> presets;
    private List<AnalysisRun> runs;
    private List<AnalysisFrame> frames;
    private List<VisualizationSession> sessions;
    private List<VisualFrame> visual_frames;

    private static <T> void add(Map<Integer,T> index, int id, T row) {
        if (id <= 0 || index.containsKey(id)) {
            throw new IllegalArgumentException("Некорректный ключ " + id);
        }
        index.put(id, row);
    }

    private static <T> T lookup(Map<Integer,T> map, int id) {
        T item = map.get(id);
        if (item == null) throw new IllegalArgumentException("Отсутствует запись " + id);
        return item;
    }

    private static int next(Map<Integer,?> map) {
        int largest = 0;
        for (int id : map.keySet()) {
            largest = Math.max(largest, id);
        }
        return Math.incrementExact(largest);
    }

    String process(Path directory, int trackId, int profileId, int presetId)
            throws IOException, UnsupportedAudioFileException {
        Map<Integer, Track> trackIndex = new HashMap<>();
        for (Track row : tracks) {
            add(trackIndex, row.track_id(), row);
        }
        Map<Integer, AnalysisProfile> profileIndex = new HashMap<>();
        for (AnalysisProfile row : profiles) {
            add(profileIndex, row.profile_id(), row);
        }
        Map<Integer, VisualPreset> presetIndex = new HashMap<>();
        for (VisualPreset row : presets) {
            add(presetIndex, row.preset_id(), row);
        }
        Map<Integer, AnalysisRun> runIndex = new HashMap<>();
        for (AnalysisRun row : runs) {
            add(runIndex, row.run_id(), row);
        }
        Map<Integer, AnalysisFrame> frameIndex = new HashMap<>();
        for (AnalysisFrame row : frames) {
            add(frameIndex, row.frame_id(), row);
        }
        Map<Integer, VisualizationSession> sessionIndex = new HashMap<>();
        for (VisualizationSession row : sessions) {
            add(sessionIndex, row.session_id(), row);
        }
        for (var run : runs) {
            lookup(trackIndex, run.track_id());
            lookup(profileIndex, run.profile_id());
        }
        checkFrames(runIndex, trackIndex);
        for (var session : sessions) {
            lookup(runIndex, session.run_id());
            lookup(presetIndex, session.preset_id());
        }
        checkVisualFrames(frameIndex, sessionIndex);
        var track = lookup(trackIndex, trackId);
        var preset = lookup(presetIndex, presetId);
        var profile = lookup(profileIndex, profileId);
        String now = Instant.now().toString();
        var run = new AnalysisRun(next(runIndex), trackId, profileId, "1.0", now);
        var session = new VisualizationSession(next(sessionIndex), run.run_id(), presetId, now);
        var fresh = run.analyze(track.read(directory), profile, track.sample_rate(), next(frameIndex));
        runs.add(run);
        sessions.add(session);
        frames.addAll(fresh);
        double previous = 0;
        for (var f : fresh) {
            var visual = preset.map(session, f, previous, track.sample_rate());
            visual_frames.add(visual);
            previous = visual.brightness();
        }
        var first = fresh.get(0);
        var last = visual_frames.get(visual_frames.size()-1);
        return String.format(Locale.ROOT, "Анализ: %d; сеанс: %d; кадров: %d%nПервый кадр: RMS=%.4f; центроид=%.2f Гц%nПоследний кадр: яркость=%.4f; оттенок=%.4f; масштаб=%.4f",
                run.run_id(), session.session_id(), fresh.size(), first.rms(), first.centroid_hz(),
                last.brightness(), last.hue(), 1 + last.brightness());
    }

    private void checkFrames(Map<Integer,AnalysisRun> runsById, Map<Integer,Track> tracksById) {
        Set<List<Integer>> positions = new HashSet<>();
        for (AnalysisFrame frame : frames) {
            AnalysisRun run = lookup(runsById, frame.run_id());
            Track track = lookup(tracksById, run.track_id());
            if (frame.frame_index() < 0 || !positions.add(List.of(frame.run_id(), frame.frame_index()))) {
                throw new IllegalArgumentException("Некорректный индекс кадра");
            }
            if (frame.rms() < 0 || frame.rms() > 1) {
                throw new IllegalArgumentException("RMS должен быть от 0 до 1");
            }
            if (frame.centroid_hz() < 0 || frame.centroid_hz() > track.sample_rate() / 2.0) {
                throw new IllegalArgumentException("Центроид вне диапазона частот трека");
            }
        }
    }

    private void checkVisualFrames(Map<Integer,AnalysisFrame> framesById,
                                   Map<Integer,VisualizationSession> sessionsById) {
        Set<List<Integer>> pairs = new HashSet<>();
        for (VisualFrame visual : visual_frames) {
            AnalysisFrame frame = lookup(framesById, visual.frame_id());
            VisualizationSession session = lookup(sessionsById, visual.session_id());
            if (frame.run_id() != session.run_id()) {
                throw new IllegalArgumentException("Кадр относится к другому анализу");
            }
            if (!pairs.add(List.of(visual.session_id(), visual.frame_id()))) {
                throw new IllegalArgumentException("Повтор визуального кадра");
            }
            if (visual.brightness() < 0 || visual.brightness() > 1 || visual.hue() < 0 || visual.hue() >= 1) {
                throw new IllegalArgumentException("Яркость или оттенок вне диапазона");
            }
        }
    }
}
