"""Timecode SMPTE LTC (SMPTE 12M) gerado na hora, amostra por amostra.

O sinal de cada quadro depende só do número do quadro (o bit de correção de
polaridade deixa todo quadro começar com a mesma polaridade), então o LTC é
uma função da posição da música: tocar, pular, voltar no loop ou exportar dão
exatamente o mesmo sinal no mesmo lugar, sempre alinhado com os stems.

Quadro k começa na amostra round(k · taxa / fps) a partir do início da música,
e o primeiro quadro (posição 0) vale o timecode de início escolhido para a música.
"""
from __future__ import annotations

from fractions import Fraction

import numpy as np

# nome: (fps exato, quadros nominais, drop-frame)
TAXAS = {
    "23.976": (Fraction(24000, 1001), 24, False),
    "24": (Fraction(24), 24, False),
    "25": (Fraction(25), 25, False),
    "29.97 DF": (Fraction(30000, 1001), 30, True),
    "29.97 ND": (Fraction(30000, 1001), 30, False),
    "30": (Fraction(30), 30, False),
}
PADRAO = {"ligado": False, "inicio": "01:00:00:00", "fps": "30", "volume_db": -6.0}

SYNC = [0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 1]  # bits 64..79


# ------------------------------------------------------------------ timecode <-> quadros

