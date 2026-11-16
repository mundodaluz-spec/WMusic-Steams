#!/usr/bin/env python3
"""WMusic Steams - gerador de seriais no computador (só para o Heitor).
Uso: python gerar_serial.py   (precisa do CHAVE-PRIVADA-WMUSIC-STEAMS.txt nesta pasta)"""
import csv, datetime as dt, os, sys, urllib.parse, webbrowser
PASTA = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(PASTA))
from wmsteams import licenca as lc, ed25519_puro as ed  # noqa: E402

TETO = 78000.0
PRECO = 197.0
LINK = "https://wmusic-steams.netlify.app"
ARQ = os.path.join(PASTA, "vendas-wmusic-steams.csv")


def ler_chave():
    c = os.path.join(PASTA, "CHAVE-PRIVADA-WMUSIC-STEAMS.txt")
    if not os.path.exists(c):
        sys.exit("Não achei " + c)
    v = dict(l.strip().split("=", 1) for l in open(c, encoding="utf-8") if "=" in l and not l.startswith("#"))
    seed = bytes.fromhex(v["CHAVE"])
    if ed.publica(seed) != lc.PUBLICA:
        sys.exit("Essa chave não é a do WMusic Steams.")
    return seed


def registrar(linha):
    novo = not os.path.exists(ARQ)
    with open(ARQ, "a", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        if novo:
            w.writerow(["tipo", "data", "id", "nome", "computador", "whatsapp", "valor", "validade", "serial"])
        w.writerow(linha)


def total_ano():
    t, ano = 0.0, str(dt.date.today().year)
    if os.path.exists(ARQ):
        for r in csv.DictReader(open(ARQ, encoding="utf-8-sig"), delimiter=";"):
            if r["tipo"] == "venda" and r["data"].endswith(ano) and r["valor"]:
                t += float(r["valor"].replace(",", "."))
    return t


def main():
    seed = ler_chave()
    print("\n=== WMusic Steams · gerador de seriais ===")
    tipo = input("1 = venda   2 = beta tester   3 = presente (ilimitado)  [1]: ").strip() or "1"
    nome = input("Nome: ").strip()
    if not nome:
        sys.exit("Sem nome, sem serial.")
    zap = "".join(c for c in input("WhatsApp com DDD (opcional): ") if c.isdigit())
    hoje = dt.date.today()
    if tipo == "3":
        cod = input("Código do computador (recomendado; Enter = qualquer computador): ").strip() or None
        serial, ident = lc.montar(seed, nome, lc.PRESENTE, codigo=cod)
        registrar(["presente", hoje.strftime("%d/%m/%Y"), ident, nome, (cod or "").upper(), zap, "", "ilimitado", serial])
        msg = (f"Olá, {nome}! Você ganhou uma licença do WMusic Steams 🎁🎧\n\nSeu serial:\n{serial}\n\n"
               "Como ativar: abra o WMusic Steams, clique no botão da chave no alto da tela, cole o serial inteiro e "
               f"clique em Ativar.\n\nDownload e instruções: {LINK}\nAproveite!")
    elif tipo == "2":
        d = input("Válido por quantos dias [30]: ").strip()
        ate = hoje + dt.timedelta(days=int(d or 30))
        cod = input("Código do computador (Enter = qualquer computador): ").strip() or None
        serial, ident = lc.montar(seed, nome, lc.BETA, codigo=cod, validade=ate)
        registrar(["beta", hoje.strftime("%d/%m/%Y"), ident, nome, cod or "", zap, "", ate.isoformat(), serial])
        msg = (f"Olá, {nome}! Obrigado por testar o WMusic Steams 🎧\n\nSeu serial de BETA (vale até {ate:%d/%m/%Y}):\n"
               f"{serial}\n\nComo ativar: abra o WMusic Steams, clique no botão da chave no alto da tela, cole o serial "
               "inteiro e clique em Ativar.\n\nPor favor, não passe o programa nem o serial para ninguém. Me conte aqui tudo o que achar!")
    else:
        cod = input("Código do computador do cliente: ").strip()
        seg = input("2º computador de quem já comprou? Digite o id (Enter = venda nova): ").strip().upper()
        valor = 0.0
        if not seg:
            v = input(f"Valor pago R$ [{PRECO:.0f}]: ").strip().replace(",", ".")
            valor = float(v) if v else PRECO
        try:
            serial, ident = lc.montar(seed, nome, lc.VENDA, codigo=cod, ident=bytes.fromhex(seg) if seg else None)
        except lc.ErroSerial as e:
            sys.exit(str(e))
        registrar(["venda", hoje.strftime("%d/%m/%Y"), ident, nome, cod.upper(), zap, f"{valor:.2f}".replace(".", ","), "", serial])
        t = total_ano()
        print(f"\nTotal do WMusic Steams em {hoje.year}: R$ {t:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        if t >= TETO:
            print("⚠ Passou do seu teto de segurança de R$ 78.000!")
        msg = (f"Olá, {nome}! Obrigado por comprar o WMusic Steams 🎧\n\nSeu serial (feito para o computador {cod.upper()}):\n"
               f"{serial}\n\nComo ativar: abra o WMusic Steams, clique no botão da chave no alto da tela, cole o serial "
               f"inteiro e clique em Ativar.\n\nDownload e instruções: {LINK}\nQualquer dúvida, é só chamar aqui.")
    print("\nSERIAL:\n" + serial + f"\n(id {ident})\n\nMensagem:\n" + "-" * 40 + "\n" + msg + "\n" + "-" * 40)
    if zap and input("\nAbrir o WhatsApp com a mensagem? [S/n] ").strip().lower() != "n":
        webbrowser.open("https://wa.me/" + ("" if zap.startswith("55") else "55") + zap + "?text=" + urllib.parse.quote(msg))
    input("\nEnter para fechar.")


if __name__ == "__main__":
    main()
