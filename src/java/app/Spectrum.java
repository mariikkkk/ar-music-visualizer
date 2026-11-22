final class Spectrum {
    double[] calculate(double[] frame) {
        int n = frame.length;
        if (Integer.bitCount(n) != 1) throw new IllegalArgumentException("Размер кадра — степень двойки");
        double[] real = frame.clone(), imag = new double[n];
        fft(real, imag);
        double[] magnitudes = new double[n / 2 + 1];
        for (int k = 0; k < magnitudes.length; k++) magnitudes[k] = Math.hypot(real[k], imag[k]);
        return magnitudes;
    }

    private void fft(double[] real, double[] imag) {
        int half = real.length / 2;
        if (half == 0) return;
        // Рекурсивно считаем спектры чётных и нечётных отсчётов.
        double[] evenReal = new double[half], evenImag = new double[half];
        double[] oddReal = new double[half], oddImag = new double[half];
        for (int i = 0; i < half; i++) {
            evenReal[i] = real[2 * i];
            oddReal[i] = real[2 * i + 1];
        }
        fft(evenReal, evenImag);
        fft(oddReal, oddImag);
        // Объединяем два спектра половин в спектр всего кадра.
        for (int k = 0; k < half; k++) {
            double phase = -Math.PI * k / half;
            double cos = Math.cos(phase), sin = Math.sin(phase);
            double termReal = cos * oddReal[k] - sin * oddImag[k];
            double termImag = sin * oddReal[k] + cos * oddImag[k];
            real[k] = evenReal[k] + termReal;
            imag[k] = evenImag[k] + termImag;
            real[k + half] = evenReal[k] - termReal;
            imag[k + half] = evenImag[k] - termImag;
        }
    }
}
