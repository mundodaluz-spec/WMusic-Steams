"""Visual WMusic (metal escovado, creme e vermelho), desenhado a partir da arte aprovada.

As peças de metal (tampa do fader, tampa do pan, parafuso e textura escovada) são
recortes da arte; o resto é desenhado em código para funcionar em qualquer tamanho
de janela e com qualquer número de canais.
"""
from __future__ import annotations

import os

from PySide6.QtCore import Qt, QRectF, QPointF, Signal, QByteArray, QSize
from PySide6.QtGui import (QColor, QFont, QFontDatabase, QLinearGradient, QPainter, QPainterPath,
                           QPen, QPixmap, QRadialGradient, QIcon, QImage, QFontMetricsF, QBrush)
from PySide6.QtWidgets import QPushButton, QWidget, QSizePolicy

from . import projeto as pj

PRETO = "#0b0b0b"
CREME = "#F2E3CF"
VERMELHO = "#E1262C"
AMBAR = "#F2A12E"
CINZA = "#9a938c"
CINZA_ESC = "#5f5953"

FAMILIA = "Inter"
MONO = ["JetBrains Mono", "Consolas", "Menlo", "DejaVu Sans Mono", "monospace"]


def recurso(*partes) -> str:
    return os.path.join(pj.pasta_recursos(), "assets", *partes)


def caminho_qss(*partes) -> str:
    return recurso(*partes).replace("\\", "/")


_cache: dict = {}


def pix(nome: str) -> QPixmap:
    if nome not in _cache:
        _cache[nome] = QPixmap(recurso(*nome.split("/")))
    return _cache[nome]


def carregar_fontes():
    global FAMILIA
    pasta = recurso("fonts")
    if os.path.isdir(pasta):
        for f in sorted(os.listdir(pasta)):
            if f.lower().endswith((".ttf", ".otf")):
                QFontDatabase.addApplicationFont(os.path.join(pasta, f))
    if "Inter" not in QFontDatabase.families():
        FAMILIA = QFont().family()


def fonte(tam: float, peso=QFont.Normal, espacamento: float = 0.0) -> QFont:
    f = QFont(FAMILIA)
    f.setPixelSize(int(round(tam)))
    f.setWeight(peso)
    if espacamento:
        f.setLetterSpacing(QFont.AbsoluteSpacing, espacamento)
    f.setHintingPreference(QFont.PreferNoHinting)
    return f


def fonte_mono(tam: float, peso=QFont.Medium) -> QFont:
    f = QFont()
    f.setFamilies(MONO)
    f.setPixelSize(int(round(tam)))
    f.setWeight(peso)
    return f


# ------------------------------------------------------------------ ícones (SVG)

