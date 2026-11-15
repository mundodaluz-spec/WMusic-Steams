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

# Modelos (todos de código aberto, rodam no computador, sem internet depois de baixados)
MODELO_6 = "htdemucs_6s.yaml"                                   # Demucs 6 stems (Meta)
MODELO_4 = "htdemucs.yaml"
MODELO_VOZ = "model_bs_roformer_ep_317_sdr_12.9755.ckpt"        # BS-RoFormer: voz
MODELO_BACKS = "mel_band_roformer_karaoke_aufr33_viperx_sdr_10.1956.ckpt"  # voz principal × backs
MODELO_SOPROS = "17_HP-Wind_Inst-UVR.pth"                       # sopros (metais e madeiras)
MODELO_PECAS = "MDX23C-DrumSep-aufr33-jarredou.ckpt"            # bumbo, caixa, tons, chimbal, ride, crash
TAMANHO_MB = {MODELO_6: 55, MODELO_VOZ: 640, MODELO_BACKS: 915, MODELO_SOPROS: 225, MODELO_PECAS: 440}

NOMES = {
    "vocals": ("voz", "Voz"),
    "drums": ("bateria", "Bateria"),
    "bass": ("baixo", "Baixo"),
    "guitar": ("guitarra", "Guitarra"),
    "piano": ("teclas", "Teclas"),
    "other": ("outros", "Outros"),
    "instrumental": ("instrumental", "Instrumental"),
}
ORDEM = ["voz", "backs", "bateria", "bumbo", "caixa", "tons", "chimbal", "pratos",
         "baixo", "guitarra", "teclas", "sopros", "outros", "instrumental"]
OPCIONAIS = {"backs", "guitarra", "teclas", "sopros", "bumbo", "caixa", "tons", "chimbal", "pratos"}
LIMIAR_DB = -42.0   # canal opcional abaixo disso (relativo à música) é "não tem": vai para Outros


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


def _nome_do_arquivo(caminho: str) -> str | None:
    """Nome do stem como o modelo escreveu no arquivo: 'vocals', 'no woodwinds', 'kick'..."""
    m = re.search(r"\(([^)]+)\)[^()]*$", os.path.basename(caminho))
    return m.group(1).strip().lower() if m else None


def _pasta_do_modelo(modelo: str, pasta_modelos: str) -> str:
    """Usa o modelo que veio com o programa; se não tiver, baixa (1ª vez) na pasta do usuário."""
    if os.path.exists(os.path.join(pasta_modelos, modelo)):
        return pasta_modelos
    from .projeto import pasta_usuario
    alt = os.path.join(pasta_usuario(), "modelos", "separacao")
    os.makedirs(alt, exist_ok=True)
    return alt


def _preparar_biblioteca():
    from audio_separator.separator import Separator
    # Lemos e gravamos tudo com soundfile: o FFmpeg externo não é usado.
    Separator.check_ffmpeg_installed = lambda self: None
    # A biblioteca reduz o volume de qualquer stem que passe de 1,0 ao gravar:
    # desligado, para cada stem manter o ganho exato (e a soma fechar).
    from audio_separator.separator import common_separator as _cs
    _cs.spec_utils.normalize = lambda wave, max_peak=1.0, min_peak=None: wave
    return Separator


