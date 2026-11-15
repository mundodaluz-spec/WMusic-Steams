"""Controle remoto pela rede: iPhone, iPad, Android ou outro computador abrem
http://IP-DO-PC:8800 no navegador (na mesma rede Wi-Fi do palco) e veem a letra,
o acorde, a música e o mixer em tempo real.

- Quem só abre a página VÊ (letra, acorde, tempo, timecode).
- Para CONTROLAR (tocar, parar, pular, trocar música, mexer no mixer) a página
  pede o PIN de 4 números que aparece no computador.
- O áudio continua saindo só do computador (pela placa de som); a rede leva
  só comandos e o estado da tela, então o Wi-Fi nunca atrasa o som.

Protocolo: WebSocket /ws com mensagens JSON.
  servidor -> cliente: {"t":"projeto", ...} ao conectar/trocar música
                       {"t":"estado", "pos":s, "tocando":b, "tc":..., "mixer":{...}, "relogio":ms}  (10x por segundo)
                       {"t":"biblioteca", "musicas":[...]}
  cliente -> servidor: {"cmd":"pin","pin":"1234"} | {"cmd":"tocar"} | {"cmd":"pausar"} | {"cmd":"parar"}
                       {"cmd":"ir","s":12.3} | {"cmd":"mixer","chave":"voz","campo":"mute|solo|volume_db","valor":...}
                       {"cmd":"abrir","id":"<pasta>"} | {"cmd":"loop","a":s,"b":s} | {"cmd":"loop_off"}
"""
from __future__ import annotations

import asyncio
import json
import os
import random
import socket
import threading
import time
from typing import Callable

from . import projeto as pj

PORTA_PADRAO = 8800


def ips_locais() -> list[str]:
    ips = []
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))  # não envia nada; só escolhe a interface de saída
        ips.append(s.getsockname()[0])
        s.close()
    except Exception:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if ip not in ips and not ip.startswith("127."):
                ips.append(ip)
    except Exception:
        pass
    return ips or ["127.0.0.1"]


