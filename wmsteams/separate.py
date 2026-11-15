"""Separação em stems com garantia de fase.

O modelo trabalha a 44,1 kHz. O caminho é:
original (taxa do arquivo) -> 44,1 kHz (resample_poly, fase linear e sem atraso)
-> modelo -> volta para a taxa original -> mede e corrige qualquer atraso
residual por correlação -> corta/completa para o comprimento exato do
original -> "restante" = original − soma dos outros stems.

Resultado: a soma de todos os stems é o original amostra por amostra
(teste de nulo), então nada fica fora de fase quando tudo toca junto.
"""
from __future__ import annotations

import glob
import os
import re
import tempfile
from fractions import Fraction
from typing import Callable

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

TAXA_MODELO = 44100

# Modelo padrão: 6 stems (voz, bateria, baixo, guitarra, piano, outros).
MODELO_6 = "htdemucs_6s.yaml"
MODELO_4 = "htdemucs.yaml"

# Nome que o modelo usa -> (chave interna, nome na tela)
NOMES = {
    "vocals": ("voz", "Voz"),
    "drums": ("bateria", "Bateria"),
    "bass": ("baixo", "Baixo"),
    "guitar": ("guitarra", "Guitarra"),
    "piano": ("teclas", "Teclas"),
    "other": ("outros", "Outros"),
    "instrumental": ("instrumental", "Instrumental"),
}
ORDEM = ["voz", "bateria", "baixo", "guitarra", "teclas", "outros", "instrumental"]


def reamostrar(x: np.ndarray, de: int, para: int) -> np.ndarray:
    """Reamostra [amostras, canais] sem atraso (resample_poly compensa o filtro)."""
    if de == para:
        return x
    r = Fraction(para, de).limit_denominator(10000)
    y = resample_poly(x, r.numerator, r.denominator, axis=0)
    return y.astype(np.float32, copy=False)


