"""Monta a música de teste do CI: acordes C G Am F + bateria + fala (se houver fala.wav).
Gera teste.wav e teste.mp4 (AAC) para conferir também a leitura de vídeo."""
import os, subprocess, sys
import numpy as np, soundfile as sf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gerar_musica import gerar

gerar("teste.wav", sr=48000, compassos=8)
mix, sr = sf.read("teste.wav", dtype="float32", always_2d=True)
if os.path.exists("fala.wav"):
    fala, sr2 = sf.read("fala.wav", dtype="float32", always_2d=True)
    fala = fala.mean(axis=1)
    if sr2 != sr:
        from scipy.signal import resample_poly
        fala = resample_poly(fala, sr, sr2).astype(np.float32)
    fala = fala / (np.max(np.abs(fala)) + 1e-9) * 0.5
    i0 = int(1.0 * sr)
    k = min(len(fala), len(mix) - i0)
    mix[i0:i0 + k] += fala[:k, None]
    mix *= 0.8 / np.max(np.abs(mix))
    sf.write("teste.wav", mix, sr, subtype="FLOAT")
# mesmo áudio dentro de um MP4 (vídeo + AAC), como um vídeo de celular
try:
    import imageio_ffmpeg
    ff = imageio_ffmpeg.get_ffmpeg_exe()
except Exception:
    ff = "ffmpeg"
subprocess.run([ff, "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=black:s=320x240:r=30:d=%.2f" % (len(mix) / sr),
                "-i", "teste.wav", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "256k",
                "-shortest", "teste.mp4"], check=True)
print("teste.wav / teste.mp4", len(mix) / sr, "s")
