"""Testes do motor (sem placa de som): fase, nulo, mute/solo, loop, pan."""
import os, sys, tempfile, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from wmsteams import projeto as pj
from wmsteams.player import Motor

ok = falhas = 0
def confere(nome, cond, extra=""):
    global ok, falhas
    if cond: ok += 1; print("OK  ", nome, extra)
    else: falhas += 1; print("FALHA", nome, extra)

def db(v):
    v = np.asarray(v, np.float64); return 20*np.log10(np.sqrt(np.mean(v**2)) + 1e-20)

def projeto_falso(pasta, taxa=48000, seg=6):
    rng = np.random.default_rng(1)
    n = taxa * seg
    trilhas = {k: (rng.standard_normal((n, 2)) * 0.05).astype(np.float32) for k in ["voz", "bateria", "baixo", "outros"]}
    orig = sum(trilhas.values())
    for k, v in trilhas.items(): pj.gravar_wav_float(os.path.join(pasta, k + ".wav"), v, taxa)
    pj.gravar_wav_float(os.path.join(pasta, "pad.wav"), np.zeros((n, 2), np.float32), taxa)
    pj.gravar_wav_float(os.path.join(pasta, "original.wav"), orig, taxa)
    p = {"pasta": pasta, "trilhas": list(trilhas) + ["pad"], "taxa": taxa, "amostras": n, "mixer": {}}
    pj.salvar(p); return p, trilhas, orig

with tempfile.TemporaryDirectory() as d:
    p, tr, orig = projeto_falso(d)
    m, sr = pj.abrir_wav_float(os.path.join(d, "voz.wav"))
    confere("WAV float ida e volta exato", np.array_equal(np.asarray(m), tr["voz"]))
    confere("teste de nulo do projeto", pj.conferir_fase(p) < -140, f"{pj.conferir_fase(p):.1f} dB")

    mo = Motor(); mo.carregar(p); mo.tocando = True
    # blocos de tamanhos irregulares, como uma placa de som faria
    pedacos = []; rng = np.random.default_rng(3)
    while mo.tocando:
        pedacos.append(mo.renderizar(int(rng.integers(64, 2048))).copy())
    tocado = np.concatenate(pedacos)[:len(orig)]
    # primeira rampa de entrada (ganho sobe de 0 no 1º bloco): compara depois dela
    k = len(pedacos[0])
    confere("mix tocado = original (nulo)", db(tocado[k:] - orig[k:]) - db(orig) < -120, f"{db(tocado[k:]-orig[k:]) - db(orig):.1f} dB")
    confere("nenhuma amostra deslocada", np.argmax(np.correlate(tocado[k:k+4000,0], orig[k:k+4000,0], 'full')) == 3999)
    confere("termina sozinho no fim", not mo.tocando and mo.pos == mo.n)

    # solo da voz
    mo.parar(); mo.trilha("voz").solo = True; mo.tocando = True
    mo.renderizar(512); y = mo.renderizar(4096)
    confere("solo: só a voz", db(y - tr["voz"][512:512+4096]) < -120)
    mo.trilha("voz").solo = False; mo.trilha("voz").mute = True
    mo.renderizar(512); a = mo.pos; y = mo.renderizar(4096)
    esperado = orig[a:a+4096] - tr["voz"][a:a+4096]
    confere("mute: tudo menos a voz", db(y - esperado) < -120)
    mo.trilha("voz").mute = False

    # pan todo à esquerda: direita zera, esquerda +3 dB
    for t in mo.trilhas: t.mute = t.chave != "baixo"
    mo.trilha("baixo").pan = -1; mo.renderizar(512); a = mo.pos; y = mo.renderizar(2048)
    confere("pan esquerda", db(y[:, 1]) < -200 and abs(db(y[:, 0]) - db(tr["baixo"][a:a+2048, 0] * np.sqrt(2))) < 0.01)
    mo.trilha("baixo").pan = 0
    for t in mo.trilhas: t.mute = False

    # loop A-B: depois do fim volta para o início, sem pular amostra
    mo.ir_para(1.0); mo.loop = (int(1.0*sr), int(1.5*sr)); mo.tocando = True
    y = mo.renderizar(int(0.75*sr))
    ini = int(1.0*sr); meio = int(0.5*sr)
    confere("loop A-B emenda certo", db(y[meio+64:meio+2000] - orig[ini+64:ini+2000]) < -100)
    mo.loop = None

    # tempo de CPU por bloco de 512 com 5 trilhas
    mo.ir_para(0); mo.tocando = True
    t0 = time.perf_counter()
    for _ in range(400): mo.renderizar(512)
    ms = (time.perf_counter() - t0) / 400 * 1000
    confere("CPU por bloco < 2 ms", ms < 2, f"{ms:.3f} ms (o bloco dura {512/sr*1000:.1f} ms)")
    mo.fechar()

print(f"\n{ok}/{ok+falhas} testes OK")
sys.exit(1 if falhas else 0)
