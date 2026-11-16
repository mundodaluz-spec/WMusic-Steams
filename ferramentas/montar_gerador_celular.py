#!/usr/bin/env python3
"""Gera ferramentas/gerador-celular.html: gerador de seriais (venda e beta) para o celular.
A chave privada NÃO vai na página: o Heitor cola uma vez e ela fica só no navegador dele."""
import base64, io, os, re
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
F = os.path.dirname(os.path.abspath(__file__))
pub = re.search(r'PUBLICA = bytes.fromhex\("([0-9a-f]{64})"\)', open(f"{R}/wmsteams/licenca.py").read()).group(1)
ed = open(f"{F}/wmst-ed25519.js", encoding="utf-8").read()
se = open(f"{F}/wmst-serial.js", encoding="utf-8").read()
from PIL import Image
im = Image.open(f"{R}/assets/logo-horizontal.png"); im = im.resize((round(im.width * 72 / im.height), 72), Image.LANCZOS)
b = io.BytesIO(); im.save(b, "PNG", optimize=True); logo = base64.b64encode(b.getvalue()).decode()
html = open(f"{F}/gerador-celular.modelo.html", encoding="utf-8").read()
html = html.replace("__LOGO__", logo).replace("__PUB__", pub).replace("/*__ED__*/", ed).replace("/*__SERIAL__*/", se)
open(f"{F}/gerador-celular.html", "w", encoding="utf-8").write(html)
print("ok", len(html))