def tc_para_quadros(tc: str, fps: str) -> int:
    _, nom, df = TAXAS[fps]
    p = [int(x) for x in tc.replace(";", ":").replace(".", ":").split(":")]
    while len(p) < 4:
        p.insert(0, 0)
    h, m, s, f = p[-4:]
    if not (0 <= h < 24 and 0 <= m < 60 and 0 <= s < 60 and 0 <= f < nom):
        raise ValueError("Timecode inválido: " + tc)
    total_min = 60 * h + m
    n = ((h * 3600 + m * 60 + s) * nom) + f
    if df:
        n -= 2 * (total_min - total_min // 10)
    return n


def quadros_para_tc(n: int, fps: str) -> tuple[int, int, int, int]:
    _, nom, df = TAXAS[fps]
    if df:
        por_10min = 17982           # 30*600 − 18
        por_min = 1798              # 30*60 − 2
        d, r = divmod(n, por_10min)
        n += 18 * d + (2 * ((r - 2) // por_min) if r > 2 else 0)
    dia = nom * 86400
    n %= dia
    f = n % nom
    s = (n // nom) % 60
    m = (n // (nom * 60)) % 60
    h = n // (nom * 3600)
    return h, m, s, f


def tc_texto(n: int, fps: str) -> str:
    h, m, s, f = quadros_para_tc(n, fps)
    sep = ";" if TAXAS[fps][2] else ":"
    return f"{h:02d}:{m:02d}:{s:02d}{sep}{f:02d}"


def validar_tc(tc: str, fps: str) -> str:
    """Normaliza (e confere) um timecode digitado: '1:0:0:0' -> '01:00:00:00'."""
    n = tc_para_quadros(tc, fps)
    t = tc_texto(n, fps)
    return t.replace(";", ":")


# ------------------------------------------------------------------ bits de um quadro

def bits_do_quadro(n: int, fps: str) -> np.ndarray:
    _, nom, df = TAXAS[fps]
    h, m, s, f = quadros_para_tc(n, fps)
    b = np.zeros(80, np.int8)

    def put(v, ini, qtd):
        for i in range(qtd):
            b[ini + i] = (v >> i) & 1

    put(f % 10, 0, 4); put(f // 10, 8, 2)
    b[10] = 1 if df else 0
    put(s % 10, 16, 4); put(s // 10, 24, 3)
    put(m % 10, 32, 4); put(m // 10, 40, 3)
    put(h % 10, 48, 4); put(h // 10, 56, 2)
    b[64:80] = SYNC
    # correção de polaridade: número par de zeros no quadro
    pol = 59 if nom == 25 else 27
    b[pol] = 0
    zeros = 80 - int(b.sum())
    if zeros % 2 == 1:
        b[pol] = 1
    return b


def meias_celulas(bits: np.ndarray) -> np.ndarray:
    """Nível (+1/−1) das 160 meias-células, começando com polaridade +1 antes do quadro."""
    out = np.empty(160, np.float32)
    nivel = 1.0
    for i, bit in enumerate(bits):
        nivel = -nivel
        out[2 * i] = nivel
        if bit:
            nivel = -nivel
        out[2 * i + 1] = nivel
    return out


# ------------------------------------------------------------------ gerador

class GeradorLTC:
    def __init__(self, taxa: int, fps: str = "30", inicio: str = "01:00:00:00", amplitude: float = 0.5):
        self.taxa = taxa
        self.amplitude = amplitude
        self.configurar(fps, inicio)

    def configurar(self, fps: str, inicio: str):
        if fps not in TAXAS:
            raise ValueError("fps inválido: " + fps)
        self.fps = fps
        self.fr = TAXAS[fps][0]
        self.q0 = tc_para_quadros(inicio, fps)
        self._cache: dict[int, np.ndarray] = {}

    def _inicio_quadro(self, k: np.ndarray | int):
        # amostra (fracionária) onde o quadro k começa
        return np.asarray(k, np.float64) * (self.taxa * self.fr.denominator / self.fr.numerator)

    def _niveis(self, k: int) -> np.ndarray:
        v = self._cache.get(k)
        if v is None:
            v = meias_celulas(bits_do_quadro(self.q0 + k, self.fps))
            if len(self._cache) > 64:
                self._cache.clear()
            self._cache[k] = v
        return v

    def quadro_em(self, amostra: int) -> int:
        return int(np.floor(amostra * self.fr.numerator / (self.taxa * self.fr.denominator) + 1e-9))

    def tc_em(self, amostra: int) -> str:
        return tc_texto(self.q0 + max(0, self.quadro_em(amostra)), self.fps)

    def gerar(self, inicio: int, n: int) -> np.ndarray:
        """n amostras (mono) a partir da amostra `inicio` da música."""
        if n <= 0:
            return np.zeros(0, np.float32)
        # 1 amostra a mais de cada lado para suavizar a borda sem atraso (filtro simétrico)
        s = np.arange(inicio - 1, inicio + n + 1, dtype=np.float64)
        num, den = self.fr.numerator, self.fr.denominator
        k = np.floor(s * num / (self.taxa * den) + 1e-9).astype(np.int64)
        ini = self._inicio_quadro(k)
        dur = self.taxa * den / num
        meia = np.clip(((s - ini) * 160.0 / dur).astype(np.int64), 0, 159)
        y = np.empty(len(s), np.float32)
        for kk in np.unique(k):
            sel = k == kk
            if kk < 0:
                y[sel] = 0.0
            else:
                y[sel] = self._niveis(int(kk))[meia[sel]]
        y = 0.25 * y[:-2] + 0.5 * y[1:-1] + 0.25 * y[2:]   # subida de ~2 amostras, centrada
        return (y * self.amplitude).astype(np.float32)


def gerar_arquivo(n: int, taxa: int, fps: str, inicio: str, amplitude: float = 0.5) -> np.ndarray:
    g = GeradorLTC(taxa, fps, inicio, amplitude)
    out = np.empty(n, np.float32)
    passo = taxa * 10
    for i in range(0, n, passo):
        out[i:i + passo] = g.gerar(i, min(passo, n - i))
    return out


# ------------------------------------------------------------------ leitor (para os testes)

def decodificar(sinal: np.ndarray, taxa: int, fps: str) -> list[tuple[int, str]]:
    """Decodificador LTC simples: devolve [(amostra onde o quadro começa, 'hh:mm:ss:ff')]."""
    fr = TAXAS[fps][0]
    meia = taxa / float(fr) / 160.0
    x = np.sign(sinal)
    x[x == 0] = 1
    trans = np.nonzero(np.diff(x) != 0)[0] + 1
    if len(trans) < 3:
        return []
    bits, pos = [], []
    i = 0
    while i < len(trans) - 1:
        d = trans[i + 1] - trans[i]
        if d > 1.5 * meia:          # célula inteira = 0
            bits.append(0); pos.append(trans[i]); i += 1
        elif i + 2 < len(trans):    # duas meias = 1
            bits.append(1); pos.append(trans[i]); i += 2
        else:
            break
    out = []
    bits = np.array(bits)
    for j in range(64, len(bits) - 15):
        if list(bits[j:j + 16]) == SYNC and j >= 64:
            q = bits[j - 64:j]

            def get(ini, qtd):
                return int(sum(int(q[ini + t]) << t for t in range(qtd)))
            f = get(0, 4) + 10 * get(8, 2)
            s = get(16, 4) + 10 * get(24, 3)
            m = get(32, 4) + 10 * get(40, 3)
            h = get(48, 4) + 10 * get(56, 2)
            out.append((int(pos[j - 64]), f"{h:02d}:{m:02d}:{s:02d}:{f:02d}"))
    return out
