"""Confere o resultado do autoteste do programa compilado (CI)."""
import json, sys

r = json.load(open(sys.argv[1], encoding="utf-8"))
print(json.dumps(r, ensure_ascii=False, indent=1))
erros = []
if not r.get("ok"):
    erros.append("processamento falhou: " + str(r.get("erro")))
else:
    if r["nulo_conferido_db"] > -90:
        erros.append(f"soma dos stems não bate com o original ({r['nulo_conferido_db']} dB)")
    esperado = {"voz", "baixo", "outros", "pad"}
    tem_bateria = "bateria" in r["trilhas"] or any(k in r["trilhas"] for k in ("bumbo", "caixa", "pratos"))
    if not tem_bateria:
        erros.append("sem bateria")
    if not esperado.issubset(r["trilhas"]):
        erros.append(f"faltam trilhas: {esperado - set(r['trilhas'])}")
    ac = r["acordes"]
    if not {"C", "G", "Am", "F"} & set(ac):
        erros.append(f"acordes estranhos: {ac}")
    if len(sys.argv) > 2 and sys.argv[2] == "--com-letra":
        if not r["letra"]:
            erros.append("letra vazia (aviso: %s)" % r.get("aviso_letra"))
print("\n".join("ERRO " + e for e in erros) or "TUDO CERTO")
sys.exit(1 if erros else 0)
