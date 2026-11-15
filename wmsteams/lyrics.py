"""Letra com o tempo de cada palavra, sem internet (Whisper small, int8, CPU).

Transcreve o stem de VOZ (sem a banda, o Whisper erra bem menos) e refina o
início de cada palavra pela energia real da voz, para a palavra acender na
hora em que é cantada e não alguns quadros depois.
"""
from __future__ import annotations

import os
from typing import Callable

import numpy as np

from .separate import reamostrar


def envelope_voz(audio: np.ndarray, sr: int = 16000, hop: float = 0.01):
    n = int(sr * 0.032)
    h = int(sr * hop)
    if len(audio) < n:
        return np.zeros(1), hop
    jan = np.hanning(n).astype(np.float32)
    quadros = 1 + (len(audio) - n) // h
    esp = np.empty(quadros, np.float64)
    f = np.fft.rfftfreq(n, 1.0 / sr)
    banda = (f >= 250) & (f <= 3800)
    for i0 in range(0, quadros, 4096):  # em blocos, para não estourar a memória
        idx = np.arange(n)[None, :] + h * np.arange(i0, min(quadros, i0 + 4096))[:, None]
        e = np.abs(np.fft.rfft(audio[idx] * jan, axis=1)) ** 2
        esp[i0:i0 + len(idx)] = e[:, banda].sum(axis=1)
    e = 10 * np.log10(esp + 1e-10)
    return np.convolve(e, np.ones(3) / 3, mode="same"), hop


def refinar_inicio(palavras: list[dict], env: np.ndarray, hop: float) -> None:
    for w in palavras:
        i0, i1 = int(w["t0"] / hop), int(w["t1"] / hop)
        if i1 - i0 < 3 or i1 >= len(env):
            continue
        trecho = env[i0:i1 + 1]
        meio = len(trecho) // 2 if len(trecho) > 40 else 0
        pico = meio + int(np.argmax(trecho[meio:]))
        baixo = float(trecho[:pico + 1].min())
        alto = float(trecho[pico])
        if alto - baixo < 6:
            continue
        limiar = baixo + 0.35 * (alto - baixo)
        k = pico
        while k > 0 and trecho[k - 1] >= limiar:
            k -= 1
        novo = (i0 + k) * hop
        if novo > w["t0"]:
            w["t0"] = round(min(novo, w["t1"] - 0.05), 3)


def agrupar_linhas(palavras: list[dict], segmentos: list[tuple[float, float]]) -> list[dict]:
    """Quebra em linhas: fim de frase do Whisper, pausa > 0,7 s ou 9 palavras."""
    linhas: list[dict] = []
    atual: list[dict] = []
    fins = [s[1] for s in segmentos]

    def fecha():
        if atual:
            linhas.append({"t0": atual[0]["t0"], "t1": atual[-1]["t1"],
                           "texto": " ".join(p["w"] for p in atual), "palavras": list(atual)})
            atual.clear()

    for i, p in enumerate(palavras):
        if atual:
            pausa = p["t0"] - atual[-1]["t1"]
            fim_frase = any(abs(atual[-1]["t1"] - f) < 0.05 for f in fins)
            if pausa > 0.7 or len(atual) >= 9 or fim_frase:
                fecha()
        atual.append(p)
    fecha()
    return linhas


def transcrever(
    voz: np.ndarray,
    taxa: int,
    pasta_modelo: str,
    idioma: str | None = "pt",
    dica: str | None = None,
    progresso: Callable[[str, float], None] | None = None,
) -> dict:
    from faster_whisper import WhisperModel

    p = progresso or (lambda *_: None)
    if not os.path.exists(os.path.join(pasta_modelo, "model.bin")):
        raise RuntimeError("Modelo de letra não encontrado em " + pasta_modelo)
    mono = voz.mean(axis=1) if voz.ndim == 2 else voz
    a16 = reamostrar(mono[:, None], taxa, 16000)[:, 0].astype(np.float32)
    pico = float(np.max(np.abs(a16))) or 1.0
    a16 = a16 * min(4.0, 0.9 / pico)  # voz isolada costuma vir baixa
    dur = len(a16) / 16000.0
    modelo = WhisperModel(pasta_modelo, device="cpu", compute_type="int8")
    segs, info = modelo.transcribe(
        a16, language=idioma or None, word_timestamps=True,
        initial_prompt=(dica or None) and " ".join(dica.split())[:600],
        condition_on_previous_text=False, beam_size=5,
        vad_filter=True, vad_parameters={"min_silence_duration_ms": 700},
    )
    palavras: list[dict] = []
    segmentos: list[tuple[float, float]] = []
    for s in segs:
        segmentos.append((s.start, s.end))
        for w in (s.words or []):
            t = w.word.strip()
            if t:
                palavras.append({"w": t, "t0": round(w.start, 3), "t1": round(w.end, 3)})
        if dur > 0:
            p("Escrevendo a letra", min(0.99, s.end / dur))
    try:
        env, hop = envelope_voz(a16)
        refinar_inicio(palavras, env, hop)
    except Exception:
        pass
    return {"idioma": info.language, "linhas": agrupar_linhas(palavras, segmentos)}


def para_lrc(letra: dict) -> str:
    def ts(t):
        m, s = divmod(max(0.0, t), 60)
        return f"[{int(m):02d}:{s:05.2f}]"
    return "\n".join(ts(l["t0"]) + l["texto"] for l in letra.get("linhas", [])) + "\n"
