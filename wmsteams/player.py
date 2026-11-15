"""Motor de reprodução multitrack.

UM relógio só: todas as trilhas são lidas na mesma posição, dentro do mesmo
callback de áudio, amostra por amostra. Não existe um player por trilha, então
não há como uma trilha escorregar em relação à outra. Mute, solo, volume e pan
mudam só o ganho (com rampa curta, sem clique), nunca o tempo.
"""
from __future__ import annotations

import os
import threading

import numpy as np

from .projeto import abrir_wav_float


class Trilha:
    def __init__(self, chave: str, dados: np.ndarray):
        self.chave = chave
        self.dados = dados
        self.volume = 1.0       # linear
        self.pan = 0.0          # -1..1
        self.mute = False
        self.solo = False
        self.saida = 0          # par de saídas (0 = 1-2, 1 = 3-4, ...)
        self._ganho_atual = np.zeros(2, np.float32)
        self.pico = 0.0


class TrilhaSMPTE(Trilha):
    """Canal de timecode: gerado na hora pela posição; não entra no solo nem no master."""

    def __init__(self, taxa: int, cfg: dict):
        super().__init__("smpte", None)
        from .smpte import GeradorLTC
        self.gerador = GeradorLTC(taxa, cfg.get("fps", "30"), cfg.get("inicio", "01:00:00:00"))
        self.cfg = dict(cfg)
        self.volume = 10 ** (cfg.get("volume_db", -6.0) / 20) / 0.5  # o gerador já sai a −6 dBFS
        self.mute = bool(cfg.get("mute", False))
        self.saida = int(cfg.get("saida", 0))


