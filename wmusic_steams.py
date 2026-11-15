"""WMusic Steams — separa a música em stems, escreve a letra, cria o pad e toca tudo em sincronia.

Uso:
  WMusic Steams                         abre o programa
  WMusic Steams --processar ARQ [--saida PASTA] [--resultado R.json] [--rapido] [--sem-letra]
                [--modelo NOME] [--idioma pt]
                                        processa sem janela (autoteste)
  WMusic Steams --captura PROJETO IMG.png
                                        abre a janela, carrega o projeto e salva uma captura
"""
import argparse
import json
import multiprocessing
import os
import sys


def _say(txt):
    if sys.stdout is not None:
        try:
            print(txt, flush=True)
        except Exception:
            pass


def cli(argv) -> int:
    ap = argparse.ArgumentParser(prog="wmusic-steams")
    ap.add_argument("--processar")
    ap.add_argument("--saida")
    ap.add_argument("--resultado")
    ap.add_argument("--rapido", action="store_true")
    ap.add_argument("--sem-letra", action="store_true")
    ap.add_argument("--modelo")
    ap.add_argument("--idioma", default="pt")
    ap.add_argument("--captura", nargs=2, metavar=("PROJETO", "IMAGEM"))
    a = ap.parse_args(argv)

    if a.captura:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from wmsteams import ui, projeto as pj
        app = QApplication([sys.argv[0]])
        ui.preparar_app(app)
        j = ui.Janela(); j.resize(1530, 1030); j.show()
        j.abrir_projeto(pj.carregar(a.captura[0]))
        j.motor.ir_para(min(5.0, j.projeto["duracao"] / 2)); j.tique(); app.processEvents()
        ok = j.grab().save(a.captura[1])
        _say(f"CAPTURA {'OK' if ok else 'FALHOU'} {a.captura[1]}")
        return 0 if ok else 3

    from wmsteams import projeto as pj
    resultado = {}
    try:
        p = pj.processar(a.processar, qualidade="rapida" if a.rapido else "alta", idioma=a.idioma,
                         fazer_letra=not a.sem_letra, modelo=a.modelo, pasta_destino=a.saida,
                         progresso=lambda m, f: _say(f"PROGRESSO {int(f*100):3d} {m}"))
        nulo = pj.conferir_fase(p)
        resultado = {"ok": nulo < -90, "pasta": p["pasta"], "trilhas": p["trilhas"], "tom": p["tom"],
                     "acordes": [c["nome"] for c in p["acordes"]][:24],
                     "letra": [l["texto"] for l in p["letra"]["linhas"]],
                     "relatorio": p["relatorio"], "nulo_conferido_db": round(nulo, 1),
                     "aviso_letra": p.get("aviso_letra"), "segundos": p["segundos_processamento"]}
    except Exception as e:
        import traceback
        resultado = {"ok": False, "erro": str(e), "traceback": traceback.format_exc()}
    txt = json.dumps(resultado, ensure_ascii=False, indent=1)
    _say("RESUMO " + txt)
    if a.resultado:
        with open(a.resultado, "w", encoding="utf-8") as f:
            f.write(txt)
    return 0 if resultado.get("ok") else 2


def main():
    multiprocessing.freeze_support()
    if len(sys.argv) > 1 and sys.argv[1].startswith("--"):
        sys.exit(cli(sys.argv[1:]))
    from wmsteams.ui import main as ui_main
    sys.exit(ui_main())


if __name__ == "__main__":
    main()
