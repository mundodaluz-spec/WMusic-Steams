"""Canal de PAD.

Modo CONTÍNUO (padrão): um pad parado no tom da música (tônica, quinta e
nona, sem a terça, então serve para maior e menor e casa com todos os acordes
do tom). Não segue os acordes: só muda se a música mudar de tom e ficar no
tom novo por um bom tempo, com uma passagem lenta. Entra devagar quando a
música começa e sai devagar no fim.

Modo ACORDES: o pad que acompanha os acordes da música.

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


NOTAS = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
_MAIOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
_MENOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
MODOS = ("continuo", "acordes")


def _pc(nome: str | None) -> int | None:
    if not nome:
        return None
    n = nome.strip().rstrip("m")
    n = {"Db": "C#", "Eb": "D#", "Gb": "F#", "Ab": "G#", "Bb": "A#"}.get(n, n)
    return NOTAS.index(n) if n in NOTAS else None


def trechos_de_tom(acordes: list[dict], dur: float, tom: str | None,
                   janela: float = 32.0, minimo: float = 28.0) -> list[tuple[float, float, int]]:
    """[(t0, t1, tônica)]: o tom da música ao longo do tempo, bem estável.
    Só aceita mudança de tom que fique pelo menos `minimo` segundos."""
    glob = _pc(tom)
    menor = bool(tom) and tom.strip().endswith("m")
    perfil = _MENOR if menor else _MAIOR
    ac = [a for a in acordes if a.get("nome") != "N" and a.get("notas")]
    if not ac:
        return [(0.0, dur, glob if glob is not None else 0)]
    passo = 1.0
    ts = np.arange(0.0, max(dur, passo), passo)
    t0s = np.array([a["t0"] for a in ac]); t1s = np.array([a["t1"] for a in ac])
    hist = np.zeros((len(ts), 12))
    for i, t in enumerate(ts):
        a, b = t - janela / 2, t + janela / 2
        sob = np.clip(np.minimum(t1s, b) - np.maximum(t0s, a), 0, None)
        for k in np.nonzero(sob)[0]:
            notas = ac[k]["notas"]
            for j, pc in enumerate(notas):
                hist[i, pc % 12] += sob[k] * (2.0 if j == 0 else 1.0)
    escolha = np.zeros(len(ts), int)
    for i in range(len(ts)):
        h = hist[i]
        if h.sum() <= 0:
            escolha[i] = -1; continue
        notas_r = [np.corrcoef(h, np.roll(perfil, r))[0, 1] + (0.06 if r == glob else 0.0) for r in range(12)]
        escolha[i] = int(np.nanargmax(notas_r))
    # preenche buracos e aplica histerese
    atual = glob if glob is not None else next((x for x in escolha if x >= 0), 0)
    if escolha[0] >= 0 and glob is None:
        atual = escolha[0]
    seq = np.full(len(ts), atual)
    i = 0
    run_ini, run_k = None, None
    for i, k in enumerate(escolha):
        # modulação de verdade em música é subir/descer 1 a 3 semitons; 4ª/5ª é quase sempre
        # só a parte da música que fica no IV ou no V, então o pad continua no tom
        if k >= 0 and min((k - atual) % 12, (atual - k) % 12) not in (1, 2, 3):
            k = atual
        if k < 0 or k == atual:
            run_ini = run_k = None
        elif k == run_k:
            if (i - run_ini) * passo >= minimo:
                atual = k
                seq[run_ini:i + 1] = k
                run_ini = run_k = None
                continue
        else:
            run_ini, run_k = i, k
        seq[i] = atual
    # trechos, começando a mudança no começo do acorde mais perto
    out = []
    ini = 0.0
    for i in range(1, len(seq)):
        if seq[i] != seq[i - 1]:
            t = ts[i]
            t = float(t0s[np.argmin(np.abs(t0s - t))]) if abs(t0s[np.argmin(np.abs(t0s - t))] - t) < 4 else t
            out.append((ini, t, int(seq[i - 1]))); ini = t
    out.append((ini, dur, int(seq[-1])))
    # junta trechos iguais vizinhos
    final = []
    for a, b, k in out:
        if final and final[-1][2] == k:
            final[-1] = (final[-1][0], b, k)
        elif b > a:
            final.append((a, b, k))
    return final


def _continuo(acordes, n, taxa, timbre, tom, tom_fixo, semente):
    harm, decai, cents, _, _ = TIMBRES.get(timbre, TIMBRES["Quente"])
    tab = _tabela_onda(max(3, harm - 4), decai + 0.3)
    L = len(tab)
    dur = n / taxa
    ac = [a for a in acordes if a.get("nome") != "N" and a.get("notas")]
    inicio = max(0.0, ac[0]["t0"]) if ac else 0.0
    fim = min(dur, ac[-1]["t1"]) if ac else dur
    fixo = _pc(tom_fixo)
    trechos = [(0.0, dur, fixo)] if fixo is not None else trechos_de_tom(acordes, dur, tom)
    rng = np.random.default_rng(semente)
    # vozes: (semitons acima da tônica grave, ganho)  -> 1, 8ª, 5ª, 8ª, 9ª, 5ª aguda
    vozes = [(0, 0.50), (12, 0.42), (19, 0.30), (24, 0.24), (26, 0.12), (31, 0.07)]
    lfo = [(rng.uniform(0.03, 0.09), rng.random()) for _ in vozes]
    cruz = 6.0                       # passagem de um tom para outro (s)
    entra, sai = 5.0, 6.0
    out = np.zeros((n, 2), np.float32)
    bloco = 1 << 17
    for (a, b, r) in trechos:
        grave = 36 + r if 36 + r >= 38 else 48 + r     # tônica entre D2 e C#3
        fases = rng.random((len(vozes), 3))
        i0 = max(0, int((a - cruz / 2) * taxa)); i1 = min(n, int((b + cruz / 2) * taxa))
        for c0 in range(i0, i1, bloco):
            c1 = min(i1, c0 + bloco)
            t = np.arange(c0, c1) / taxa
            # envelope do trecho (passagem em potência constante)
            e = np.ones_like(t)
            if a > 0.01:
                x = np.clip((t - (a - cruz / 2)) / cruz, 0, 1); e *= np.sin(0.5 * np.pi * x)
            if b < dur - 0.01:
                x = np.clip(((b + cruz / 2) - t) / cruz, 0, 1); e *= np.sin(0.5 * np.pi * x)
            # entrada e saída da música
            e *= 0.5 - 0.5 * np.cos(np.pi * np.clip((t - inicio) / entra, 0, 1))
            e *= 0.5 - 0.5 * np.cos(np.pi * np.clip((fim + 2.0 - t) / sai, 0, 1))
            if not e.any():
                continue
            acc = np.zeros((c1 - c0, 2), np.float32)
            for v, (st, g) in enumerate(vozes):
                f = 440.0 * 2 ** ((grave + st - 69) / 12)
                fl, fasel = lfo[v]
                mov = 1.0 - 0.18 * (0.5 + 0.5 * np.sin(2 * np.pi * (fl * t + fasel)))
                for j, (d, pan) in enumerate(((-cents, 0.2), (0.0, 0.5), (cents, 0.8))):
                    fd = f * 2 ** (d / 1200)
                    idx = (((fases[v, j] + fd * t) % 1.0) * L).astype(np.int64) % L
                    sv = tab[idx] * (g * mov)
                    acc[:, 0] += sv * np.sqrt(1 - pan); acc[:, 1] += sv * np.sqrt(pan)
            out[c0:c1] += acc * e[:, None].astype(np.float32)
    return out, 1800.0


def gerar_pad(acordes: list[dict], n: int, taxa: int, timbre: str = "Quente",
              volume_db: float = -16.0, semente: int = 7, modo: str = "continuo",
              tom: str | None = None, tom_fixo: str | None = None) -> np.ndarray:
    if modo != "acordes":
        out, corte = _continuo(acordes, n, taxa, timbre, tom, tom_fixo, semente)
        return _finalizar(out, taxa, corte, volume_db)
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
    return _finalizar(out, taxa, 2500.0, volume_db)


def _finalizar(out, taxa, corte, volume_db):
    # passa-baixa, ida e volta: sem atraso nenhum
    a = np.exp(-2 * np.pi * corte / taxa)
    from scipy.signal import filtfilt
    out = filtfilt([1 - a], [1, -a], out, axis=0).astype(np.float32)  # fase zero
    vivo = np.abs(out).max(axis=1) > 1e-4
    rms = float(np.sqrt(np.mean(out[vivo] ** 2))) if vivo.any() else 1.0
    alvo = 10 ** (volume_db / 20)
    out *= alvo / rms
    pico = float(np.max(np.abs(out)))
    if pico > 0.9:
        out *= 0.9 / pico
    return out