def _rodar(audio, taxa, pasta_modelos, modelo, qualidade, p, f0, f1, fator_tempo, texto):
    """Roda UM modelo; devolve ({nome do stem: áudio na taxa original, alinhado}, atraso corrigido)."""
    Separator = _preparar_biblioteca()
    n = len(audio)
    x44 = reamostrar(audio, taxa, TAXA_MODELO)
    # Modelos como MDX/RoFormer dependem do nível: com a música baixa tiram bem menos.
    # A entrada vai para pico −1 dBFS (e o ganho é desfeito na saída).
    pico = float(np.max(np.abs(x44))) or 1.0
    escala = 0.89 / pico
    x44 = x44 * escala
    pasta = _pasta_do_modelo(modelo, pasta_modelos)
    with tempfile.TemporaryDirectory(prefix="wmsteams_") as tmp:
        entrada = os.path.join(tmp, "mix.wav")
        sf.write(entrada, x44, TAXA_MODELO, subtype="FLOAT")
        demucs = {"segment_size": "Default", "shifts": 2 if qualidade == "alta" else 1,
                  "overlap": 0.25, "segments_enabled": True}
        sep = Separator(
            model_file_dir=pasta, output_dir=tmp, output_format="WAV",
            normalization_threshold=1.0, amplification_threshold=0.0, use_soundfile=True,
            sample_rate=TAXA_MODELO, demucs_params=demucs,
            # RoFormer/MDXC: sobreposição 4 na "alta" e 2 na "rápida" (8 é o padrão, lento sem placa de vídeo)
            mdxc_params={"segment_size": 256, "override_model_segment_size": False, "batch_size": 1,
                         "overlap": 4 if qualidade == "alta" else 2, "pitch_shift": 0},
            vr_params={"batch_size": 1, "window_size": 512, "aggression": 5, "enable_tta": False,
                       "enable_post_process": False, "post_process_threshold": 0.2, "high_end_process": False},
        )
        if not os.path.exists(os.path.join(pasta, modelo)):
            mb = TAMANHO_MB.get(modelo)
            p(f"Baixando modelo{f' ({mb} MB)' if mb else ''}: só na primeira vez", f0)
        else:
            p("Carregando o modelo", f0)
        sep.load_model(model_filename=modelo)
        import threading, time
        fim = threading.Event()
        previsto = max(10.0, len(x44) / TAXA_MODELO * fator_tempo)

        def andamento():
            t0 = time.time()
            while not fim.wait(0.5):
                f = 1 - np.exp(-(time.time() - t0) / previsto * 1.6)
                p(texto, f0 + (f1 - f0) * 0.95 * f)
        threading.Thread(target=andamento, daemon=True).start()
        try:
            saidas = sep.separate(entrada)
        finally:
            fim.set()
        stems44: dict[str, np.ndarray] = {}
        for s_ in saidas:
            caminho = s_ if os.path.isabs(s_) else os.path.join(tmp, s_)
            nome = _nome_do_arquivo(caminho)
            if not nome:
                continue
            y, _sr = sf.read(caminho, dtype="float32", always_2d=True)
            if y.shape[1] == 1:
                y = np.repeat(y, 2, axis=1)
            stems44[nome] = ajustar_tamanho(y[:, :2], len(x44)) / escala
    if not stems44:
        raise RuntimeError("O modelo não devolveu nenhum stem: " + modelo)
    soma44 = sum(stems44.values())
    atraso = medir_atraso(x44 / escala, soma44)
    if atraso:
        stems44 = {k: deslocar(v, atraso) for k, v in stems44.items()}
    return {k: ajustar_tamanho(reamostrar(v, TAXA_MODELO, taxa), n) for k, v in stems44.items()}, atraso


def _db(v) -> float:
    return 20 * float(np.log10(np.sqrt(np.mean(np.asarray(v, np.float64) ** 2)) + 1e-20))


