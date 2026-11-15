"""Abre a janela sem tela (offscreen), carrega um projeto e salva uma captura."""
import os, sys, json, shutil
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import numpy as np
from wmsteams import projeto as pj

def projeto_demo(base, destino):
    """Projeto de 6 stems feito a partir de um projeto real de 2 stems (só para a captura)."""
    if os.path.exists(destino): shutil.rmtree(destino)
    os.makedirs(destino)
    p = pj.carregar(base)
    voz, sr = pj.abrir_wav_float(os.path.join(base, "voz.wav"))
    ins, _ = pj.abrir_wav_float(os.path.join(base, "instrumental.wav"))
    ins = np.asarray(ins)
    partes = {"voz": np.asarray(voz), "bateria": ins * 0.3, "baixo": ins * 0.25, "guitarra": ins * 0.15, "teclas": ins * 0.2, "outros": ins * 0.1}
    for k, v in partes.items(): pj.gravar_wav_float(os.path.join(destino, k + ".wav"), v.astype(np.float32), sr)
    for k in ("pad", "original"): shutil.copy(os.path.join(base, k + ".wav"), os.path.join(destino, k + ".wav"))
    def linha(t0, txt):
        ws = txt.split(); d = 2.2 / len(ws)
        pal = [{"w": w, "t0": round(t0 + i*d, 2), "t1": round(t0 + (i+1)*d, 2)} for i, w in enumerate(ws)]
        return {"t0": t0, "t1": t0 + 2.2, "texto": txt, "palavras": pal}
    p.update({"pasta": destino, "titulo": "Exemplo - Ensaio", "trilhas": list(partes) + ["pad"],
              "letra": {"idioma": "pt", "linhas": [linha(1.0, "Eu vou cantar de novo"), linha(3.6, "a tua graça me alcançou"),
                                                   linha(6.2, "e o teu amor me sustentou"), linha(8.8, "aleluia, aleluia")]},
              "aviso_letra": None})
    pj.salvar(p); return p

if __name__ == "__main__":
    base, saida = sys.argv[1], sys.argv[2]
    p = projeto_demo(base, "/tmp/proj_demo")
    from PySide6.QtWidgets import QApplication
    from wmsteams import ui
    app = QApplication(sys.argv); app.setStyleSheet(ui.ESTILO)
    j = ui.Janela(); j.resize(1280, 860); j.show()
    j.abrir_projeto(p)
    j.faixas[0].s.setChecked(False); j.faixas[3].m.setChecked(True); j.faixas[6].fader.setValue(-60)
    j.motor.ir_para(4.5); j.onda.loop_s = (2.4, 7.2)
    for t in j.motor.trilhas: t.pico = 0.3 + 0.5 * np.random.rand()
    j.motor.tocando = False
    j.tique(); app.processEvents()
    j.grab().save(saida); print("salvo", saida)
