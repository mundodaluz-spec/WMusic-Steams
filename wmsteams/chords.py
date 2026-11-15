"""Acordes da música, a partir dos stems harmônicos (sem bateria e sem voz).

Cromagrama com janela centrada (o tempo de cada quadro é o centro da janela,
então a troca de acorde não sai atrasada), comparação com modelos de acordes
maiores, menores, com sétima e suspensos, suavização por Viterbi e ajuste fino
de cada troca para o ataque mais próximo do baixo.
"""
from __future__ import annotations

import numpy as np

from .separate import reamostrar

NOTAS = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]
TIPOS = {  # intervalos a partir da tônica
    "": (0, 4, 7),
    "m": (0, 3, 7),
    "7": (0, 4, 7, 10),
    "m7": (0, 3, 7, 10),
    "7M": (0, 4, 7, 11),
    "sus4": (0, 5, 7),
}
PESO_TIPO = {"": 1.0, "m": 1.0, "7": 0.92, "m7": 0.92, "7M": 0.9, "sus4": 0.86}

SR = 11025
HOP = 512          # ~46 ms
NFFT = 8192        # ~0,74 s: resolução para separar notas graves


def _croma(x: np.ndarray, fmin: float, fmax: float) -> np.ndarray:
    """[quadros, 12], quadros centrados em i*HOP."""
    pad = NFFT // 2
    x = np.concatenate([np.zeros(pad), x, np.zeros(pad)]).astype(np.float32)
    nq = 1 + (len(x) - NFFT) // HOP
    f = np.fft.rfftfreq(NFFT, 1 / SR)
    sel = (f >= fmin) & (f <= fmax)
    midi = 69 + 12 * np.log2(f[sel] / 440.0)
    pc = np.mod(np.round(midi), 12).astype(int)
    desvio = np.abs(midi - np.round(midi))
    peso = np.clip(1 - 2 * desvio, 0, 1)  # só o que está perto de uma nota
    M = np.zeros((sel.sum(), 12), np.float32)
    M[np.arange(len(pc)), pc] = peso
    jan = np.hanning(NFFT).astype(np.float32)
    out = np.empty((nq, 12), np.float32)
    for i0 in range(0, nq, 512):
        idx = np.arange(NFFT)[None, :] + HOP * np.arange(i0, min(nq, i0 + 512))[:, None]
        mag = np.abs(np.fft.rfft(x[idx] * jan, axis=1))[:, sel]
        out[i0:i0 + len(idx)] = (mag ** 0.5) @ M
    return out


def _fluxo_ataques(x: np.ndarray, nq: int) -> np.ndarray:
    """Fluxo espectral com janela curta (93 ms), centrado nos mesmos quadros."""
    n = 1024
    pad = n // 2
    y = np.concatenate([np.zeros(pad), x, np.zeros(pad)]).astype(np.float32)
    q = 1 + (len(y) - n) // HOP
    jan = np.hanning(n).astype(np.float32)
    idx = np.arange(n)[None, :] + HOP * np.arange(q)[:, None]
    mag = np.log1p(50 * np.abs(np.fft.rfft(y[idx] * jan, axis=1)))
    f = np.maximum(0, np.diff(mag, axis=0, prepend=mag[:1])).sum(axis=1)
    f = np.concatenate([f, np.zeros(max(0, nq - len(f)))])[:nq]
    return f


def _modelos():
    nomes, mats, pesos, notas = [], [], [], []
    for r in range(12):
        for tipo, iv in TIPOS.items():
            v = np.zeros(12)
            for k, i in enumerate(iv):
                v[(r + i) % 12] = 1.0 if k < 3 else 0.7
            v[r] += 0.3
            v = v - v.mean()
            mats.append(v / np.linalg.norm(v))
            nomes.append(NOTAS[r] + tipo)
            pesos.append(PESO_TIPO[tipo])
            notas.append([(r + i) % 12 for i in iv])
    return nomes, np.array(mats), np.array(pesos), notas