def separar(
    audio: np.ndarray,
    taxa: int,
    pasta_modelos: str,
    modelo: str | None = None,
    qualidade: str = "alta",
    progresso: Callable[[str, float], None] | None = None,
    backs: bool = True,
    sopros: bool = True,
    bateria_pecas: bool = False,
) -> tuple[dict[str, np.ndarray], dict]:
    """Separa e devolve ({chave: audio [n,2] na taxa original}, relatório).

    Cadeia (cada etapa trabalha em cima do que sobrou, e cada divisão fecha a conta):
      Alta:   voz pelo BS-RoFormer; resto pelo Demucs 6 stems.  Rápida: tudo pelo Demucs.
      Backs:  a voz é dividida em voz principal e backs (RoFormer karaokê).
      Sopros: o "outros" do Demucs é dividido em sopros e outros.
      Bateria por peça: a bateria vira bumbo, caixa, tons, chimbal e pratos.
    Canal opcional sem som de verdade (abaixo de −42 dB da música) não aparece: vai para Outros.
    No fim, "outros" = original − todos os outros canais, então a soma é o original exato."""
    p = progresso or (lambda *_: None)
    p("Preparando o áudio", 0.02)
    atrasos: dict[str, int] = {}
    usados: list[str] = []

    def rodar(x, mod, f0, f1, fator, texto):
        st, at = _rodar(x, taxa, pasta_modelos, mod, qualidade, p, f0, f1, fator, texto)
        atrasos[mod] = int(at)
        usados.append(mod)
        return st

    stems: dict[str, np.ndarray] = {}
    if modelo:  # um modelo só (testes / linha de comando)
        st = rodar(audio, modelo, 0.04, 0.78, 1.0, "Separando os instrumentos (pode levar alguns minutos)")
        for k, v in st.items():
            if k in NOMES:
                stems[NOMES[k][0]] = v
            elif k in ("no vocals", "no_vocals", "accompaniment"):
                stems["instrumental"] = v
    else:
        etapas = 1 + (qualidade == "alta") + backs + sopros + bateria_pecas
        fatias = np.linspace(0.04, 0.78, etapas + 1)
        e = 0
        if qualidade == "alta":
            v = rodar(audio, MODELO_VOZ, fatias[e], fatias[e + 1], 3.0, "Separando a voz (pode levar alguns minutos)")
            e += 1
            voz_total = v["vocals"]
            resto = (audio - voz_total).astype(np.float32)
            d = rodar(resto, MODELO_6, fatias[e], fatias[e + 1], 1.0, "Separando bateria, baixo, guitarra e teclas")
            e += 1
            d.pop("vocals", None)                 # sobra de voz do 2º modelo fica em "outros"
        else:
            d = rodar(audio, MODELO_6, fatias[e], fatias[e + 1], 1.0, "Separando os instrumentos")
            e += 1
            voz_total = d.pop("vocals")
        stems["voz"] = voz_total
        for k, v in d.items():
            if k in NOMES:
                stems[NOMES[k][0]] = v

        if backs:
            kk = rodar(voz_total, MODELO_BACKS, fatias[e], fatias[e + 1], 3.0, "Separando voz principal e backs")
            e += 1
            principal = kk.get("vocals")
            if principal is not None:
                stems["voz"] = principal
                stems["backs"] = (voz_total - principal).astype(np.float32)
        if sopros and "outros" in stems:
            ss = rodar(stems["outros"], MODELO_SOPROS, fatias[e], fatias[e + 1], 0.6, "Procurando sopros e metais")
            e += 1
            w = ss.get("woodwinds")
            if w is not None:
                stems["outros"] = (stems["outros"] - w).astype(np.float32)
                stems["sopros"] = w
        if bateria_pecas and "bateria" in stems:
            bb = rodar(stems["bateria"], MODELO_PECAS, fatias[e], fatias[e + 1], 1.5, "Separando as peças da bateria")
            e += 1
            total = stems.pop("bateria")
            pecas = {"bumbo": bb.get("kick"), "caixa": bb.get("snare"), "tons": bb.get("toms"), "chimbal": bb.get("hh")}
            pecas = {k: v for k, v in pecas.items() if v is not None}
            soma = sum(pecas.values()) if pecas else np.zeros_like(total)
            pecas["pratos"] = (total - soma).astype(np.float32)   # ride + crash + o que sobrou da bateria
            stems.update(pecas)

    # Canais opcionais sem som de verdade não aparecem (o conteúdo vai para Outros).
    ref = _db(audio)
    removidos = []
    for k in list(stems):
        if k in OPCIONAIS and _db(stems[k]) - ref < LIMIAR_DB:
            removidos.append(k)
            v = stems.pop(k)
            if k in ("bumbo", "caixa", "tons", "chimbal") and "pratos" in stems:
                stems["pratos"] = (stems["pratos"] + v).astype(np.float32)   # fica na bateria

    p("Alinhando os stems com o original", 0.79)
    if "outros" not in stems and "instrumental" not in stems and len(stems) > 1:
        stems["outros"] = np.zeros_like(audio)
    destino = "outros" if "outros" in stems else ("instrumental" if "instrumental" in stems else list(stems)[-1])
    soma = np.zeros_like(audio)
    for k, v in stems.items():
        if k != destino:
            soma += v
    residuo_antes = audio - soma - stems[destino]
    stems[destino] = (audio - soma).astype(np.float32)
    soma_final = sum(stems.values())
    rel = {
        "modelo": " + ".join(usados),
        "atraso_corrigido_amostras_44k": atrasos,
        "residuo_do_modelo_db": round(_db(residuo_antes) - ref, 1),
        "nulo_db": round(_db(audio - soma_final) - ref, 1),
        "canais_sem_som": removidos,
    }
    ordenado = {k: stems[k] for k in ORDEM if k in stems}
    return ordenado, rel
