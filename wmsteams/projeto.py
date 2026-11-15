"""Projeto de uma música: pasta com os stems (WAV float 32), acordes, letra e
relatório. Os stems são gravados em ponto flutuante, sem nenhum
arredondamento, para a soma continuar idêntica ao original."""
from __future__ import annotations

import json
import os
import re
import struct
import sys
import time
from typing import Callable

import numpy as np

VERSAO = "1.0.0"

NOMES_TELA = {
    "voz": "Voz", "bateria": "Bateria", "baixo": "Baixo", "guitarra": "Guitarra",
    "teclas": "Teclas", "outros": "Outros", "instrumental": "Instrumental",
    "backs": "Backs", "sopros": "Sopros", "bumbo": "Bumbo", "caixa": "Caixa", "tons": "Tons",
    "chimbal": "Chimbal", "pratos": "Pratos",
    "pad": "Pad", "original": "Original",
}


# ---------------------------------------------------------------- pastas

def pasta_app() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def pasta_recursos() -> str:
    """Onde ficam assets e modelos (no Mac, dentro de .app/Contents/Resources)."""
    base = getattr(sys, "_MEIPASS", None)
    return base or pasta_app()


def pasta_usuario() -> str:
    if sys.platform == "win32":
        raiz = os.environ.get("APPDATA") or os.path.expanduser("~")
        p = os.path.join(raiz, "WMusic", "WMusic Steams")
    elif sys.platform == "darwin":
        p = os.path.expanduser("~/Library/Application Support/WMusic/WMusic Steams")
    else:
        p = os.path.expanduser("~/.local/share/WMusic/WMusic Steams")
    os.makedirs(p, exist_ok=True)
    return p


def pasta_biblioteca() -> str:
    musicas = os.path.join(os.path.expanduser("~"), "Music")
    if not os.path.isdir(musicas):
        musicas = os.path.join(os.path.expanduser("~"), "Músicas")
    if not os.path.isdir(musicas):
        musicas = os.path.expanduser("~")
    p = os.path.join(musicas, "WMusic Steams")
    os.makedirs(p, exist_ok=True)
    return p


def pasta_modelos_separacao() -> str:
    for p in (os.path.join(pasta_recursos(), "modelos", "separacao"),
              os.path.join(pasta_app(), "modelos", "separacao")):
        if os.path.isdir(p) and os.listdir(p):
            return p
    p = os.path.join(pasta_usuario(), "modelos", "separacao")  # baixa no 1º uso
    os.makedirs(p, exist_ok=True)
    return p


def pasta_modelo_letra() -> str | None:
    for p in (os.path.join(pasta_recursos(), "modelos", "letra"),
              os.path.join(pasta_app(), "modelos", "letra"),
              os.path.join(pasta_usuario(), "modelos", "letra")):
        if os.path.exists(os.path.join(p, "model.bin")):
            return p
    return None


# ---------------------------------------------------------------- preferências

