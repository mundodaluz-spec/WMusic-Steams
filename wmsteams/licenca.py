"""Licença do WMusic Steams.

Serial = dados + assinatura Ed25519 (só o Heitor tem a chave privada). O app
confere offline com a chave pública abaixo.

- VENDA: preso ao "código do computador" (mandado pelo cliente junto com o
  comprovante). O mesmo serial não ativa em outro computador.
- BETA: tem data de validade; pode ou não ser preso a um computador.
- Sem serial: modo teste, separa GRATIS músicas. Tocar o que já foi separado
  continua livre sempre.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import subprocess
import sys
import uuid

from . import ed25519_puro as ed

PUBLICA = bytes.fromhex("ecb8b486b9511181d065a5a72d1978b566fa53798f0890bfdf49c96cef090623")
PREFIXO = "WMST"
CONTEXTO = b"WMUSIC STEAMS 1"
ALF = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
EPOCA = dt.date(2026, 1, 1)
GRATIS = 3
VENDA, BETA = 1, 2
REVOGADOS: set[str] = set()   # ids (hex) de seriais cancelados; entram na próxima versão

PASTAS_TESTE: list[str] | None = None   # os testes trocam para uma pasta temporária
MAQUINA_TESTE: str | None = None


class ErroSerial(Exception):
    pass


# ---------------------------------------------------------------- base32 sem letras confusas

def b32(b: bytes) -> str:
    s, acc, bits = "", 0, 0
    for x in b:
        acc = ((acc << 8) | x) & 0xFFFF
        bits += 8
        while bits >= 5:
            s += ALF[(acc >> (bits - 5)) & 31]
            bits -= 5
    if bits:
        s += ALF[(acc << (5 - bits)) & 31]
    return s


def de_b32(s: str) -> bytes:
    out, acc, bits = bytearray(), 0, 0
    for c in s:
        v = ALF.index(c)
        acc = ((acc << 5) | v) & 0xFFFF
        bits += 5
        if bits >= 8:
            out.append((acc >> (bits - 8)) & 255)
            bits -= 8
    return bytes(out)


def _limpar(texto: str) -> str:
    t = texto.upper().replace("O", "0").replace("I", "1").replace("L", "1").replace("U", "V")
    return "".join(c for c in t if c in ALF)


# ---------------------------------------------------------------- código do computador

def _id_maquina() -> str:
    if MAQUINA_TESTE:
        return MAQUINA_TESTE
    try:
        if sys.platform == "win32":
            import winreg
            k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography", 0,
                               winreg.KEY_READ | getattr(winreg, "KEY_WOW64_64KEY", 0))
            return str(winreg.QueryValueEx(k, "MachineGuid")[0])
        if sys.platform == "darwin":
            out = subprocess.run(["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
                                 capture_output=True, text=True, timeout=5).stdout
            for linha in out.splitlines():
                if "IOPlatformUUID" in linha:
                    return linha.split("=")[-1].strip().strip('"')
        for f in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
            if os.path.exists(f):
                return open(f).read().strip()
    except Exception:
        pass
    return "mac-%012x" % uuid.getnode()


def _maquina_bytes() -> bytes:
    return hashlib.sha256(b"WMST-MAQ|" + _id_maquina().encode()).digest()[:5]


def codigo_computador() -> str:
    s = b32(_maquina_bytes())
    return s[:4] + "-" + s[4:]


def codigo_para_bytes(codigo: str) -> bytes:
    c = _limpar(codigo)
    if len(c) != 8:
        raise ErroSerial("O código do computador tem 8 letras e números (ex.: AB12-CD34).")
    return de_b32(c)


# ---------------------------------------------------------------- serial

def montar(seed: bytes, nome: str, tipo: int = VENDA, codigo: str | None = None,
           validade: dt.date | None = None, ident: bytes | None = None,
           hoje: dt.date | None = None) -> tuple[str, str]:
    """Usado só pelo gerador (precisa da chave privada)."""
    hoje = hoje or dt.date.today()
    ident = ident or os.urandom(4)
    maq = codigo_para_bytes(codigo) if codigo else bytes(5)
    if tipo == VENDA and not codigo:
        raise ErroSerial("Serial de venda precisa do código do computador do cliente.")
    if tipo == BETA and not validade:
        raise ErroSerial("Serial de beta precisa de data de validade.")
    nb = nome.strip().encode("utf-8")[:48]
    while True:
        try:
            nb.decode("utf-8"); break
        except UnicodeDecodeError:
            nb = nb[:-1]
    emissao = (hoje - EPOCA).days
    val = (validade - EPOCA).days if validade else 0
    payload = (bytes([1, tipo]) + ident + emissao.to_bytes(2, "big") + val.to_bytes(2, "big")
               + maq + bytes([len(nb)]) + nb)
    sig = ed.assinar(seed, CONTEXTO + payload)
    s = b32(payload + sig)
    return PREFIXO + "-" + "-".join(s[i:i + 5] for i in range(0, len(s), 5)), ident.hex().upper()


def ler(texto: str, conferir_maquina: bool = True) -> dict:
    t = texto.strip().upper()
    if PREFIXO in t:
        t = t[t.index(PREFIXO) + len(PREFIXO):]
    c = _limpar(t)
    try:
        bruto = de_b32(c)
    except ValueError:
        raise ErroSerial("Esse serial tem caracteres que não existem num serial do WMusic Steams.")
    if len(bruto) < 16 + 64:
        raise ErroSerial("Serial incompleto. Copie e cole o serial inteiro, do WMST até o fim.")
    n = bruto[15]
    payload = bruto[:16 + n]
    sig = bruto[16 + n:16 + n + 64]
    if bruto[0] != 1 or len(sig) != 64 or not ed.conferir(PUBLICA, CONTEXTO + payload, sig):
        raise ErroSerial("Serial inválido. Confira se copiou inteiro, sem cortar nenhuma parte.")
    tipo = bruto[1]
    ident = bruto[2:6].hex().upper()
    emissao = EPOCA + dt.timedelta(days=int.from_bytes(bruto[6:8], "big"))
    v = int.from_bytes(bruto[8:10], "big")
    validade = EPOCA + dt.timedelta(days=v) if v else None
    maq = bruto[10:15]
    nome = payload[16:].decode("utf-8", "replace")
    if ident in REVOGADOS:
        raise ErroSerial("Este serial foi cancelado. Fale com a WMusic no WhatsApp.")
    if conferir_maquina and maq != bytes(5) and maq != _maquina_bytes():
        raise ErroSerial("Este serial é de outro computador. O código deste computador é "
                         f"{codigo_computador()}: mande para a WMusic no WhatsApp.")
    return {"tipo": "venda" if tipo == VENDA else "beta", "id": ident, "nome": nome,
            "emissao": emissao.isoformat(), "validade": validade.isoformat() if validade else None,
            "preso": maq != bytes(5), "serial": texto.strip()}


# ---------------------------------------------------------------- guardar estado (2 lugares)

def _pastas() -> list[str]:
    if PASTAS_TESTE is not None:
        return PASTAS_TESTE
    from .projeto import pasta_usuario
    casa = os.path.expanduser("~")
    if sys.platform == "win32":
        outra = os.path.join(os.environ.get("LOCALAPPDATA") or casa, "WMusic")
    elif sys.platform == "darwin":
        outra = os.path.join(casa, "Library", "Preferences")
    else:
        outra = os.path.join(casa, ".config")
    return [pasta_usuario(), outra]


def _arq(i: int) -> str:
    nomes = ["licenca.json", ".wmusic-steams.dat"]
    return os.path.join(_pastas()[i], nomes[i])


def _selo(d: dict) -> str:
    base = f'{d.get("usadas", 0)}|{d.get("visto", "")}|{codigo_computador()}'
    return hashlib.sha256(b"WMST-SELO|" + base.encode()).hexdigest()[:16]


def _ler_todos() -> dict:
    final = {"usadas": 0, "visto": "", "serial": None, "violado": False}
    for i in range(2):
        try:
            with open(_arq(i), encoding="utf-8") as f:
                d = json.load(f)
        except Exception:
            continue
        if d.get("selo") != _selo(d):
            final["violado"] = True
        final["usadas"] = max(final["usadas"], int(d.get("usadas", 0)))
        final["visto"] = max(final["visto"], str(d.get("visto", "")))
        if d.get("serial") and not final["serial"]:
            final["serial"] = d["serial"]
    return final


def _gravar(d: dict):
    d = {"usadas": d["usadas"], "visto": d["visto"], "serial": d.get("serial")}
    d["selo"] = _selo(d)
    for i in range(2):
        try:
            os.makedirs(os.path.dirname(_arq(i)), exist_ok=True)
            with open(_arq(i), "w", encoding="utf-8") as f:
                json.dump(d, f)
        except Exception:
            pass


def _hoje(d: dict) -> dt.date:
    """Data de hoje, sem deixar o relógio voltar para trás (beta)."""
    hoje = dt.date.today()
    if d.get("visto"):
        try:
            hoje = max(hoje, dt.date.fromisoformat(d["visto"]))
        except ValueError:
            pass
    return hoje


# ---------------------------------------------------------------- o que o app usa

def estado() -> dict:
    d = _ler_todos()
    hoje = _hoje(d)
    restantes = 0 if d["violado"] else max(0, GRATIS - d["usadas"])
    base = {"tipo": "teste", "nome": "", "validade": None, "restantes": restantes,
            "codigo": codigo_computador(), "aviso": ""}
    if d["serial"]:
        try:
            lic = ler(d["serial"])
            if lic["validade"] and hoje > dt.date.fromisoformat(lic["validade"]):
                base["aviso"] = "O período do beta terminou. Peça a versão nova ou compre a licença."
            else:
                base.update(lic)
                base["restantes"] = None
        except ErroSerial as e:
            base["aviso"] = str(e)
    return base


def ativar(texto: str) -> dict:
    lic = ler(texto)
    d = _ler_todos()
    if lic["validade"] and _hoje(d) > dt.date.fromisoformat(lic["validade"]):
        raise ErroSerial("Este serial de beta já venceu (válido até "
                         f"{dt.date.fromisoformat(lic['validade']).strftime('%d/%m/%Y')}).")
    d["serial"] = lic["serial"]
    d["visto"] = max(d["visto"], dt.date.today().isoformat())
    _gravar(d)
    return estado()


def remover():
    d = _ler_todos()
    d["serial"] = None
    _gravar(d)


def pode_separar() -> tuple[bool, str]:
    e = estado()
    if e["tipo"] in ("venda", "beta"):
        return True, ""
    if e["restantes"] > 0:
        return True, ""
    msg = e["aviso"] or (f"O teste grátis acabou ({GRATIS} músicas). As músicas já separadas continuam "
                         "tocando normalmente.")
    return False, msg + f" Para separar mais, ative sua licença (código deste computador: {e['codigo']})."


def registrar_separacao():
    d = _ler_todos()
    d["visto"] = max(d["visto"], dt.date.today().isoformat())
    if estado()["tipo"] == "teste":
        d["usadas"] += 1
    _gravar(d)


def texto_estado(e: dict | None = None) -> str:
    e = e or estado()
    if e["tipo"] == "venda":
        return f"Licenciado para {e['nome']}"
    if e["tipo"] == "beta":
        v = dt.date.fromisoformat(e["validade"]).strftime("%d/%m/%Y")
        return f"BETA · {e['nome']} · até {v}"
    r = e["restantes"]
    return "Teste grátis · " + (f"{r} música{'s' if r != 1 else ''} restante{'s' if r != 1 else ''}" if r else "acabou")


def texto_curto(e: dict | None = None) -> str:
    e = e or estado()
    if e["tipo"] == "venda":
        return "Licenciado"
    if e["tipo"] == "beta":
        return "BETA até " + dt.date.fromisoformat(e["validade"]).strftime("%d/%m")
    return f"Teste · {e['restantes']} restantes" if e["restantes"] else "Ativar licença"