_SVG = {
    "mais": '<circle cx="12" cy="12" r="9"/><path d="M12 7.5v9M7.5 12h9"/>',
    "pasta": '<path d="M3 7.5a1.5 1.5 0 0 1 1.5-1.5H9l2 2h8.5A1.5 1.5 0 0 1 21 9.5v8A1.5 1.5 0 0 1 19.5 19h-15A1.5 1.5 0 0 1 3 17.5z"/>',
    "exportar": '<path d="M12 15V4M7.5 8.5 12 4l4.5 4.5M5 14v4.5A1.5 1.5 0 0 0 6.5 20h11a1.5 1.5 0 0 0 1.5-1.5V14"/>',
    "tocar": '<path d="M7 4.8v14.4a.8.8 0 0 0 1.2.7l11.3-7.2a.8.8 0 0 0 0-1.4L8.2 4.1A.8.8 0 0 0 7 4.8z" fill="C" stroke="none"/>',
    "pausar": '<rect x="6" y="4.5" width="4" height="15" rx="1" fill="C" stroke="none"/><rect x="14" y="4.5" width="4" height="15" rx="1" fill="C" stroke="none"/>',
    "parar": '<rect x="6" y="6" width="12" height="12" rx="1.2" fill="C" stroke="none"/>',
    "inicio": '<path d="M6 5v14" /><path d="M19 5.8v12.4a.7.7 0 0 1-1.1.6L9.6 12.6a.7.7 0 0 1 0-1.2l8.3-6.2a.7.7 0 0 1 1.1.6z" fill="C" stroke="none"/>',
    "loop": '<path d="M4 12a7 7 0 0 1 12-4.9L18.5 9.5"/><path d="M18.5 4.5v5h-5"/><path d="M20 12a7 7 0 0 1-12 4.9L5.5 14.5"/><path d="M5.5 19.5v-5h5"/>',
    "lixo": '<path d="M4.5 6.5h15M9.5 6.5V4.8a.8.8 0 0 1 .8-.8h3.4a.8.8 0 0 1 .8.8v1.7M6.5 6.5l.9 12.6A1 1 0 0 0 8.4 20h7.2a1 1 0 0 0 1-.9l.9-12.6M10 10.5v6M14 10.5v6"/>',
    "banco": '<ellipse cx="12" cy="6" rx="7.5" ry="2.8"/><path d="M4.5 6v12c0 1.5 3.4 2.8 7.5 2.8s7.5-1.3 7.5-2.8V6M4.5 12c0 1.5 3.4 2.8 7.5 2.8s7.5-1.3 7.5-2.8"/>',
    "onda": '<path d="M3 10v4M6.5 7v10M10 4v16M13.5 8v8M17 5.5v13M20.5 10v4"/>',
    "teclado": '<rect x="2.5" y="6" width="19" height="12" rx="1.5"/><path d="M6 9.5h1.5M10 9.5h1.5M14 9.5h1.5M18 9.5h.01M6 13.5h12"/>',
    "wifi": '<path d="M2.5 9a14 14 0 0 1 19 0M5.5 12.5a9.5 9.5 0 0 1 13 0M8.8 16a4.8 4.8 0 0 1 6.4 0"/><circle cx="12" cy="19.2" r="1.2" fill="C" stroke="none"/>',
    "chave": '<circle cx="8" cy="15" r="4.5"/><path d="M11.2 11.8 20 3M16.5 6.5l2.5 2.5M14 9l2 2"/>',
    "relogio": '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
    "idioma": '<path d="M3.5 17 7.5 6h1l4 11M5 13.5h6"/><path d="M14 6.5h7M17.5 5v1.5M15.5 6.5c.6 3.4 2.5 6 5.5 7.5M19.5 6.5c-.6 3.4-2.5 6-5.5 7.5"/>',
}


def icone_pix(nome: str, cor: str = CREME, tam: int = 18, dpr: float = 2.0) -> QPixmap:
    from PySide6.QtSvg import QSvgRenderer
    chave = ("ic", nome, cor, tam, dpr)
    if chave in _cache:
        return _cache[chave]
    corpo = _SVG[nome].replace('"C"', f'"{cor}"')
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{cor}" '
           f'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">{corpo}</svg>')
    r = QSvgRenderer(QByteArray(svg.encode()))
    lado = int(tam * dpr)
    img = QImage(lado, lado, QImage.Format_ARGB32_Premultiplied)
    img.fill(0)
    p = QPainter(img)
    r.render(p)
    p.end()
    pm = QPixmap.fromImage(img)
    pm.setDevicePixelRatio(dpr)
    _cache[chave] = pm
    return pm


# ------------------------------------------------------------------ fundos e painéis

def pintar_fundo(p: QPainter, r: QRectF, escurecer: int = 70):
    tex = pix("skin/metal.jpg")
    if not tex.isNull():
        p.drawPixmap(r, tex, QRectF(tex.rect()))
    else:
        p.fillRect(r, QColor("#121212"))
    p.fillRect(r, QColor(0, 0, 0, escurecer))


def _caminho(r: QRectF, raio: float) -> QPainterPath:
    c = QPainterPath()
    c.addRoundedRect(r, raio, raio)
    return c