class Remoto:
    """Servidor HTTP + WebSocket numa thread própria (aiohttp)."""

    def __init__(self, obter_estado: Callable[[], dict], obter_projeto: Callable[[], dict | None],
                 executar: Callable[[dict], None], porta: int = PORTA_PADRAO):
        self.obter_estado = obter_estado
        self.obter_projeto = obter_projeto
        self.executar = executar
        self.porta = porta
        self.pin = f"{random.randint(0, 9999):04d}"
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._clientes: dict = {}   # ws -> {"controle": bool}
        self._runner = None
        self.ativo = False
        self.erro = None
        self._versao_projeto = 0
        self._pasta_web = os.path.join(pj.pasta_recursos(), "assets", "web")
        self._assets = os.path.join(pj.pasta_recursos(), "assets")

    # -------------------------------------------------------------- ciclo de vida
    def iniciar(self) -> bool:
        if self.ativo:
            return True
        pronto = threading.Event()
        self.erro = None

        def rodar():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            try:
                self._loop.run_until_complete(self._subir())
                self.ativo = True
            except Exception as e:
                self.erro = str(e)
            pronto.set()
            if self.ativo:
                self._tarefa = self._loop.create_task(self._transmitir())
                self._loop.run_forever()

        self._thread = threading.Thread(target=rodar, daemon=True, name="wmusic-remoto")
        self._thread.start()
        pronto.wait(10)
        return self.ativo

    def parar(self):
        if not self.ativo or not self._loop:
            return
        fut = asyncio.run_coroutine_threadsafe(self._descer(), self._loop)
        try:
            fut.result(5)
        except Exception:
            pass
        self._loop.call_soon_threadsafe(self._loop.stop)
        self.ativo = False

    def novo_pin(self):
        self.pin = f"{random.randint(0, 9999):04d}"
        for info in self._clientes.values():
            info["controle"] = False

    def projeto_mudou(self):
        self._versao_projeto += 1

    @property
    def clientes(self) -> int:
        return len(self._clientes)

    def urls(self) -> list[str]:
        return [f"http://{ip}:{self.porta}" for ip in ips_locais()]

    # -------------------------------------------------------------- servidor
    async def _subir(self):
        from aiohttp import web
        app = web.Application()
        app.router.add_get("/", self._index)
        app.router.add_get("/ws", self._ws)
        app.router.add_get("/manifest.webmanifest", self._manifest)
        app.router.add_static("/web/", self._pasta_web, show_index=False)
        app.router.add_static("/assets/", self._assets, show_index=False)
        self._runner = web.AppRunner(app, access_log=None)
        await self._runner.setup()
        site = web.TCPSite(self._runner, "0.0.0.0", self.porta, reuse_address=True)
        await site.start()

    async def _descer(self):
        t = getattr(self, "_tarefa", None)
        if t:
            t.cancel()
        for ws in list(self._clientes):
            try:
                await ws.close()
            except Exception:
                pass
        if self._runner:
            await self._runner.cleanup()

    async def _index(self, req):
        from aiohttp import web
        return web.FileResponse(os.path.join(self._pasta_web, "index.html"),
                                headers={"Cache-Control": "no-cache"})

    async def _manifest(self, req):
        from aiohttp import web
        return web.json_response({
            "name": "WMusic Steams", "short_name": "Steams", "start_url": "/", "display": "standalone",
            "background_color": "#0b0b0b", "theme_color": "#0b0b0b",
            "icons": [{"src": "/assets/icone.png", "sizes": "1024x1024", "type": "image/png"}]})

    async def _enviar(self, ws, msg: dict):
        try:
            await ws.send_str(json.dumps(msg, ensure_ascii=False, separators=(",", ":")))
        except Exception:
            pass

    def _msg_projeto(self) -> dict:
        p = self.obter_projeto()
        bib = [{"id": os.path.basename(x["pasta"]), "titulo": x.get("titulo"), "duracao": x.get("duracao", 0),
                "tom": x.get("tom")} for x in pj.listar_biblioteca()]
        if not p:
            return {"t": "projeto", "projeto": None, "biblioteca": bib}
        return {"t": "projeto", "biblioteca": bib, "projeto": {
            "id": os.path.basename(p["pasta"]), "titulo": p["titulo"], "duracao": p["duracao"],
            "tom": p.get("tom"), "acordes": p.get("acordes", []), "letra": p.get("letra", {}),
            "trilhas": p["trilhas"], "picos": p.get("_picos_web", []), "smpte": p.get("smpte")}}

    async def _ws(self, req):
        from aiohttp import web, WSMsgType
        ws = web.WebSocketResponse(heartbeat=10)
        await ws.prepare(req)
        self._clientes[ws] = {"controle": False, "versao": self._versao_projeto}
        await self._enviar(ws, self._msg_projeto())
        await self._enviar(ws, {"t": "acesso", "controle": False})
        try:
            async for m in ws:
                if m.type != WSMsgType.TEXT:
                    continue
                try:
                    c = json.loads(m.data)
                except Exception:
                    continue
                cmd = c.get("cmd")
                if cmd == "pin":
                    ok = str(c.get("pin", "")).strip() == self.pin
                    self._clientes[ws]["controle"] = ok
                    await self._enviar(ws, {"t": "acesso", "controle": ok, "erro": None if ok else "PIN errado"})
                elif cmd == "ping":
                    await self._enviar(ws, {"t": "pong", "c": c.get("c"), "relogio": time.time() * 1000})
                elif cmd in ("tocar", "pausar", "parar", "ir", "mixer", "abrir", "loop", "loop_off"):
                    if not self._clientes[ws]["controle"]:
                        await self._enviar(ws, {"t": "acesso", "controle": False, "erro": "Digite o PIN para controlar"})
                        continue
                    if cmd == "abrir":
                        ids = {os.path.basename(x["pasta"]): x["pasta"] for x in pj.listar_biblioteca()}
                        if c.get("id") not in ids:
                            continue
                        c = {"cmd": "abrir", "pasta": ids[c["id"]]}
                    self.executar(c)
        finally:
            self._clientes.pop(ws, None)
        return ws

    async def _transmitir(self):
        while True:
            await asyncio.sleep(0.1)
            if not self._clientes:
                continue
            try:
                est = self.obter_estado()
            except Exception:
                continue
            est["t"] = "estado"
            est["relogio"] = time.time() * 1000
            for ws, info in list(self._clientes.items()):
                if info["versao"] != self._versao_projeto:
                    info["versao"] = self._versao_projeto
                    await self._enviar(ws, self._msg_projeto())
                await self._enviar(ws, est)