def medir_atraso(ref: np.ndarray, sinal: np.ndarray, max_lag: int = 4096) -> int:
    """Atraso (em amostras) de `sinal` em relação a `ref`, por correlação cruzada
    na mono de um trecho com bastante energia. Positivo = sinal atrasado."""
    a = ref.mean(axis=1) if ref.ndim == 2 else ref
    b = sinal.mean(axis=1) if sinal.ndim == 2 else sinal
    n = min(len(a), len(b))
    if n < 4 * max_lag:
        max_lag = max(1, n // 4)
    # janela de até 20 s no trecho mais forte
    jan = min(n, 20 * TAXA_MODELO)
    if n > jan:
        energia = np.convolve(a[:n] ** 2, np.ones(4096), "valid")[:: 4096]
        ini = int(np.argmax(np.convolve(energia, np.ones(max(1, jan // 4096)), "valid"))) * 4096
        ini = min(ini, n - jan)
    else:
        ini = 0
    x = a[ini:ini + jan].astype(np.float64)
    y = b[ini:ini + jan].astype(np.float64)
    if not np.any(x) or not np.any(y):
        return 0
    m = 1 << int(np.ceil(np.log2(len(x) + len(y))))
    c = np.fft.irfft(np.fft.rfft(y, m) * np.conj(np.fft.rfft(x, m)), m)
    lags = np.concatenate([c[: max_lag + 1], c[-max_lag:]])
    idx = int(np.argmax(lags))
    return idx if idx <= max_lag else idx - (2 * max_lag + 1)


def deslocar(x: np.ndarray, atraso: int) -> np.ndarray:
    """Remove um atraso positivo (adianta) ou negativo (atrasa) mantendo o tamanho."""
    if atraso == 0:
        return x
    y = np.zeros_like(x)
    if atraso > 0:
        y[:-atraso] = x[atraso:]
    else:
        y[-atraso:] = x[:atraso]
    return y


def ajustar_tamanho(x: np.ndarray, n: int) -> np.ndarray:
    if len(x) == n:
        return x
    if len(x) > n:
        return x[:n]
    return np.concatenate([x, np.zeros((n - len(x),) + x.shape[1:], x.dtype)])


def _chave_do_arquivo(caminho: str) -> str | None:
    m = re.search(r"\(([^)]+)\)[^()]*$", os.path.basename(caminho))
    if not m:
        return None
    nome = m.group(1).strip().lower()
    for k in NOMES:
        if nome == k:
            return k
    if nome in ("no vocals", "no_vocals", "accompaniment"):
        return "instrumental"
    return None


def separar(
    audio: np.ndarray,
    taxa: int,
    pasta_modelos: str,
    modelo: str = MODELO_6,
    qualidade: str = "alta",
    progresso: Callable[[str, float], None] | None = None,
) -> tuple[dict[str, np.ndarray], dict]:
    """Separa e devolve ({chave: audio [n,2] na taxa original}, relatório)."""
    from audio_separator.separator import Separator
    # Lemos e gravamos tudo com soundfile: o FFmpeg externo não é usado.
    Separator.check_ffmpeg_installed = lambda self: None
    # A biblioteca reduz o volume de qualquer stem que passe de 1,0 ao gravar:
    # desligado, para cada stem manter o ganho exato (e a soma fechar).
    from audio_separator.separator import common_separator as _cs
    _cs.spec_utils.normalize = lambda wave, max_peak=1.0, min_peak=None: wave

    p = progresso or (lambda *_: None)
    n = len(audio)
    p("Preparando o áudio", 0.02)
    x44 = reamostrar(audio, taxa, TAXA_MODELO)
    # Modelos como o MDX dependem do nível de entrada: com a música baixa eles tiram
    # bem menos voz. A entrada vai para pico −1 dBFS (e o ganho é desfeito na saída).
    pico = float(np.max(np.abs(x44))) or 1.0
    escala = 0.89 / pico
    x44 = x44 * escala

    with tempfile.TemporaryDirectory(prefix="wmsteams_") as tmp:
        entrada = os.path.join(tmp, "mix.wav")
        sf.write(entrada, x44, TAXA_MODELO, subtype="FLOAT")
        demucs = {"segment_size": "Default", "shifts": 2 if qualidade == "alta" else 1,
                  "overlap": 0.25, "segments_enabled": True}
        sep = Separator(
            model_file_dir=pasta_modelos,
            output_dir=tmp,
            output_format="WAV",
            normalization_threshold=1.0,   # com a folga acima, nunca chega a agir
            amplification_threshold=0.0,
            use_soundfile=True,
            sample_rate=TAXA_MODELO,
            demucs_params=demucs,
        )
        p("Carregando o modelo de separação", 0.06)
        sep.load_model(model_filename=modelo)
        p("Separando os instrumentos (pode levar alguns minutos)", 0.10)
        # o modelo não informa o andamento: estimativa pelo tempo, sem passar de 90%
        import threading, time
        fim = threading.Event()
        previsto = max(20.0, len(x44) / TAXA_MODELO * (1.0 if qualidade == "alta" else 0.5))
        def andamento():
            t0 = time.time()
            while not fim.wait(0.5):
                f = 1 - np.exp(-(time.time() - t0) / previsto * 1.6)
                p("Separando os instrumentos (pode levar alguns minutos)", 0.10 + 0.80 * 0.9 * f)
        th = threading.Thread(target=andamento, daemon=True); th.start()
        try:
            saidas = sep.separate(entrada)
        finally:
            fim.set()
        stems44: dict[str, np.ndarray] = {}
        for s in saidas:
            caminho = s if os.path.isabs(s) else os.path.join(tmp, s)
            k = _chave_do_arquivo(caminho)
            if not k:
                continue
            y, sr = sf.read(caminho, dtype="float32", always_2d=True)
            if y.shape[1] == 1:
                y = np.repeat(y, 2, axis=1)
            stems44[NOMES[k][0]] = ajustar_tamanho(y[:, :2], len(x44)) / escala
        for f in glob.glob(os.path.join(tmp, "*")):
            try:
                os.remove(f)
            except OSError:
                pass

    if not stems44:
        raise RuntimeError("O modelo não devolveu nenhum stem.")

    p("Alinhando os stems com o original", 0.80)
    soma44 = sum(stems44.values())
    atraso = medir_atraso(x44 / escala, soma44)
    if atraso:
        stems44 = {k: deslocar(v, atraso) for k, v in stems44.items()}

    stems: dict[str, np.ndarray] = {}
    for k, v in stems44.items():
        stems[k] = ajustar_tamanho(reamostrar(v, TAXA_MODELO, taxa), n)

    # Fecha a conta: o que o modelo não pôs em nenhum stem vai para "outros"
    # (ou para o instrumental), então a soma volta a ser exatamente o original.
    destino = "outros" if "outros" in stems else ("instrumental" if "instrumental" in stems else list(stems)[-1])
    soma = np.zeros_like(audio)
    for k, v in stems.items():
        if k != destino:
            soma += v
    residuo_antes = audio - soma - stems[destino]
    stems[destino] = (audio - soma).astype(np.float32)

    def db(v):
        r = float(np.sqrt(np.mean(v.astype(np.float64) ** 2)) + 1e-20)
        return 20 * np.log10(r)

    soma_final = sum(stems.values())
    rel = {
        "modelo": modelo,
        "atraso_corrigido_amostras_44k": int(atraso),
        "residuo_do_modelo_db": round(db(residuo_antes) - db(audio), 1),
        "nulo_db": round(db(audio - soma_final) - db(audio), 1),
    }
    ordenado = {k: stems[k] for k in ORDEM if k in stems}
    return ordenado, rel
