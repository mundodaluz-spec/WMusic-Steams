"""WMusic Steams — separa a música em stems, escreve a letra, cria o pad e toca tudo em sincronia.

Uso:
  WMusic Steams                         abre o programa
  WMusic Steams --processar ARQ [--saida PASTA] [--resultado R.json] [--rapido] [--sem-letra]
                [--modelo NOME] [--idioma pt]
                                        processa sem janela (autoteste)
  WMusic Steams --captura PROJETO IMG.png
                                        abre a janela, carrega o projeto e salva uma captura
  WMusic Steams --licenca               mostra a licença e o código do computador
  WMusic Steams --ativar SERIAL         ativa um serial
"""
import argparse
import json
import multiprocessing
import os
import sys


_LOG = None


def _say(txt):  # noqa: E302
    if _LOG:
        try:
            with open(_LOG, "a", encoding="utf-8") as f:
                f.write(txt + "\n")
        except Exception:
            pass
    if sys.stdout is not None:
        try:
            print(txt, flush=True)
        except Exception:
            pass


def cli(argv) -> int:
    ap = argparse.ArgumentParser(prog="wmusic-steams")
    ap.add_argument("--processar")
    ap.add_argument("--licenca", action="store_true", help="mostra a licença e o código do computador")
    ap.add_argument("--ativar", metavar="SERIAL")
    ap.add_argument("--saida")
    ap.add_argument("--resultado")
    ap.add_argument("--rapido", action="store_true")
    ap.add_argument("--sem-letra", action="store_true")
    ap.add_argument("--modelo")
    ap.add_argument("--idioma", default="pt")
    ap.add_argument("--sem-backs", action="store_true")
    ap.add_argument("--sem-sopros", action="store_true")
    ap.add_argument("--bateria-pecas", action="store_true")
    ap.add_argument("--captura", nargs=2, metavar=("PROJETO", "IMAGEM"))
    ap.add_argument("--log")
    a = ap.parse_args(argv)
    global _LOG
    _LOG = a.log
    if _LOG:
        import faulthandler
        _fh = open(_LOG + ".pilha", "w")
        faulthandler.dump_traceback_later(600, repeat=False, file=_fh)  # mostra onde travou

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

    if a.licenca or a.ativar:
        from wmsteams import licenca as lc
        if a.ativar:
            try:
                lc.ativar(a.ativar)
            except lc.ErroSerial as e:
                _say("ERRO " + str(e)); return 4
        _say(f"{lc.texto_estado()}  ·  código do computador: {lc.codigo_computador()}")
        return 0

    from wmsteams import projeto as pj
    resultado = {}
    try:
        p = pj.processar(a.processar, qualidade="rapida" if a.rapido else "alta", idioma=a.idioma,
                         fazer_letra=not a.sem_letra, modelo=a.modelo, pasta_destino=a.saida,
                         backs=not a.sem_backs, sopros=not a.sem_sopros, bateria_pecas=a.bateria_pecas,
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


def _saidas_seguras():
    """No Windows, o programa aberto pelo ícone não tem console: sys.stdout e sys.stderr
    ficam None e qualquer barra de progresso/print das bibliotecas quebra com
    "'NoneType' object has no attribute 'write'". Manda tudo para um arquivo de log."""
    if sys.stdout is not None and sys.stderr is not None:
        return
    try:
        if sys.platform == "win32":
            pasta = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "WMusic", "WMusic Steams")
        elif sys.platform == "darwin":
            pasta = os.path.expanduser("~/Library/Application Support/WMusic/WMusic Steams")
        else:
            pasta = os.path.expanduser("~/.local/share/WMusic/WMusic Steams")
        os.makedirs(pasta, exist_ok=True)
        log = open(os.path.join(pasta, "registro.log"), "a", encoding="utf-8", buffering=1)
    except Exception:
        log = open(os.devnull, "w", encoding="utf-8")
    if sys.stdout is None:
        sys.stdout = log
    if sys.stderr is None:
        sys.stderr = log
    try:
        import faulthandler
        faulthandler.enable(file=log)
    except Exception:
        pass


def main():
    multiprocessing.freeze_support()
    _saidas_seguras()
    if len(sys.argv) > 1 and sys.argv[1].startswith("--"):
        sys.exit(cli(sys.argv[1:]))
    from wmsteams.ui import main as ui_main
    sys.exit(ui_main())


if __name__ == "__main__":
    main()
