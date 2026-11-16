"""Licença: serial assinado, preso ao computador, beta com validade, teste grátis."""
import datetime as dt
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from wmsteams import licenca as lc, ed25519_puro as ed  # noqa: E402

SEED = bytes(range(32))          # chave de TESTE (a pública é trocada abaixo)
PUB_REAL = lc.PUBLICA
ok = falhas = 0


def caso(nome, cond):
    global ok, falhas
    print(("OK   " if cond else "FALHA") + " " + nome)
    ok += bool(cond); falhas += not cond


def erro(fn):
    try:
        fn(); return ""
    except lc.ErroSerial as e:
        return str(e)


def main():
    tmp = tempfile.mkdtemp()
    lc.PASTAS_TESTE = [os.path.join(tmp, "a"), os.path.join(tmp, "b")]
    lc.MAQUINA_TESTE = "maquina-do-cliente"
    lc.PUBLICA = ed.publica(SEED)
    cod = lc.codigo_computador()
    caso("código do computador tem 8 caracteres", len(cod) == 9 and cod[4] == "-")

    # teste grátis
    e = lc.estado()
    caso("começa em teste com 3 músicas", e["tipo"] == "teste" and e["restantes"] == 3)
    for _ in range(3):
        caso("pode separar no teste", lc.pode_separar()[0]); lc.registrar_separacao()
    pode, msg = lc.pode_separar()
    caso("depois de 3, bloqueia e mostra o código", not pode and cod in msg)
    os.remove(os.path.join(lc.PASTAS_TESTE[0], "licenca.json"))
    caso("apagar um arquivo não zera o teste", not lc.pode_separar()[0])
    arq = os.path.join(lc.PASTAS_TESTE[1], ".wmusic-steams.dat")
    txt = open(arq).read().replace('"usadas": 3', '"usadas": 0'); open(arq, "w").write(txt)
    caso("mexer no arquivo encerra o teste", not lc.pode_separar()[0])

    # venda
    serial, ident = lc.montar(SEED, "João da Silva", lc.VENDA, codigo=cod)
    caso("serial começa com WMST", serial.startswith("WMST-"))
    lic = lc.ler(serial)
    caso("lê nome com acento", lic["nome"] == "João da Silva" and lic["tipo"] == "venda" and lic["id"] == ident)
    caso("aceita minúsculas, espaços e quebras", lc.ler("  " + serial.lower().replace("-", " ")[:40] + "\n" + serial.lower()[40:])["id"] == ident)
    adulterado = serial[:-3] + ("A" if serial[-3] != "A" else "B") + serial[-2:]
    caso("serial adulterado é recusado", "inválido" in erro(lambda: lc.ler(adulterado)))
    caso("serial cortado é recusado", erro(lambda: lc.ler(serial[:60])) != "")
    e = lc.ativar(serial)
    caso("ativa e libera a separação", e["tipo"] == "venda" and lc.pode_separar()[0])
    caso("texto do estado", lc.texto_estado() == "Licenciado para João da Silva")

    lc.MAQUINA_TESTE = "outro-computador"
    caso("em outro computador o serial não vale", "outro computador" in erro(lambda: lc.ler(serial)))
    caso("e o app volta para o teste (acabado)", lc.estado()["tipo"] == "teste" and not lc.pode_separar()[0])
    lc.MAQUINA_TESTE = "maquina-do-cliente"
    caso("de volta no computador certo, vale", lc.estado()["tipo"] == "venda")

    caso("venda sem código é recusada no gerador", "código" in erro(lambda: lc.montar(SEED, "X", lc.VENDA)))
    caso("código errado é recusado no gerador", erro(lambda: lc.montar(SEED, "X", lc.VENDA, codigo="AB12")) != "")

    lc.REVOGADOS.add(ident)
    caso("serial cancelado é recusado", "cancelado" in erro(lambda: lc.ler(serial)))
    lc.REVOGADOS.clear()

    # beta
    hoje = dt.date.today()
    beta, _ = lc.montar(SEED, "Testador 1", lc.BETA, validade=hoje + dt.timedelta(days=30))
    caso("beta sem computador ativa em qualquer máquina", lc.ativar(beta)["tipo"] == "beta")
    caso("texto do beta tem a validade", "BETA" in lc.texto_estado() and (hoje + dt.timedelta(days=30)).strftime("%d/%m/%Y") in lc.texto_estado())
    vencido, _ = lc.montar(SEED, "Testador 2", lc.BETA, validade=hoje - dt.timedelta(days=1),
                           hoje=hoje - dt.timedelta(days=40))
    caso("beta vencido não ativa", "venceu" in erro(lambda: lc.ativar(vencido)))
    beta_preso, _ = lc.montar(SEED, "Testador 3", lc.BETA, codigo=cod, validade=hoje + dt.timedelta(days=10))
    caso("beta preso ao computador", lc.ler(beta_preso)["preso"])
    caso("beta sem validade é recusado no gerador", erro(lambda: lc.montar(SEED, "X", lc.BETA)) != "")

    # relógio voltando
    lc.ativar(beta)
    d = lc._ler_todos(); d["visto"] = (hoje + dt.timedelta(days=31)).isoformat(); lc._gravar(d)
    caso("beta vence mesmo voltando o relógio", lc.estado()["tipo"] == "teste" and "terminou" in lc.estado()["aviso"])

    lc.remover()
    caso("remover volta ao teste", lc.estado()["tipo"] == "teste")

    # chave real: serial de teste não vale no app de verdade
    lc.PUBLICA = PUB_REAL
    caso("serial feito com outra chave é recusado", "inválido" in erro(lambda: lc.ler(serial)))
    caso("assinatura confere com cryptography (RFC 8032)", _rfc())
    print(f"\n{ok}/{ok + falhas}")
    return 1 if falhas else 0


def _rfc():
    # vetor 1 da RFC 8032
    sk = bytes.fromhex("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60")
    pk = bytes.fromhex("d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a")
    sig = bytes.fromhex("e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b")
    return ed.publica(sk) == pk and ed.assinar(sk, b"") == sig and ed.conferir(pk, b"", sig) and not ed.conferir(pk, b"x", sig)


if __name__ == "__main__":
    sys.exit(main())
