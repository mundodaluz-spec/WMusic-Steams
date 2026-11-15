"""Gera uma 'música' sintética com acordes conhecidos para os testes (C G Am F)."""
import sys
import numpy as np, soundfile as sf

def gerar(caminho, sr=48000, bpm=100, compassos=8):
    seg_compasso = 4 * 60 / bpm
    n = int(sr * seg_compasso * compassos)
    t = np.arange(n) / sr
    acordes = [(60, 64, 67), (55, 59, 62), (57, 60, 64), (53, 57, 60)]  # C G Am F
    mix = np.zeros((n, 2))
    f = lambda m: 440 * 2 ** ((m - 69) / 12)
    for c in range(compassos):
        a = acordes[c % 4]
        i0, i1 = int(c * seg_compasso * sr), int((c + 1) * seg_compasso * sr)
        tt = t[i0:i1] - t[i0]
        env = np.minimum(1, tt / 0.02) * np.exp(-tt * 0.6)
        ch = sum(np.sin(2 * np.pi * f(m) * tt) + 0.3 * np.sin(4 * np.pi * f(m) * tt) for m in a) * 0.08 * env
        baixo = np.sin(2 * np.pi * f(a[0] - 24) * tt) * 0.25 * env
        voz = np.sin(2 * np.pi * f(a[2] + 12) * tt + 0.3 * np.sin(2 * np.pi * 5 * tt)) * 0.12 * np.minimum(1, tt / 0.1)
        mix[i0:i1, 0] += ch + baixo + voz
        mix[i0:i1, 1] += ch * 0.8 + baixo + voz
    # bumbo a cada tempo
    beat = int(60 / bpm * sr)
    for i in range(0, n, beat):
        k = np.arange(min(4000, n - i))
        mix[i:i + len(k)] += (np.sin(2 * np.pi * 55 * k / sr * np.exp(-k / 2000)) * np.exp(-k / 1500) * 0.4)[:, None]
    sf.write(caminho, mix.astype(np.float32), sr, subtype="FLOAT")
    return acordes

if __name__ == "__main__":
    gerar(sys.argv[1])