class Motor:
    def __init__(self):
        self.trilhas: list[Trilha] = []
        self.smpte: TrilhaSMPTE | None = None
        self.taxa = 48000
        self.n = 0
        self.pos = 0
        self.tocando = False
        self.loop: tuple[int, int] | None = None
        self.master = 1.0
        self.canais_saida = 2
        self._trava = threading.Lock()
        self._stream = None
        self.dispositivo = None
        self._prefetch_parar = threading.Event()
        self._prefetch: threading.Thread | None = None

    # ------------------------------------------------------------ carga
    def carregar(self, projeto: dict, incluir_original: bool = False) -> None:
        self.parar()
        self.fechar_stream()  # a taxa pode mudar de uma música para outra
        trilhas = []
        taxa = None
        chaves = list(projeto["trilhas"]) + (["original"] if incluir_original else [])
        for k in chaves:
            mm, sr = abrir_wav_float(os.path.join(projeto["pasta"], k + ".wav"))
            taxa = taxa or sr
            if sr != taxa:
                raise RuntimeError("Trilhas com taxas diferentes no projeto.")
            trilhas.append(Trilha(k, mm))
        n = min(len(t.dados) for t in trilhas)
        with self._trava:
            self.trilhas = trilhas
            self.taxa = taxa
            self.n = n
            self.pos = 0
            self.loop = None
        mixer = projeto.get("mixer", {})
        for t in self.trilhas:
            m = mixer.get(t.chave)
            if m:
                t.volume, t.pan = m.get("volume", 1.0), m.get("pan", 0.0)
                t.mute, t.solo, t.saida = m.get("mute", False), m.get("solo", False), m.get("saida", 0)
        if "original" in [t.chave for t in self.trilhas]:
            self.trilha("original").mute = True
        self.configurar_smpte(projeto.get("smpte"))
        self._iniciar_prefetch()

    def configurar_smpte(self, cfg: dict | None) -> None:
        """Liga/desliga ou muda o timecode (início e fps) sem parar a música."""
        with self._trava:
            if cfg and cfg.get("ligado"):
                self.smpte = TrilhaSMPTE(self.taxa, cfg)
            else:
                self.smpte = None

    def tc_atual(self) -> str | None:
        s = self.smpte
        return s.gerador.tc_em(self.pos) if s else None

    def descarregar(self) -> None:
        """Solta os arquivos (no Windows um arquivo aberto em memmap não pode ser trocado nem apagado)."""
        self.parar()
        self.fechar_stream()
        self._prefetch_parar.set()
        if self._prefetch:
            self._prefetch.join(timeout=1)
        with self._trava:
            for t in self.trilhas:
                mm = getattr(t.dados, "_mmap", None)
                t.dados = None
                try:
                    if mm is not None:
                        mm.close()
                except Exception:
                    pass
            self.trilhas = []
            self.n = 0
        import gc
        gc.collect()

    def trilha(self, chave: str) -> Trilha | None:
        if chave == "smpte":
            return self.smpte
        return next((t for t in self.trilhas if t.chave == chave), None)

    def estado_mixer(self) -> dict:
        return {t.chave: {"volume": t.volume, "pan": t.pan, "mute": t.mute, "solo": t.solo,
                          "saida": t.saida} for t in self.trilhas if t.chave != "original"}

    def estado_smpte(self) -> dict | None:
        s = self.smpte
        if not s:
            return None
        import math
        d = dict(s.cfg)
        d.update({"ligado": True, "mute": s.mute, "saida": s.saida,
                  "volume_db": round(20 * math.log10(max(1e-6, s.volume * 0.5)), 2)})
        return d

    # ------------------------------------------------------------ mixagem
    def _ganhos_alvo(self) -> list[np.ndarray]:
        algum_solo = any(t.solo for t in self.trilhas)
        out = []
        for t in self.trilhas:
            ligado = (t.solo if algum_solo else not t.mute)
            if not ligado:
                out.append(np.zeros(2, np.float32))
                continue
            ang = (t.pan + 1) * np.pi / 4  # pan de potência constante, 0 dB no centro
            g = np.array([np.cos(ang), np.sin(ang)], np.float32) * np.sqrt(2) * t.volume * self.master
            out.append(g.astype(np.float32))
        return out

    def renderizar(self, frames: int, saida: np.ndarray | None = None) -> np.ndarray:
        """Mistura `frames` amostras a partir de self.pos (avança a posição)."""
        canais = self.canais_saida if saida is None else saida.shape[1]
        out = saida if saida is not None else np.zeros((frames, canais), np.float32)
        out[:] = 0
        if not self.tocando or not self.trilhas:
            return out
        with self._trava:
            escrito = 0
            alvos = self._ganhos_alvo()
            while escrito < frames:
                fim = self.loop[1] if self.loop else self.n
                ini_loop = self.loop[0] if self.loop else None
                k = min(frames - escrito, fim - self.pos)
                if k <= 0:
                    if ini_loop is not None:
                        self.pos = ini_loop
                        continue
                    self.tocando = False
                    break
                rampa = np.linspace(0, 1, k, endpoint=False, dtype=np.float32)[:, None] if k > 1 else np.ones((k, 1), np.float32)
                for t, alvo in zip(self.trilhas, alvos):
                    g0 = t._ganho_atual
                    if not np.any(alvo) and not np.any(g0):
                        t.pico *= 0.9
                        continue
                    bloco = np.asarray(t.dados[self.pos:self.pos + k], dtype=np.float32)
                    if bloco.shape[1] == 1:
                        bloco = np.repeat(bloco, 2, axis=1)
                    if np.array_equal(g0, alvo):
                        y = bloco[:, :2] * alvo
                    else:
                        y = bloco[:, :2] * (g0 + (alvo - g0) * rampa)
                        t._ganho_atual = alvo
                    t.pico = max(t.pico * 0.9, float(np.max(np.abs(y))) if len(y) else 0.0)
                    c = 2 * t.saida
                    if c + 2 > canais:
                        c = 0
                    out[escrito:escrito + k, c:c + 2] += y
                sm = self.smpte
                if sm is not None:
                    alvo = 0.0 if sm.mute else sm.volume
                    if alvo > 0 or sm._ganho_atual[0] > 0:
                        ltc = sm.gerador.gerar(self.pos, k)
                        g0 = float(sm._ganho_atual[0])
                        ganho = g0 + (alvo - g0) * rampa[:, 0] if g0 != alvo else alvo
                        ltc = ltc * ganho
                        sm._ganho_atual = np.array([alvo, alvo], np.float32)
                        sm.pico = max(sm.pico * 0.9, float(np.max(np.abs(ltc))) if k else 0.0)
                        c = 2 * sm.saida
                        if c + 2 > canais:
                            c = 0
                        out[escrito:escrito + k, c] += ltc
                        out[escrito:escrito + k, c + 1] += ltc
                    else:
                        sm.pico *= 0.9
                self.pos += k
                escrito += k
        return out

    # ------------------------------------------------------------ transporte
    def tocar(self):
        if not self.trilhas:
            return
        if self.pos >= self.n:
            self.pos = 0
        self._abrir_stream()
        self.tocando = True

    def pausar(self):
        self.tocando = False

    def parar(self):
        self.tocando = False
        self.pos = 0

    def ir_para(self, segundos: float):
        with self._trava:
            self.pos = int(max(0, min(self.n - 1, round(segundos * self.taxa)))) if self.n else 0
        for t in self.trilhas:   # sem rampa saindo do nada após salto: entra suave
            t._ganho_atual = np.zeros(2, np.float32)
        if self.smpte is not None:  # o timecode pula seco (leitor de LTC prefere assim)
            self.smpte._ganho_atual = np.full(2, 0.0 if self.smpte.mute else self.smpte.volume, np.float32)

    @property
    def segundos(self) -> float:
        return self.pos / self.taxa if self.taxa else 0.0

    # ------------------------------------------------------------ dispositivo
    @staticmethod
    def dispositivos() -> list[dict]:
        try:
            import sounddevice as sd
            out = []
            for i, d in enumerate(sd.query_devices()):
                if d["max_output_channels"] >= 2:
                    api = sd.query_hostapis(d["hostapi"])["name"]
                    out.append({"indice": i, "nome": f'{d["name"]} ({api})', "canais": d["max_output_channels"]})
            return out
        except Exception:
            return []

    def escolher_dispositivo(self, indice: int | None):
        self.fechar_stream()
        self.dispositivo = indice

    def _abrir_stream(self):
        if self._stream is not None:
            return
        import sounddevice as sd
        info = sd.query_devices(self.dispositivo, "output")
        self.canais_saida = max(2, min(int(info["max_output_channels"]), 16))

        def cb(outdata, frames, tempo, status):
            self.renderizar(frames, outdata)

        self._stream = sd.OutputStream(
            device=self.dispositivo, samplerate=self.taxa, channels=self.canais_saida,
            dtype="float32", blocksize=512, latency="low", callback=cb)
        self._stream.start()

    def fechar_stream(self):
        s, self._stream = self._stream, None
        if s is not None:
            try:
                s.stop()
                s.close()
            except Exception:
                pass

    # ------------------------------------------------------------ leitura antecipada
    def _iniciar_prefetch(self):
        """Mantém ~3 s à frente já na memória (o disco nunca atrasa o callback)."""
        self._prefetch_parar.set()
        if self._prefetch:
            self._prefetch.join(timeout=1)
        self._prefetch_parar = threading.Event()
        parar = self._prefetch_parar

        def loop():
            ultimo = -1
            while not parar.wait(0.25):
                ini = self.pos
                if ini == ultimo:
                    continue
                ultimo = ini
                fim = min(self.n, ini + 3 * self.taxa)
                for t in list(self.trilhas):
                    try:
                        _ = float(t.dados[ini:fim:256, 0].sum())  # toca as páginas
                    except Exception:
                        pass

        self._prefetch = threading.Thread(target=loop, daemon=True)
        self._prefetch.start()

    def fechar(self):
        self.descarregar()