def pintar_painel(p: QPainter, r: QRectF, raio: float = 10, parafusos: bool = True,
                  brilho_vermelho: bool = False, fundo_escuro: bool = False, laterais_vermelhas: bool = False):
    p.save()
    p.setRenderHint(QPainter.Antialiasing)
    # sombra
    for i, a in ((4, 40), (2, 70), (1, 110)):
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, a))
        p.drawRoundedRect(r.adjusted(-i, -i + 1, i, i + 1), raio + i, raio + i)
    cam = _caminho(r, raio)
    g = QLinearGradient(r.topLeft(), r.bottomLeft())
    if fundo_escuro:
        g.setColorAt(0, QColor("#141414")); g.setColorAt(1, QColor("#0c0c0c"))
    else:
        g.setColorAt(0, QColor("#232323")); g.setColorAt(1, QColor("#121212"))
    p.fillPath(cam, g)
    tex = pix("skin/metal.jpg")
    if not tex.isNull():
        p.setClipPath(cam)
        p.setOpacity(0.35 if not fundo_escuro else 0.18)
        p.drawPixmap(r, tex, QRectF(tex.rect()))
        p.setOpacity(1.0)
        # reflexo suave no canto de cima
        rg = QRadialGradient(r.left() + r.width() * 0.25, r.top(), max(r.width(), r.height()) * 0.7)
        rg.setColorAt(0, QColor(255, 255, 255, 16)); rg.setColorAt(1, QColor(255, 255, 255, 0))
        p.fillRect(r, rg)
        p.setClipping(False)
    # bordas: escura por fora, luz fina por dentro
    p.setBrush(Qt.NoBrush)
    p.setPen(QPen(QColor(0, 0, 0, 230), 1.4))
    p.drawRoundedRect(r, raio, raio)
    gl = QLinearGradient(r.topLeft(), r.bottomLeft())
    gl.setColorAt(0, QColor(255, 255, 255, 70)); gl.setColorAt(0.5, QColor(255, 255, 255, 18)); gl.setColorAt(1, QColor(255, 255, 255, 30))
    p.setPen(QPen(QBrush(gl), 1))
    p.drawRoundedRect(r.adjusted(1.2, 1.2, -1.2, -1.2), raio - 1, raio - 1)
    if laterais_vermelhas:
        for x in (r.left() + 2.2, r.right() - 2.2):
            gv = QLinearGradient(QPointF(x, r.top()), QPointF(x, r.bottom()))
            gv.setColorAt(0, QColor(225, 38, 44, 0)); gv.setColorAt(0.5, QColor(225, 38, 44, 120)); gv.setColorAt(1, QColor(225, 38, 44, 40))
            p.setPen(QPen(QBrush(gv), 1))
            p.drawLine(QPointF(x, r.top() + raio), QPointF(x, r.bottom() - raio))
    if brilho_vermelho:
        y = r.bottom() - 1
        gb = QLinearGradient(QPointF(r.left(), y), QPointF(r.right(), y))
        gb.setColorAt(0, QColor(225, 38, 44, 0)); gb.setColorAt(0.5, QColor(225, 38, 44, 210)); gb.setColorAt(1, QColor(225, 38, 44, 0))
        for w, a in ((6, 0.18), (3, 0.35), (1.2, 1.0)):
            p.setOpacity(a)
            p.setPen(QPen(QBrush(gb), w))
            p.drawLine(QPointF(r.left() + raio, y), QPointF(r.right() - raio, y))
        p.setOpacity(1)
    if parafusos:
        pm = pix("skin/parafuso.png")
        if not pm.isNull():
            s = 11
            for cx, cy in ((r.left() + 9, r.top() + 9), (r.right() - 9, r.top() + 9),
                           (r.left() + 9, r.bottom() - 9), (r.right() - 9, r.bottom() - 9)):
                p.drawPixmap(QRectF(cx - s / 2, cy - s / 2, s, s), pm, QRectF(pm.rect()))
    p.restore()


