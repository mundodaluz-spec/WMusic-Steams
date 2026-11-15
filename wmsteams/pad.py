"""Canal de PAD que acompanha os acordes da música.

Gera o pad na MESMA taxa e com o MESMO comprimento do original, a partir da
linha do tempo dos acordes; então ele começa e muda de acorde exatamente junto
com a música. Vozes com condução suave (cada acorde escolhe a inversão mais
perto do anterior), três osciladores levemente desafinados abertos no
estéreo, ataque e soltura lentos e um filtro passa-baixa suave.
"""
from __future__ import annotations

import numpy as np

TIMBRES = {
    # nome: (harmônicos, decaimento, desafinação em cents, ataque s, soltura s)
    "Quente": (10, 1.6, 7.0, 0.6, 1.2),
    "Brilhante": (18, 1.1, 9.0, 0.4, 0.9),
    "Suave": (5, 2.2, 5.0, 0.9, 1.6),
}


def _voicing(notas: list[int], anterior: list[int] | None) -> list[int]:
    """Notas MIDI (tônica grave + tríade na região 52-72), perto do acorde anterior."""
    if not notas:
        return []
    tonica = notas[0]
    grave = 36 + tonica if 36 + tonica >= 40 else 48 + tonica
    pcs = notas[:4]
    candidatos = []
    for base in range(52, 64):
        v = sorted(base + ((pc - base) % 12) for pc in pcs)
        candidatos.append(v)
    if anterior:
        ant = anterior[1:]
        def dist(v):
            return sum(min(abs(n - a) for a in ant) for n in v) + 0.2 * abs(np.mean(v) - 62)
        melhor = min(candidatos, key=dist)
    else:
        melhor = min(candidatos, key=lambda v: abs(np.mean(v) - 62))
    return [grave] + melhor


def _tabela_onda(harm: int, decai: float, n: int = 4096) -> np.ndarray:
    t = np.arange(n) / n
    w = np.zeros(n)
    for k in range(1, harm + 1):
        w += np.sin(2 * np.pi * k * t) / (k ** decai)
    return (w / np.max(np.abs(w))).astype(np.float32)


def gerar_pad(acordes: list[dict], n: int, taxa: int, timbre: str = "Quente",
              volume_db: float = -16.0, semente: int = 7) -> np.ndarray:
    harm, decai, cents, ataque, soltura = TIMBRES.get(timbre, TIMBRES["Quente"])
    tab = _tabela_onda(harm, decai)
    L = len(tab)
    rng = np.random.default_rng(semente)
    out = np.zeros((n, 2), np.float32)
    anterior = None
    for a in acordes:
        if a["nome"] == "N" or not a["notas"]:
            continue
        voz = _voicing(a["notas"], anterior)
        anterior = voz
        i0 = int(round(a["t0"] * taxa))
        i1 = int(round(a["t1"] * taxa))
        if i1 <= i0:
            continue
        fim = min(n, i1 + int(soltura * taxa))
        m = fim - i0
        t = np.arange(m) / taxa
        env = np.minimum(1.0, t / ataque)
        dur = (i1 - i0) / taxa
        env = np.where(t > dur, env * np.exp(-(t - dur) / (soltura / 4)), env)
        env *= 0.5 - 0.5 * np.cos(np.pi * np.minimum(1.0, t / ataque))  # S suave
        bloco = np.zeros((m, 2), np.float32)
        for k, nota in enumerate(voz):
            f = 440.0 * 2 ** ((nota - 69) / 12)
            ganho = 0.55 if k == 0 else 0.32
            for d, pan in ((-cents, 0.15), (0.0, 0.5), (cents, 0.85)):
                fd = f * 2 ** (d / 1200)
                fase = rng.random()
                idx = ((fase + fd * t) * L).astype(np.int64) % L
                s = tab[idx] * ganho
                bloco[:, 0] += s * np.sqrt(1 - pan)
                bloco[:, 1] += s * np.sqrt(pan)
        bloco *= env[:, None].astype(np.float32)
        out[i0:fim] += bloco

    # passa-baixa (~2,5 kHz), ida e volta: sem atraso nenhum
    a = np.exp(-2 * np.pi * 2500 / taxa)
    from scipy.signal import filtfilt
    out = filtfilt([1 - a], [1, -a], out, axis=0)  # fase zero.astype(np.float32)
    rms = float(np.sqrt(np.mean(out ** 2))) or 1.0
    alvo = 10 ** (volume_db / 20)
    out *= alvo / rms
    pico = float(np.max(np.abs(out)))
    if pico > 0.9:
        out *= 0.9 / pico
    return out
