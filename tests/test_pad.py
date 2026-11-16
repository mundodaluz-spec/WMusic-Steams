"""Pad contínuo: fica no tom, não segue os acordes, só muda em modulação de verdade."""
import os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from wmsteams import pad  # noqa: E402

ok = falhas = 0
def caso(nome, cond):
    global ok, falhas
    print(("OK   " if cond else "FALHA") + " " + nome); ok += bool(cond); falhas += not cond

N = pad.NOTAS
def ac_de(blocos):
    out, t = [], 0.0
    for prog, ate in blocos:
        while t < ate:
            for r, menor in prog:
                i = N.index(r); out.append({"t0": t, "t1": t + 2, "nome": r + ("m" if menor else ""),
                                            "notas": [i, (i + (3 if menor else 4)) % 12, (i + 7) % 12]})
                t += 2
    return out

G = [("G", 0), ("D", 0), ("E", 1), ("C", 0)]
A = [("A", 0), ("E", 0), ("F#", 1), ("D", 0)]
so_iv = [("C", 0), ("G", 0), ("C", 0), ("D", 0)]   # refrão "parado" no IV
tr = pad.trechos_de_tom(ac_de([(G, 200)]), 200, "G")
caso("música toda em G: um trecho só, em G", tr == [(0.0, 200, 7)])
tr = pad.trechos_de_tom(ac_de([(G, 60), (so_iv, 100), (G, 180)]), 180, "G")
caso("parte no IV não muda o pad", len(tr) == 1 and tr[0][2] == 7)
tr = pad.trechos_de_tom(ac_de([(G, 150), (A, 220)]), 220, "G")
caso("modulação de 1 tom no fim muda para A", len(tr) == 2 and tr[1][2] == 9 and 140 <= tr[1][0] <= 160)
tr = pad.trechos_de_tom(ac_de([(G, 100), (A, 112), (G, 200)]), 200, "G")
caso("modulação curta (12 s) não muda", len(tr) == 1)

taxa = 22050; dur = 60; n = dur * taxa
ac = ac_de([(G, 56)])
x = pad.gerar_pad(ac, n, taxa, "Quente", modo="continuo", tom="G")
caso("mesmo tamanho da música e estéreo", x.shape == (n, 2) and np.isfinite(x).all())
S = np.abs(np.fft.rfft(x[:, 0])); F = np.fft.rfftfreq(n, 1 / taxa)
caso("sem estalos (quase nada acima de 5 kHz)", S[F > 5000].sum() / S.sum() < 0.002)
seg = lambda a, b: float(np.sqrt(np.mean(x[int(a * taxa):int(b * taxa)] ** 2)))
caso("entra devagar e fica estável", seg(0, 0.5) < seg(20, 21) * 0.2 and 0.6 < seg(20, 21) / seg(40, 41) < 1.6)
# no contínuo o espectro não muda com o acorde: compara 2 acordes diferentes
def espectro(a, b):
    s = np.abs(np.fft.rfft(x[int(a * taxa):int(b * taxa), 0] * np.hanning(int((b - a) * taxa))))
    return s / s.sum()
caso("não segue os acordes (G e Em soam como o mesmo G e G)",
     np.abs(espectro(20, 22) - espectro(24, 26)).sum() < 1.6 * np.abs(espectro(20, 22) - espectro(36, 38)).sum())
# notas: tônica G e quinta D, sem a terça B
f = np.fft.rfftfreq(int(4 * taxa), 1 / taxa); s = np.abs(np.fft.rfft(x[20 * taxa:24 * taxa, 0]))
def energia(hz): return s[(f > hz * 0.985) & (f < hz * 1.015)].max()
caso("tem tônica e quinta, sem terça", min(energia(98.0), energia(293.66)) > 20 * max(energia(123.47), energia(246.94)))
y = pad.gerar_pad(ac, n, taxa, "Quente", modo="continuo", tom="G", tom_fixo="E")
s2 = np.abs(np.fft.rfft(y[20 * taxa:24 * taxa, 0]))
caso("tom fixo escolhido (E)", s2[(f > 81.4) & (f < 83.4)].max() > 5 * s2[(f > 97) & (f < 99)].max())
z = pad.gerar_pad(ac, n, taxa, "Quente", modo="acordes")
caso("modo acordes continua funcionando", z.shape == (n, 2) and np.abs(z).max() > 0.01)
print(f"\n{ok}/{ok + falhas}")
sys.exit(1 if falhas else 0)