def detectar(stems: dict[str, np.ndarray], taxa: int) -> dict:
    sem_altura = ("bateria", "bumbo", "caixa", "tons", "chimbal", "pratos", "voz", "backs")
    harm = [v for k, v in stems.items() if k not in sem_altura]
    if not harm:
        harm = list(stems.values())
    mix = sum(harm).mean(axis=1)
    baixo = stems.get("baixo")
    x = reamostrar(mix[:, None], taxa, SR)[:, 0]
    C = _croma(x, 60, 2000)
    if baixo is not None:
        b = reamostrar(baixo.mean(axis=1)[:, None], taxa, SR)[:, 0]
        B = _croma(b, 35, 300)
    else:
        B = _croma(x, 35, 200)
    nq = min(len(C), len(B))
    C, B = C[:nq], B[:nq]
    energia = C.sum(axis=1)
    Cc = C - C.mean(axis=1, keepdims=True)
    Cn = Cc / (np.linalg.norm(Cc, axis=1, keepdims=True) + 1e-9)
    Bc = np.maximum(0, B - B.mean(axis=1, keepdims=True))
    Bn = Bc / (Bc.max(axis=1, keepdims=True) + 1e-9)

    nomes, T, pesos, notas = _modelos()
    tonicas = np.array([NOTAS.index(n[:2] if len(n) > 1 and n[1] in "#b" else n[0]) for n in nomes])
    S = (Cn @ T.T) * pesos[None, :] + 0.25 * Bn[:, tonicas]  # baixo puxa a tônica
    silencio = energia < 0.05 * (np.percentile(energia, 95) + 1e-9)

    # Viterbi: ficar no mesmo acorde é bem mais provável que trocar
    K = len(nomes) + 1  # + "N" (sem acorde)
    Sc = np.concatenate([S, np.full((nq, 1), 0.2)], axis=1)
    Sc[silencio, :-1] -= 1.0
    troca = 0.35
    custo = Sc[0].copy()
    volta = np.zeros((nq, K), np.int32)
    for t in range(1, nq):
        melhor = int(np.argmax(custo))
        fica = custo
        muda = custo[melhor] - troca
        escolhe_mudar = muda > fica
        volta[t] = np.where(escolhe_mudar, melhor, np.arange(K))
        custo = np.where(escolhe_mudar, muda, fica) + Sc[t]
    cam = np.empty(nq, np.int32)
    cam[-1] = int(np.argmax(custo))
    for t in range(nq - 1, 0, -1):
        cam[t - 1] = volta[t, cam[t]]

    # segmentos
    seg = []
    i = 0
    while i < nq:
        j = i
        while j + 1 < nq and cam[j + 1] == cam[i]:
            j += 1
        seg.append([i, j + 1, int(cam[i])])
        i = j + 1
    # descarta acordes de menos de 0,45 s (junta no vizinho)
    minq = int(0.45 * SR / HOP)
    limpo = []
    for s in seg:
        if limpo and (s[1] - s[0] < minq or s[2] == limpo[-1][2]):
            limpo[-1][1] = s[1]
        else:
            limpo.append(s)

    # troca de acorde encosta no ataque mais forte por perto (±350 ms)
    fluxo = _fluxo_ataques(x, nq)
    raio = int(0.35 * SR / HOP)
    dt = HOP / SR
    acordes = []
    for k, (a, b, c) in enumerate(limpo):
        if k > 0:
            lo, hi = max(0, a - raio), min(nq, a + raio + 1)
            a2 = lo + int(np.argmax(fluxo[lo:hi]))
            acordes[-1]["t1"] = round(a2 * dt, 3)
            a = a2
        if c == K - 1:
            nome, nts = "N", []
        else:
            nome, nts = nomes[c], notas[c]
        acordes.append({"t0": round(a * dt, 3), "t1": round(b * dt, 3), "nome": nome, "notas": nts})
    if acordes:
        acordes[0]["t0"] = 0.0
    acordes = [a for a in acordes if a["t1"] - a["t0"] > 0.05]
    return {"acordes": acordes, "tom": estimar_tom(C)}


def estimar_tom(C: np.ndarray) -> str:
    """Krumhansl-Schmuckler sobre o cromagrama médio."""
    maior = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
    menor = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
    m = C.mean(axis=0)
    melhor, nome = -9, "C"
    for r in range(12):
        for perfil, suf in ((maior, ""), (menor, "m")):
            c = np.corrcoef(m, np.roll(perfil, r))[0, 1]
            if c > melhor:
                melhor, nome = c, NOTAS[r] + suf
    return nome
