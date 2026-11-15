"""Leitura de MP3, WAV, FLAC, M4A, MP4, MOV etc. sem deslocar o tempo.

Regras para não defasar:
- decodifica pelo libavformat (PyAV), que aplica a lista de edição do MP4/MOV
  e o cabeçalho LAME/Xing do MP3: o "silêncio de codificador" (priming) do
  AAC/MP3 é descartado e a amostra 0 do resultado é a amostra 0 da música;
- não reamostra: devolve na taxa original do arquivo;
- conta as amostras pelo PTS do primeiro quadro, para que um fluxo que comece
  depois de 0 (vídeo com áudio atrasado) mantenha o atraso real.
"""
from __future__ import annotations

import numpy as np


def ler_audio(caminho: str) -> tuple[np.ndarray, int, dict]:
    """Devolve (audio float32 [amostras, 2], taxa, info)."""
    import av

    with av.open(caminho) as cont:
        fluxos = [s for s in cont.streams if s.type == "audio"]
        if not fluxos:
            raise ValueError("O arquivo não tem áudio.")
        st = fluxos[0]
        taxa = st.codec_context.sample_rate or st.rate
        canais = st.codec_context.channels
        info = {
            "codec": st.codec_context.name,
            "taxa": int(taxa),
            "canais_originais": int(canais),
            "inicio_s": 0.0,
        }
        # mesma taxa, só converte para float planar estéreo (sem reamostrar)
        conv = av.AudioResampler(format="fltp", layout="stereo", rate=taxa)
        blocos: list[np.ndarray] = []
        primeiro_pts = None
        videos = [v for v in cont.streams if v.type == "video" and v.start_time is not None]
        inicio_video = min((float(v.start_time * v.time_base) for v in videos), default=None)
        for pacote in cont.demux(st):
            for quadro in pacote.decode():
                if primeiro_pts is None and quadro.pts is not None:
                    primeiro_pts = float(quadro.pts * quadro.time_base)
                for q in conv.resample(quadro):
                    blocos.append(q.to_ndarray())
        for q in conv.resample(None):
            blocos.append(q.to_ndarray())

    if not blocos:
        raise ValueError("Não consegui decodificar o áudio.")
    audio = np.concatenate(blocos, axis=1).T.astype(np.float32, copy=False)

    # Em vídeo, se o áudio começa depois da imagem, mantém esse atraso real.
    # (No MP3 o PTS inicial é só o priming já descartado: não conta.)
    inicio = 0.0
    if inicio_video is not None and primeiro_pts is not None:
        inicio = max(0.0, primeiro_pts - inicio_video)
    if inicio > 0.0005:
        info["inicio_s"] = inicio
        pad = int(round(inicio * taxa))
        audio = np.concatenate([np.zeros((pad, 2), np.float32), audio])
    return np.ascontiguousarray(audio), int(taxa), info
