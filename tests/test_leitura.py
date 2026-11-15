"""Leitura sem defasagem: um clique em 1,000 s tem que sair na amostra exata,
em WAV, FLAC, MP3, M4A, MP4 e MOV, a 44,1 e 48 kHz."""
import os, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np, soundfile as sf
from wmsteams.decode import ler_audio
from wmsteams.separate import medir_atraso, reamostrar

try:
    import imageio_ffmpeg
    FF = imageio_ffmpeg.get_ffmpeg_exe()
except Exception:
    FF = "ffmpeg"

ok = falhas = 0
def confere(nome, cond, extra=""):
    global ok, falhas
    if cond: ok += 1; print("OK  ", nome, extra)
    else: falhas += 1; print("FALHA", nome, extra)

rng = np.random.default_rng(5)
with tempfile.TemporaryDirectory() as d:
    for sr in (44100, 48000):
        # ruído musical (banda limitada) + clique: a correlação mede o atraso exato
        x = np.zeros((sr * 4, 2), np.float32)
        ruido = np.convolve(rng.standard_normal(sr * 4), np.hanning(16), "same") * 0.05
        x[:, 0] = x[:, 1] = ruido
        ref = os.path.join(d, f"r{sr}.wav"); sf.write(ref, x, sr, subtype="FLOAT")
        cmds = {
            "wav": [], "flac": ["-c:a", "flac"], "mp3": ["-c:a", "libmp3lame", "-b:a", "256k"],
            "m4a": ["-c:a", "aac", "-b:a", "256k"],
        }
        for ext, args in cmds.items():
            f = os.path.join(d, f"t{sr}.{ext}")
            subprocess.run([FF, "-v", "error", "-y", "-i", ref] + args + [f], check=True)
            a, taxa, _ = ler_audio(f)
            atraso = medir_atraso(x, a[:len(x)])
            confere(f"{ext} {sr} Hz sem atraso", atraso == 0 and taxa == sr, f"atraso={atraso} tam={len(a)}/{len(x)}")
        for ext in ("mp4", "mov"):
            f = os.path.join(d, f"t{sr}.{ext}")
            subprocess.run([FF, "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=black:s=160x120:r=30:d=4", "-i", ref,
                            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "256k", "-shortest", f], check=True)
            a, taxa, _ = ler_audio(f)
            atraso = medir_atraso(x, a[:len(x)])
            confere(f"{ext} {sr} Hz sem atraso", atraso == 0 and taxa == sr, f"atraso={atraso}")

    # reamostragem ida e volta (48k -> 44,1k -> 48k) não desloca
    sr = 48000
    y = np.convolve(rng.standard_normal(sr * 3), np.hanning(32), "same")[:, None].repeat(2, 1).astype(np.float32) * 0.1
    z = reamostrar(reamostrar(y, 48000, 44100), 44100, 48000)[:len(y)]
    confere("reamostragem ida e volta sem atraso", medir_atraso(y, z) == 0)

print(f"\n{ok}/{ok+falhas} testes OK")
sys.exit(1 if falhas else 0)