def ler_config() -> dict:
    try:
        with open(os.path.join(pasta_usuario(), "config.json"), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def gravar_config(cfg: dict) -> None:
    atual = ler_config()
    atual.update(cfg)
    tmp = os.path.join(pasta_usuario(), "config.json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(atual, f, ensure_ascii=False, indent=1)
    os.replace(tmp, os.path.join(pasta_usuario(), "config.json"))


def smpte_padrao() -> dict:
    from .smpte import PADRAO
    d = dict(PADRAO)
    d.update(ler_config().get("smpte_padrao", {}))
    return d


# ---------------------------------------------------------------- WAV float

def gravar_wav_float(caminho: str, audio: np.ndarray, taxa: int) -> None:
    """WAV IEEE float 32 bits, estéreo, cabeçalho simples (dados no byte 44)."""
    a = np.ascontiguousarray(audio, dtype="<f4")
    ch = a.shape[1]
    dados = a.nbytes
    cab = b"RIFF" + struct.pack("<I", 36 + dados) + b"WAVE"
    cab += b"fmt " + struct.pack("<IHHIIHH", 16, 3, ch, taxa, taxa * ch * 4, ch * 4, 32)
    cab += b"data" + struct.pack("<I", dados)
    tmp = caminho + ".tmp"
    with open(tmp, "wb") as f:
        f.write(cab)
        a.tofile(f)
    os.replace(tmp, caminho)


def abrir_wav_float(caminho: str) -> tuple[np.memmap, int]:
    """Abre um WAV float 32 sem carregar na memória (memmap)."""
    with open(caminho, "rb") as f:
        if f.read(4) != b"RIFF":
            raise ValueError("WAV inválido: " + caminho)
        f.read(4)
        if f.read(4) != b"WAVE":
            raise ValueError("WAV inválido: " + caminho)
        taxa = ch = fmt = bits = None
        while True:
            cab = f.read(8)
            if len(cab) < 8:
                raise ValueError("WAV sem dados: " + caminho)
            nome, tam = cab[:4], struct.unpack("<I", cab[4:])[0]
            if nome == b"fmt ":
                d = f.read(tam)
                fmt, ch, taxa = struct.unpack("<HHI", d[:8])
                bits = struct.unpack("<H", d[14:16])[0]
            elif nome == b"data":
                ini = f.tell()
                break
            else:
                f.seek(tam + (tam & 1), 1)
    if fmt not in (3, 0xFFFE) or bits != 32:
        raise ValueError("O WAV não é float 32: " + caminho)
    n = tam // (4 * ch)
    mm = np.memmap(caminho, dtype="<f4", mode="r", offset=ini, shape=(n, ch))
    return mm, int(taxa)


# ---------------------------------------------------------------- projeto

def nome_seguro(t: str) -> str:
    t = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", t).strip().rstrip(".")
    return t[:80] or "Música"


def carregar(pasta: str) -> dict:
    with open(os.path.join(pasta, "projeto.json"), encoding="utf-8") as f:
        p = json.load(f)
    p["pasta"] = pasta
    return p


def salvar(projeto: dict) -> None:
    d = {k: v for k, v in projeto.items() if k != "pasta" and not k.startswith("_")}
    tmp = os.path.join(projeto["pasta"], "projeto.json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    os.replace(tmp, os.path.join(projeto["pasta"], "projeto.json"))


def listar_biblioteca() -> list[dict]:
    out = []
    raiz = pasta_biblioteca()
    for nome in sorted(os.listdir(raiz)):
        p = os.path.join(raiz, nome)
        if os.path.exists(os.path.join(p, "projeto.json")):
            try:
                out.append(carregar(p))
            except Exception:
                pass
    out.sort(key=lambda p: p.get("criado", 0), reverse=True)
    return out


def regerar_pad(projeto: dict, timbre: str, volume_db: float = -16.0) -> None:
    from .pad import gerar_pad
    taxa, n = projeto["taxa"], projeto["amostras"]
    pad = gerar_pad(projeto["acordes"], n, taxa, timbre=timbre, volume_db=volume_db)
    gravar_wav_float(os.path.join(projeto["pasta"], "pad.wav"), pad, taxa)
    projeto["pad_timbre"] = timbre
    salvar(projeto)


def processar(
    arquivo: str,
    qualidade: str = "alta",
    idioma: str | None = "pt",
    dica_letra: str | None = None,
    fazer_letra: bool = True,
    timbre_pad: str = "Quente",
    modelo: str | None = None,
    progresso: Callable[[str, float], None] | None = None,
    pasta_destino: str | None = None,
    backs: bool = True,
    sopros: bool = True,
    bateria_pecas: bool = False,
) -> dict:
    from .decode import ler_audio
    from .separate import separar
    from .chords import detectar
    from .pad import gerar_pad

    p = progresso or (lambda *_: None)
    t_ini = time.time()
    p("Lendo o arquivo", 0.0)
    audio, taxa, info = ler_audio(arquivo)
    n = len(audio)

    titulo = os.path.splitext(os.path.basename(arquivo))[0]
    raiz = pasta_destino or pasta_biblioteca()
    pasta = os.path.join(raiz, nome_seguro(titulo))
    k = 2
    while os.path.exists(pasta):
        pasta = os.path.join(raiz, f"{nome_seguro(titulo)} ({k})")
        k += 1
    os.makedirs(pasta)

    def faixa(a, b):
        return lambda m, f: p(m, a + (b - a) * f)

    gravar_wav_float(os.path.join(pasta, "original.wav"), audio, taxa)
    stems, rel = separar(audio, taxa, pasta_modelos_separacao(), modelo=modelo,
                         backs=backs, sopros=sopros, bateria_pecas=bateria_pecas,
                         qualidade=qualidade, progresso=faixa(0.03, 0.75))
    p("Gravando os stems", 0.76)
    for k_, v in stems.items():
        gravar_wav_float(os.path.join(pasta, k_ + ".wav"), v, taxa)

    p("Encontrando os acordes", 0.78)
    ac = detectar(stems, taxa)
    p("Gerando o pad", 0.80)
    pad = gerar_pad(ac["acordes"], n, taxa, timbre=timbre_pad)
    gravar_wav_float(os.path.join(pasta, "pad.wav"), pad, taxa)

    letra = {"idioma": idioma, "linhas": []}
    aviso_letra = None
    if fazer_letra and "voz" in stems:
        mod = pasta_modelo_letra()
        if mod:
            try:
                letra = __import__("wmsteams.lyrics", fromlist=["x"]).transcrever(
                    stems["voz"], taxa, mod, idioma=idioma, dica=dica_letra,
                    progresso=faixa(0.82, 0.98))
            except Exception as e:  # a letra nunca derruba o processamento
                aviso_letra = f"Não consegui escrever a letra: {e}"
        else:
            aviso_letra = "Modelo de letra não instalado."

    trilhas = list(stems.keys()) + ["pad"]
    projeto = {
        "app": "WMusic Steams", "versao": VERSAO, "titulo": titulo,
        "arquivo_original": os.path.abspath(arquivo), "taxa": taxa, "amostras": n,
        "duracao": n / taxa, "criado": time.time(), "info": info,
        "trilhas": trilhas, "acordes": ac["acordes"], "tom": ac["tom"],
        "letra": letra, "pad_timbre": timbre_pad, "relatorio": rel,
        "segundos_processamento": round(time.time() - t_ini, 1),
        "aviso_letra": aviso_letra,
        "mixer": {},
        "smpte": smpte_padrao(),
        "pasta": pasta,
    }
    salvar(projeto)
    p("Pronto", 1.0)
    return projeto


def conferir_fase(projeto: dict) -> float:
    """Teste de nulo: original − soma dos stems (sem o pad), em dB relativo."""
    pasta = projeto["pasta"]
    orig, _ = abrir_wav_float(os.path.join(pasta, "original.wav"))
    soma = np.zeros(orig.shape, np.float64)
    for t in projeto["trilhas"]:
        if t == "pad":
            continue
        a, _ = abrir_wav_float(os.path.join(pasta, t + ".wav"))
        soma += a
    dif = np.asarray(orig, np.float64) - soma
    r = lambda v: 20 * np.log10(np.sqrt(np.mean(v ** 2)) + 1e-20)
    return float(r(dif) - r(np.asarray(orig, np.float64)))
