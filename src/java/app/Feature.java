interface Feature {
    double measure(double[] frame, double[] spectrum, int rate);
}

final class Rms implements Feature {
    public double measure(double[] frame, double[] spectrum, int rate) {
        double sum = 0;
        for (double sample : frame) sum += sample * sample;
        return frame.length == 0 ? 0 : Math.sqrt(sum / frame.length);
    }
}

// Частотные признаки усредняют функцию частоты с весами из спектра.
abstract class SpectralFeature implements Feature {
    protected abstract double valueAt(double hz);

    public final double measure(double[] frame, double[] spectrum, int rate) {
        if (frame.length == 0) return 0;
        if (rate <= 0 || spectrum.length != frame.length / 2 + 1)
            throw new IllegalArgumentException("Неверная частота или размер спектра");
        double sum = 0, weighted = 0;
        for (int k = 0; k < spectrum.length; k++) {
            sum += spectrum[k];
            weighted += valueAt((double) k * rate / frame.length) * spectrum[k];
        }
        return sum <= 1e-12 ? 0 : weighted / sum;
    }
}

final class Centroid extends SpectralFeature {
    @Override protected double valueAt(double hz) { return hz; }
}
