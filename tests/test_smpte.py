"""SMPTE LTC: sequência certa em todas as taxas, quadro começando na amostra exata,
mesmo sinal tocando em blocos ou de uma vez, drop-frame certo e polaridade fixa."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from wmsteams import smpte as s

ok = falhas = 0
def confere(nome, cond, extra=""):
    global ok, falhas
    if cond: ok += 1; print("OK  ", nome, extra)
    else: falhas += 1; print("FALHA", nome, extra)

for sr in (44100, 48000):
    for fps in s.TAXAS:
        inicio = "00:59:58:00"
        q0 = s.tc_para_quadros(inicio, fps)
        inteiro = s.gerar_arquivo(sr * 4, sr, fps, inicio)
        g = s.GeradorLTC(sr, fps, inicio)
        pedacos, p, rng = [], 0, np.random.default_rng(1)
        while p < len(inteiro):
            k = int(rng.integers(32, 3000)); pedacos.append(g.gerar(p, min(k, len(inteiro) - p))); p += k
        igual = np.array_equal(np.concatenate(pedacos), inteiro)
        dec = s.decodificar(inteiro, sr, fps)
        fr = float(s.TAXAS[fps][0])
        # o leitor perde o 1º bit do arquivo; a partir do 2º quadro tudo tem que bater
        idx = [s.tc_para_quadros(t, fps) - q0 for _, t in dec]
        seq = idx == list(range(idx[0], idx[0] + len(idx)))
        erro = max(abs(a - i * sr / fr) for a, i in zip([a for a, _ in dec], idx))
        cruza = any(t.startswith("01:00:00") for _, t in dec)
        confere(f"{fps:>8} @ {sr}", igual and seq and erro <= 1.0 and cruza and len(dec) >= int(4 * fr) - 2,
                f"quadros={len(dec)} 1º={dec[0][1]} último={dec[-1][1]} erro início={erro:.2f} amostra")

# drop-frame: 00:00:59;29 -> 00:01:00;02 (pula ;00 e ;01), mas não no minuto 10
n = s.tc_para_quadros("00:00:59:29", "29.97 DF")
confere("DF pula :00 e :01", s.tc_texto(n + 1, "29.97 DF") == "00:01:00;02", s.tc_texto(n + 1, "29.97 DF"))
n = s.tc_para_quadros("00:09:59:29", "29.97 DF")
confere("DF não pula no minuto 10", s.tc_texto(n + 1, "29.97 DF") == "00:10:00;00", s.tc_texto(n + 1, "29.97 DF"))
# uma hora em DF = 107892 quadros (≈ 3600 s reais)
confere("DF 1 hora = 107892 quadros", s.tc_para_quadros("01:00:00:00", "29.97 DF") == 107892)
# ida e volta de todos os quadros de 12 minutos
okk = all(s.tc_para_quadros(s.tc_texto(i, "29.97 DF").replace(";", ":"), "29.97 DF") == i for i in range(0, 30 * 60 * 12))
confere("DF ida e volta 12 min", okk)
# polaridade: todo quadro termina com o mesmo nível em que começou
pol = all(s.meias_celulas(s.bits_do_quadro(i, f))[-1] == 1.0 for f in s.TAXAS for i in range(0, 3000, 7))
confere("polaridade fixa por quadro (bit de correção)", pol)
# palavra de sincronismo e bit de drop-frame
b = s.bits_do_quadro(0, "29.97 DF")
confere("sync 0x3FFD e flag DF", list(b[64:80]) == s.SYNC and b[10] == 1)
try:
    s.validar_tc("25:00:00:00", "30"); confere("hora 25 recusada", False)
except ValueError:
    confere("hora 25 recusada", True)
try:
    s.validar_tc("00:00:00:25", "25"); confere("quadro 25 em 25 fps recusado", False)
except ValueError:
    confere("quadro 25 em 25 fps recusado", True)
confere("normaliza '1:0:0:0'", s.validar_tc("1:0:0:0", "30") == "01:00:00:00")

print(f"\n{ok}/{ok+falhas} testes OK")
sys.exit(1 if falhas else 0)