def texto_brilho(p: QPainter, r: QRectF, flags, txt: str, cor: str, brilho: int = 90):
    c = QColor(cor)
    p.save()
    for dx, dy, a in ((0, 0, brilho // 3), (1, 0, brilho // 4), (-1, 0, brilho // 4), (0, 1, brilho // 4), (0, -1, brilho // 4)):
        g = QColor(c); g.setAlpha(a)
        p.setPen(g)
        p.drawText(r.translated(dx * 1.5, dy * 1.5), flags, txt)
    p.setPen(c)
    p.drawText(r, flags, txt)
    p.restore()


# ------------------------------------------------------------------ botão

class Botao(QPushButton):
    """Botão de metal. tipo: 'metal' ou 'vermelho'. ligado (checável): 'vermelho' ou 'ambar'."""

    def __init__(self, texto: str = "", icone: str | None = None, tipo: str = "metal",
                 ligado: str = "vermelho", tam_fonte: float = 14, peso=QFont.DemiBold, parent=None):
        super().__init__(texto, parent)
        self.tipo, self.cor_ligado, self.icone = tipo, ligado, icone
        self.tam_fonte, self.peso = tam_fonte, peso
        self._hover = False
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(34)
        self.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)

    def sizeHint(self):
        fm = QFontMetricsF(fonte(self.tam_fonte, self.peso))
        w = fm.horizontalAdvance(self.text()) + 30 + (24 if self.icone else 0)
        return QSize(int(max(w, 40)), max(self.minimumHeight(), 34))

    def enterEvent(self, e):
        self._hover = True; self.update(); super().enterEvent(e)

    def leaveEvent(self, e):
        self._hover = False; self.update(); super().leaveEvent(e)

    def definir_icone(self, nome):
        self.icone = nome; self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(3, 3, -3, -4)
        raio = min(8.0, r.height() / 3.2)
        aceso = self.tipo == "vermelho" or (self.isCheckable() and self.isChecked())
        cor = "vermelho" if self.tipo == "vermelho" else (self.cor_ligado if aceso else "metal")
        if not self.isEnabled():
            p.setOpacity(0.45)
        # brilho em volta quando aceso
        if aceso:
            base = QColor(VERMELHO if cor == "vermelho" else AMBAR)
            for i, a in ((5, 25), (3, 45), (1.5, 80)):
                c = QColor(base); c.setAlpha(a)
                p.setPen(Qt.NoPen); p.setBrush(c)
                p.drawRoundedRect(r.adjusted(-i, -i, i, i), raio + i, raio + i)
        # moldura escura
        p.setPen(Qt.NoPen); p.setBrush(QColor(0, 0, 0, 220))
        p.drawRoundedRect(r.adjusted(-1.5, -1.5, 1.5, 2), raio + 1.5, raio + 1.5)
        g = QLinearGradient(r.topLeft(), r.bottomLeft())
        if cor == "vermelho":
            g.setColorAt(0, QColor("#ff4a45")); g.setColorAt(0.45, QColor("#d71920")); g.setColorAt(1, QColor("#8c0a10"))
        elif cor == "ambar":
            g.setColorAt(0, QColor("#ffc75a")); g.setColorAt(0.5, QColor("#e8901c")); g.setColorAt(1, QColor("#a85a06"))
        else:
            claro = 12 if (self._hover or self.isDown()) else 0
            g.setColorAt(0, QColor(48 + claro, 48 + claro, 48 + claro)); g.setColorAt(0.5, QColor(27 + claro, 27 + claro, 27 + claro)); g.setColorAt(1, QColor(16, 16, 16))
        p.setBrush(g)
        p.drawRoundedRect(r, raio, raio)
        if cor == "metal":
            tex = pix("skin/metal.jpg")
            if not tex.isNull():
                p.save(); p.setClipPath(_caminho(r, raio)); p.setOpacity(0.25)
                p.drawPixmap(r, tex, QRectF(tex.rect())); p.restore()
        # brilho de vidro na metade de cima
        gv = QLinearGradient(r.topLeft(), QPointF(r.left(), r.center().y()))
        gv.setColorAt(0, QColor(255, 255, 255, 60 if cor != "metal" else 26)); gv.setColorAt(1, QColor(255, 255, 255, 0))
        p.setBrush(gv)
        p.drawRoundedRect(r.adjusted(1, 1, -1, -r.height() / 2), raio - 1, raio - 1)
        # filete de luz
        gl = QLinearGradient(r.topLeft(), r.bottomLeft())
        gl.setColorAt(0, QColor(255, 255, 255, 110 if cor != "metal" else 70)); gl.setColorAt(1, QColor(255, 255, 255, 10))
        p.setBrush(Qt.NoBrush); p.setPen(QPen(QBrush(gl), 1))
        p.drawRoundedRect(r.adjusted(0.5, 0.5, -0.5, -0.5), raio, raio)
        if self.isDown():
            p.fillRect(r, QColor(0, 0, 0, 40))
        # conteúdo
        cor_txt = QColor("#2a1400") if cor == "ambar" else (QColor("#ffffff") if cor == "vermelho" else QColor(CREME))
        f = fonte(self.tam_fonte, self.peso)
        p.setFont(f)
        fm = QFontMetricsF(f)
        txt = self.text()
        tam_ic = int(min(r.height() - 12, 18))
        larg = fm.horizontalAdvance(txt) + ((tam_ic + (8 if txt else 0)) if self.icone else 0)
        x = r.center().x() - larg / 2
        if self.icone:
            pm = icone_pix(self.icone, "#ffffff" if cor == "vermelho" else (cor_txt.name()), tam_ic)
            p.drawPixmap(QRectF(x, r.center().y() - tam_ic / 2, tam_ic, tam_ic), pm, QRectF(pm.rect()))
            x += tam_ic + (8 if txt else 0)
        if txt:
            p.setPen(QColor(0, 0, 0, 120))
            p.drawText(QRectF(x, r.top() + 1, larg + 4, r.height()), Qt.AlignVCenter | Qt.AlignLeft, txt)
            p.setPen(cor_txt)
            p.drawText(QRectF(x, r.top(), larg + 4, r.height()), Qt.AlignVCenter | Qt.AlignLeft, txt)


# ------------------------------------------------------------------ fader com régua e medidor

ESCALA = [12, 6, 0, -6, -12, -18, -24, -30, -40, -60]


def db_para_frac(db: float) -> float:
    """0 = topo (+12), 1 = fundo (−60). Régua com espaçamento igual entre as marcas."""
    if db >= ESCALA[0]:
        return 0.0
    if db <= ESCALA[-1]:
        return 1.0
    for i in range(len(ESCALA) - 1):
        a, b = ESCALA[i], ESCALA[i + 1]
        if b <= db <= a:
            return (i + (a - db) / (a - b)) / (len(ESCALA) - 1)
    return 1.0


def frac_para_db(f: float) -> float:
    f = min(1.0, max(0.0, f)) * (len(ESCALA) - 1)
    i = min(int(f), len(ESCALA) - 2)
    a, b = ESCALA[i], ESCALA[i + 1]
    return a - (f - i) * (a - b)


class Fader(QWidget):
    mudou = Signal(float)  # dB (−inf = −100)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.db = 0.0
        self.nivel = 0.0  # pico linear do medidor
        self._arr = None
        self.setMinimumSize(112, 180)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        self.setCursor(Qt.SizeVerCursor)

    def _geo(self):
        w, h = self.width(), self.height()
        topo, base = 16, h - 16
        cx_fader = w / 2 - 11
        cx_med = w / 2 + 13
        return topo, base, cx_fader, cx_med

    def definir(self, db: float, emitir=False):
        self.db = max(-100.0, min(12.0, db))
        self.update()
        if emitir:
            self.mudou.emit(self.db)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        topo, base, cxf, cxm = self._geo()
        alt = base - topo
        # régua
        p.setFont(fonte(9.5, QFont.Medium))
        for i, v in enumerate(ESCALA):
            y = topo + alt * i / (len(ESCALA) - 1)
            txt = f"+{v}" if v > 0 else str(v)
            p.setPen(QColor(CINZA))
            p.drawText(QRectF(0, y - 7, cxf - 16, 14), Qt.AlignRight | Qt.AlignVCenter, txt)
            p.drawText(QRectF(cxm + 14, y - 7, w - cxm - 14, 14), Qt.AlignLeft | Qt.AlignVCenter, txt)
            p.setPen(QPen(QColor(120, 114, 108), 1.2))
            p.drawLine(QPointF(cxf - 13, y), QPointF(cxf - 8, y))
            p.drawLine(QPointF(cxm + 7, y), QPointF(cxm + 12, y))
            if i < len(ESCALA) - 1:
                ym = y + alt / (len(ESCALA) - 1) / 2
                p.setPen(QPen(QColor(80, 76, 72), 1))
                p.drawLine(QPointF(cxf - 11, ym), QPointF(cxf - 8, ym))
                p.drawLine(QPointF(cxm + 7, ym), QPointF(cxm + 10, ym))
        # trilhos (fader e medidor)
        for cx, lw in ((cxf, 9), (cxm, 9)):
            rr = QRectF(cx - lw / 2, topo - 8, lw, alt + 16)
            p.setPen(QPen(QColor(0, 0, 0), 1.2))
            g = QLinearGradient(rr.topLeft(), rr.topRight())
            g.setColorAt(0, QColor("#050505")); g.setColorAt(0.5, QColor("#141414")); g.setColorAt(1, QColor("#050505"))
            p.setBrush(g)
            p.drawRoundedRect(rr, lw / 2, lw / 2)
            p.setPen(QPen(QColor(255, 255, 255, 35), 1))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(rr.adjusted(-1.5, -1.5, 1.5, 1.5), lw / 2 + 1.5, lw / 2 + 1.5)
        # medidor (barra creme com brilho)
        import math
        db_med = 20 * math.log10(self.nivel) if self.nivel > 1e-6 else -100
        f = db_para_frac(db_med)
        if f < 1:
            y0 = topo + alt * f
            rr = QRectF(cxm - 2.5, y0, 5, base + 4 - y0)
            cor = QColor(VERMELHO) if db_med > -0.5 else QColor("#fff1d6")
            for i, a in ((4, 30), (2, 60)):
                c = QColor(cor); c.setAlpha(a)
                p.setPen(Qt.NoPen); p.setBrush(c)
                p.drawRoundedRect(rr.adjusted(-i, -i, i, i), 3 + i, 3 + i)
            p.setBrush(cor)
            p.drawRoundedRect(rr, 2.5, 2.5)
        # tampa do fader
        yv = topo + alt * db_para_frac(self.db)
        pm = pix("skin/fader.png")
        cw = 30
        ch = cw * (pm.height() / pm.width()) if not pm.isNull() else 34
        alvo = QRectF(cxf - cw / 2, yv - ch / 2, cw, ch)
        p.setPen(Qt.NoPen); p.setBrush(QColor(0, 0, 0, 120))
        p.drawRoundedRect(alvo.adjusted(1, 3, 1, 4), 4, 4)
        if not pm.isNull():
            p.drawPixmap(alvo, pm, QRectF(pm.rect()))
        else:
            p.setBrush(QColor("#ccc")); p.drawRoundedRect(alvo, 4, 4)

    def _db_em(self, y):
        topo, base, _, _ = self._geo()
        f = (y - topo) / max(1, base - topo)
        return -100.0 if f >= 1.0 else frac_para_db(f)

    def mousePressEvent(self, e):
        topo, base, cxf, _ = self._geo()
        yv = topo + (base - topo) * db_para_frac(self.db)
        if abs(e.position().y() - yv) < 20:
            self._arr = (e.position().y(), self.db)
        else:
            self.definir(self._db_em(e.position().y()), True)
            self._arr = (e.position().y(), self.db)

    def mouseMoveEvent(self, e):
        if self._arr is None:
            return
        topo, base, _, _ = self._geo()
        y0, db0 = self._arr
        fino = 0.25 if e.modifiers() & Qt.ShiftModifier else 1.0
        f0 = db_para_frac(db0) if db0 > -100 else 1.0
        f = f0 + (e.position().y() - y0) / max(1, base - topo) * fino
        self.definir(-100.0 if f >= 1.0 else frac_para_db(f), True)

    def mouseReleaseEvent(self, e):
        self._arr = None

    def mouseDoubleClickEvent(self, e):
        self.definir(0.0, True)

    def wheelEvent(self, e):
        passo = 0.5 if e.angleDelta().y() > 0 else -0.5
        base = self.db if self.db > -60 else -60
        self.definir(base + passo, True)


class Pan(QWidget):
    """Pan horizontal E/D com a tampa de metal."""
    mudou = Signal(float)

    def __init__(self, parent=None, mestre=False):
        super().__init__(parent)
        self.valor = 0.0  # -1..1 (no master: 0..1)
        self.mestre = mestre
        self.setFixedHeight(24 if not mestre else 26)
        self.setMinimumWidth(90)
        self.setCursor(Qt.SizeHorCursor)
        self._arr = False

    def _trilho(self):
        if self.mestre:
            return 12.0, self.width() - 12.0
        return 18.0, self.width() - 18.0

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        x0, x1 = self._trilho()
        cy = self.height() / 2
        if not self.mestre:
            p.setPen(QColor(CINZA)); p.setFont(fonte(11, QFont.Medium))
            p.drawText(QRectF(0, 0, 14, self.height()), Qt.AlignCenter, "E")
            p.drawText(QRectF(self.width() - 14, 0, 14, self.height()), Qt.AlignCenter, "D")
        rr = QRectF(x0, cy - 2.5, x1 - x0, 5)
        p.setPen(QPen(QColor(0, 0, 0), 1)); p.setBrush(QColor("#080808"))
        p.drawRoundedRect(rr, 2.5, 2.5)
        p.setPen(QPen(QColor(255, 255, 255, 30), 1)); p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(rr.adjusted(-1, -1, 1, 1), 3.5, 3.5)
        if self.mestre:
            xv = x0 + (x1 - x0) * self.valor
            g = QLinearGradient(QPointF(x0, 0), QPointF(xv, 0))
            g.setColorAt(0, QColor("#7a0b10")); g.setColorAt(1, QColor("#ff3b3b"))
            for i, a in ((3, 40), (1.5, 90)):
                c = QColor(VERMELHO); c.setAlpha(a); p.setPen(Qt.NoPen); p.setBrush(c)
                p.drawRoundedRect(QRectF(x0, cy - 2.5, xv - x0, 5).adjusted(-i, -i, i, i), 3 + i, 3 + i)
            p.setBrush(g); p.drawRoundedRect(QRectF(x0, cy - 2, xv - x0, 4), 2, 2)
        else:
            p.setPen(QPen(QColor(110, 104, 98), 1))
            for k in range(-4, 5):
                x = (x0 + x1) / 2 + k * (x1 - x0) / 9
                hh = 4 if k == 0 else 2.5
                p.drawLine(QPointF(x, cy - 4 - hh), QPointF(x, cy - 4))
            xv = (x0 + x1) / 2 + self.valor * (x1 - x0) / 2
        pm = pix("skin/pan.png")
        s = 20 if not self.mestre else 22
        alvo = QRectF(xv - s / 2, cy - s / 2, s, s)
        p.setPen(Qt.NoPen); p.setBrush(QColor(0, 0, 0, 120)); p.drawRoundedRect(alvo.adjusted(1, 2, 1, 2), 3, 3)
        if not pm.isNull():
            p.drawPixmap(alvo, pm, QRectF(pm.rect()))

    def _valor_em(self, x):
        x0, x1 = self._trilho()
        f = (x - x0) / max(1, x1 - x0)
        return min(1.0, max(0.0, f)) if self.mestre else min(1.0, max(-1.0, f * 2 - 1))

    def definir(self, v, emitir=False):
        self.valor = v
        if not self.mestre and abs(self.valor) < 0.04:
            self.valor = 0.0
        self.update()
        if emitir:
            self.mudou.emit(self.valor)

    def mousePressEvent(self, e):
        self._arr = True; self.definir(self._valor_em(e.position().x()), True)

    def mouseMoveEvent(self, e):
        if self._arr:
            self.definir(self._valor_em(e.position().x()), True)

    def mouseReleaseEvent(self, e):
        self._arr = False

    def mouseDoubleClickEvent(self, e):
        self.definir(0.0 if not self.mestre else 0.82, True)

    def wheelEvent(self, e):
        d = 0.02 if e.angleDelta().y() > 0 else -0.02
        lo = 0.0 if self.mestre else -1.0
        self.definir(min(1.0, max(lo, self.valor + d)), True)


def estilo_global() -> str:
    seta = caminho_qss("skin", "seta.png")
    seta_v = caminho_qss("skin", "seta_vermelha.png")
    check = caminho_qss("skin", "check.png")
    return f"""
* {{ font-family: '{FAMILIA}'; color: {CREME}; }}
QDialog, QMainWindow {{ background: {PRETO}; }}
QToolTip {{ background: #1b1b1b; color: {CREME}; border: 1px solid #3a3a3a; padding: 4px 8px; }}
QLabel {{ background: transparent; }}
QLabel#sub {{ color: {CINZA}; }}
QComboBox {{
  background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #2c2c2c, stop:0.5 #1b1b1b, stop:1 #121212);
  border: 1px solid #000; border-top-color: #4b4b4b; border-radius: 7px;
  padding: 5px 30px 5px 12px; min-height: 18px; font-weight: 500;
}}
QComboBox:hover {{ border-top-color: #6a6a6a; }}
QComboBox::drop-down {{ subcontrol-origin: padding; subcontrol-position: center right; width: 26px;
  border-left: 1px solid #070707; }}
QComboBox::down-arrow {{ image: url({seta}); width: 10px; height: 6px; }}
QComboBox#vermelha::down-arrow {{ image: url({seta_v}); }}
QComboBox QAbstractItemView {{ background: #161616; border: 1px solid #2c2c2c; selection-background-color: {VERMELHO};
  selection-color: white; outline: 0; padding: 4px; }}
QPlainTextEdit {{ background: rgba(8,8,8,200); border: 1px solid rgba(225,38,44,110); border-radius: 10px;
  padding: 10px 12px; font-size: 14px; selection-background-color: {VERMELHO}; }}
QPlainTextEdit:focus {{ border: 1px solid rgba(225,38,44,230); }}
QCheckBox {{ spacing: 10px; font-size: 14px; }}
QCheckBox::indicator {{ width: 20px; height: 20px; border-radius: 5px; border: 1px solid #000;
  background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #2c2c2c, stop:1 #121212); }}
QCheckBox::indicator:checked {{ border: 1px solid #ff5a55; image: url({check});
  background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #ff4a45, stop:0.5 #d71920, stop:1 #8c0a10); }}
QProgressBar {{ background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #070707, stop:1 #1a1a1a);
  border: 1px solid #000; border-bottom-color: #3a3a3a; border-radius: 9px; min-height: 18px; max-height: 18px; }}
QProgressBar::chunk {{ border-radius: 8px; margin: 1px;
  background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #ff6a62, stop:0.35 #e8222a, stop:1 #8c0a10); }}
QListWidget {{ background: rgba(6,6,8,220); border: 1px solid #000; border-top-color: #333; border-radius: 10px;
  padding: 6px; outline: 0; font-size: 16px; }}
QListWidget::item {{ padding: 9px 14px; border-bottom: 1px solid #1c1c1f; border-radius: 0px; }}
QListWidget::item:hover {{ background: rgba(255,255,255,10); }}
QListWidget::item:selected {{ color: white; border: 1px solid #ff4a45; border-radius: 8px;
  background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #e2262c, stop:0.6 #a8121a, stop:1 #6d070b); }}
QScrollArea {{ border: none; background: transparent; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 0 4px; }}
QScrollBar::handle:horizontal {{ background: #3a3a3a; border-radius: 5px; min-width: 40px; }}
QScrollBar:vertical {{ background: transparent; width: 10px; }}
QScrollBar::handle:vertical {{ background: #3a3a3a; border-radius: 5px; min-height: 40px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QMessageBox {{ background: #141414; }}
QMessageBox QPushButton {{ background: #262626; border: 1px solid #000; border-top-color: #555; border-radius: 7px;
  padding: 6px 18px; min-width: 70px; }}
"""
