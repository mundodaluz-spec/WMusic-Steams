"""Controle remoto: página abre, WebSocket manda projeto e estado, sem PIN só vê,
com PIN errado continua só vendo, com PIN certo o comando chega no programa."""
import asyncio, json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from wmsteams.remoto import Remoto

ok = falhas = 0
def confere(nome, cond, extra=""):
    global ok, falhas
    if cond: ok += 1; print("OK  ", nome, extra)
    else: falhas += 1; print("FALHA", nome, extra)

recebidos = []
estado = {"pos": 12.5, "tocando": True, "tc": "01:00:12:15", "mixer": {"voz": {"mute": False, "solo": False, "volume_db": 0.0}}}
proj = {"pasta": "/tmp/x/Minha Musica", "titulo": "Minha Música", "duracao": 200.0, "tom": "G", "acordes": [],
        "letra": {"linhas": []}, "trilhas": ["voz", "pad"], "smpte": {"ligado": True}}
r = Remoto(lambda: dict(estado), lambda: proj, recebidos.append, porta=8877)
confere("servidor sobe", r.iniciar(), r.erro or "")

async def cliente():
    import aiohttp
    async with aiohttp.ClientSession() as s:
        async with s.get("http://127.0.0.1:8877/") as h:
            html = await h.text()
            confere("página principal", h.status == 200 and "WMusic Steams" in html)
        async with s.get("http://127.0.0.1:8877/assets/logo-horizontal.png") as h:
            confere("imagens da página", h.status == 200)
        async with s.get("http://127.0.0.1:8877/assets/../wmsteams/remoto.py") as h:
            confere("não serve arquivos fora de assets", h.status in (403, 404))
        async with s.ws_connect("http://127.0.0.1:8877/ws") as ws:
            msgs = []
            async def ler(n, t=3.0):
                fim = time.time() + t
                while len(msgs) < n and time.time() < fim:
                    try:
                        m = await ws.receive(timeout=fim - time.time())
                    except asyncio.TimeoutError:
                        break
                    msgs.append(json.loads(m.data))
            async def esperar(cond, t=3.0):
                fim = time.time() + t
                while time.time() < fim:
                    try:
                        m = json.loads((await ws.receive(timeout=fim - time.time())).data)
                    except asyncio.TimeoutError:
                        return None
                    if cond(m):
                        return m
                return None
            await ler(3)
            tipos = [m["t"] for m in msgs]
            confere("recebe projeto, acesso e estado", "projeto" in tipos and "acesso" in tipos and "estado" in tipos, str(tipos[:4]))
            pr = next(m for m in msgs if m["t"] == "projeto")
            confere("projeto certo", pr["projeto"]["titulo"] == "Minha Música" and pr["projeto"]["id"] == "Minha Musica")
            es = next(m for m in msgs if m["t"] == "estado")
            confere("estado com posição e timecode", es["pos"] == 12.5 and es["tc"] == "01:00:12:15" and "relogio" in es)
            await ws.send_str(json.dumps({"cmd": "tocar"})); await asyncio.sleep(0.3)
            confere("sem PIN o comando não passa", recebidos == [])
            await ws.send_str(json.dumps({"cmd": "pin", "pin": "0000" if r.pin != "0000" else "1111"}))
            m = await esperar(lambda m: m["t"] == "acesso")
            confere("PIN errado recusado", m is not None and not m["controle"])
            await ws.send_str(json.dumps({"cmd": "pin", "pin": r.pin}))
            m = await esperar(lambda m: m["t"] == "acesso" and m["controle"])
            confere("PIN certo aceito", m is not None)
            await ws.send_str(json.dumps({"cmd": "mixer", "chave": "voz", "campo": "mute", "valor": True}))
            await ws.send_str(json.dumps({"cmd": "ir", "s": 30}))
            await ws.send_str(json.dumps({"cmd": "abrir", "id": "../../etc"}))
            await asyncio.sleep(0.4)
            confere("comandos chegam no programa", [c["cmd"] for c in recebidos] == ["mixer", "ir"], str(recebidos))
            t0 = time.time(); await ws.send_str(json.dumps({"cmd": "ping", "c": 1}))
            m = await esperar(lambda m: m["t"] == "pong")
            confere("relógio (ping/pong) responde", m is not None, f"{(time.time()-t0)*1000:.0f} ms")
            confere("1 aparelho conectado", r.clientes == 1)

asyncio.run(cliente())
r.parar()
confere("servidor desliga", not r.ativo)
print(f"\n{ok}/{ok+falhas} testes OK")
sys.exit(1 if falhas else 0)
