"""Interface do WMusic Steams (PySide6), no visual WMusic de metal escovado."""
from __future__ import annotations

import os
import shutil
import sys
import traceback

import numpy as np
from PySide6.QtCore import Qt, QThread, QTimer, Signal, QRectF, QPointF
from PySide6.QtGui import (QColor, QFont, QIcon, QKeySequence, QPainter, QPen, QShortcut,
                           QFontMetricsF, QLinearGradient, QBrush, QPainterPath)
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog, QFileDialog, QFrame,
                               QGridLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
                               QMainWindow, QMessageBox, QPlainTextEdit, QProgressBar, QScrollArea,
                               QVBoxLayout, QWidget)

from . import projeto as pj
from . import skin as sk
from .player import Motor
from .skin import CREME, VERMELHO, CINZA, Botao, fonte, pix

CORES = {
    "voz": "#F0353A", "bateria": "#F2E3CF", "baixo": "#F2A12E", "guitarra": "#E6C27A",
    "teclas": "#8EC5EA", "outros": "#A99BF0", "instrumental": "#E6C27A", "pad": "#6FE0A8",
    "original": "#9a938c",
}


def tempo_txt(s: float) -> str:
    s = max(0.0, s)
    m, s = divmod(s, 60)
    return f"{int(m)}:{s:04.1f}"


def db_para_lin(db: float) -> float:
    return 0.0 if db <= -60 else 10 ** (db / 20)


def abrir_no_sistema(caminho: str):
    import subprocess
    if sys.platform == "win32":
        os.startfile(caminho)  # noqa
    elif sys.platform == "darwin":
        subprocess.Popen(["open", caminho])
    else:
        subprocess.Popen(["xdg-open", caminho])


# ===================================================================== peças comuns

class Fundo(QWidget):
    def paintEvent(self, e):
        p = QPainter(self)
        sk.pintar_fundo(p, QRectF(self.rect()), 60)


class Logo(QWidget):
    """Logo WMusic (fone + Music) | STEAMS (ou outro título), como no cabeçalho da arte."""

    def __init__(self, altura=46, com_steams=True, titulo: str | None = None, tam_titulo=16, espac=6.0, peso=QFont.DemiBold):
        super().__init__()
        self.altura, self.com_steams, self.titulo = altura, com_steams, titulo
        self.tam_titulo, self.espac, self.peso = tam_titulo, espac, peso
        self.icone = None
        pm = pix("logo-horizontal.png")
        self.lw = pm.width() * altura / pm.height() if not pm.isNull() else 100
        self.setFixedHeight(altura + 8)
        self.setFixedWidth(int(self._largura()))

    def _fonte(self):
        if self.titulo:
            return fonte(self.tam_titulo, self.peso, self.espac)
        return fonte(22, QFont.ExtraBold, 7.0)

    def _largura(self):
        w = self.lw + 26
        if self.com_steams or self.titulo:
            w += QFontMetricsF(self._fonte()).horizontalAdvance(self.titulo or "STEAMS") + 14 + (34 if self.icone else 0)
        return w

    def definir_icone(self, nome):
        self.icone = nome
        self.setFixedWidth(int(self._largura()))

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        pm = pix("logo-horizontal.png")
        h = self.altura
        y = (self.height() - h) / 2
        if not pm.isNull():
            p.drawPixmap(QRectF(0, y, self.lw, h), pm, QRectF(pm.rect()))
        x = self.lw + 12
        g = QLinearGradient(QPointF(x, y), QPointF(x, y + h))
        g.setColorAt(0, QColor(225, 38, 44, 0)); g.setColorAt(0.5, QColor(225, 38, 44, 255)); g.setColorAt(1, QColor(225, 38, 44, 0))
        p.setPen(QPen(QBrush(g), 1.6))
        p.drawLine(QPointF(x, y + 2), QPointF(x, y + h - 2))
        x += 14
        if self.icone:
            ic = sk.icone_pix(self.icone, CREME, 26)
            p.drawPixmap(QRectF(x, self.height() / 2 - 13, 26, 26), ic, QRectF(ic.rect()))
            x += 34
        if self.com_steams or self.titulo:
            txt = self.titulo or "STEAMS"
            p.setFont(self._fonte())
            gt = QLinearGradient(QPointF(0, y + h * 0.25), QPointF(0, y + h * 0.75))
            gt.setColorAt(0, QColor("#ffffff")); gt.setColorAt(0.55, QColor("#ddd6cc")); gt.setColorAt(1, QColor("#a39d96"))
            p.setPen(QColor(0, 0, 0, 160))
            p.drawText(QRectF(x + 1, 1, 2000, self.height()), Qt.AlignVCenter | Qt.AlignLeft, txt)
            p.setPen(QPen(QBrush(gt), 1))
            p.drawText(QRectF(x, 0, 2000, self.height()), Qt.AlignVCenter | Qt.AlignLeft, txt)


class Cabecalho(QWidget):
    """Barra de metal do topo (janela principal e diálogos)."""

    def __init__(self, altura=74):
        super().__init__()
        self.setFixedHeight(altura)
        self.lay = QHBoxLayout(self)
        self.lay.setContentsMargins(28, 6, 24, 8)
        self.lay.setSpacing(12)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect())
        g = QLinearGradient(r.topLeft(), r.bottomLeft())
        g.setColorAt(0, QColor("#303030")); g.setColorAt(0.45, QColor("#1c1c1c")); g.setColorAt(1, QColor("#101010"))
        p.fillRect(r, g)
        tex = pix("skin/metal.jpg")
        if not tex.isNull():
            p.setOpacity(0.45); p.drawPixmap(r, tex, QRectF(tex.rect())); p.setOpacity(1)
        for cx, a in ((0.62, 55), (0.18, 25)):
            gl = QLinearGradient(QPointF(r.width() * (cx - 0.12), 0), QPointF(r.width() * (cx + 0.12), 0))
            gl.setColorAt(0, QColor(255, 255, 255, 0)); gl.setColorAt(0.5, QColor(255, 255, 255, a)); gl.setColorAt(1, QColor(255, 255, 255, 0))
            p.fillRect(QRectF(0, 0, r.width(), r.height() * 0.55), gl)
        p.setPen(QPen(QColor(255, 255, 255, 60), 1)); p.drawLine(r.topLeft() + QPointF(0, 0.5), r.topRight() + QPointF(0, 0.5))
        p.setPen(QPen(QColor(0, 0, 0, 255), 2)); p.drawLine(r.bottomLeft() - QPointF(0, 1), r.bottomRight() - QPointF(0, 1))
        y = r.bottom() - 2
        gb = QLinearGradient(QPointF(0, y), QPointF(r.width(), y))
        gb.setColorAt(0, QColor(225, 38, 44, 0)); gb.setColorAt(0.5, QColor(225, 38, 44, 200)); gb.setColorAt(1, QColor(225, 38, 44, 0))
        p.setPen(QPen(QBrush(gb), 1.2)); p.drawLine(QPointF(0, y), QPointF(r.width(), y))
        pm = pix("skin/parafuso.png")
        if not pm.isNull():
            for cx in (12, r.width() - 12):
                p.drawPixmap(QRectF(cx - 6, 10, 12, 12), pm, QRectF(pm.rect()))


class Rodape(QWidget):
    def __init__(self, altura=78):
        super().__init__()
        self.setFixedHeight(altura)
        self.lay = QHBoxLayout(self)
        self.lay.setContentsMargins(24, 12, 24, 14)
        self.lay.setSpacing(14)

    def paintEvent(self, e):
        p = QPainter(self)
        r = QRectF(self.rect())
        g = QLinearGradient(r.topLeft(), r.bottomLeft())
        g.setColorAt(0, QColor("#1d1d1d")); g.setColorAt(1, QColor("#0f0f0f"))
        p.fillRect(r, g)
        tex = pix("skin/metal.jpg")
        if not tex.isNull():
            p.setOpacity(0.4); p.drawPixmap(r, tex, QRectF(tex.rect())); p.setOpacity(1)
        gl = QLinearGradient(QPointF(r.width() * 0.45, 0), QPointF(r.width() * 0.75, 0))
        gl.setColorAt(0, QColor(255, 255, 255, 0)); gl.setColorAt(0.5, QColor(255, 255, 255, 30)); gl.setColorAt(1, QColor(255, 255, 255, 0))
        p.fillRect(r, gl)
        gb = QLinearGradient(QPointF(0, 0), QPointF(r.width(), 0))
        gb.setColorAt(0, QColor(225, 38, 44, 0)); gb.setColorAt(0.5, QColor(225, 38, 44, 170)); gb.setColorAt(1, QColor(225, 38, 44, 0))
        p.setPen(QPen(QBrush(gb), 1.2)); p.drawLine(QPointF(0, 0.6), QPointF(r.width(), 0.6))


class DialogoWM(QDialog):
    """Diálogo com cabeçalho de metal (logo + título), corpo e rodapé."""

    def __init__(self, parent, titulo: str, icone: str | None = None, titulo_grande=False, com_rodape=True):
        super().__init__(parent)
        raiz = QVBoxLayout(self); raiz.setContentsMargins(0, 0, 0, 0); raiz.setSpacing(0)
        self.cab = Cabecalho(84)
        if titulo_grande:
            lg = Logo(50, com_steams=False, titulo=titulo, tam_titulo=27, espac=0.2, peso=QFont.Bold)
        else:
            lg = Logo(44, com_steams=False, titulo=titulo.upper(), tam_titulo=15, espac=6.0, peso=QFont.Medium)
            if icone:
                lg.definir_icone(icone)
        self.cab.lay.addWidget(lg); self.cab.lay.addStretch()
        raiz.addWidget(self.cab)
        self.corpo = QVBoxLayout(); self.corpo.setContentsMargins(26, 22, 26, 20); self.corpo.setSpacing(14)
        raiz.addLayout(self.corpo, 1)
        self.rodape = Rodape() if com_rodape else None
        if self.rodape:
            raiz.addWidget(self.rodape)

    def paintEvent(self, e):
        p = QPainter(self)
        sk.pintar_fundo(p, QRectF(self.rect()), 120)


# ===================================================================== processamento

class Trabalho(QThread):
    progresso = Signal(str, float)
    pronto = Signal(dict)
    erro = Signal(str)

    def __init__(self, arquivo: str, opcoes: dict):
        super().__init__()
        self.arquivo, self.opcoes = arquivo, opcoes

    def run(self):
        try:
            p = pj.processar(self.arquivo, progresso=lambda m, f: self.progresso.emit(m, f), **self.opcoes)
            self.pronto.emit(p)
        except Exception as e:
            traceback.print_exc()
            self.erro.emit(str(e) or e.__class__.__name__)


class RotuloIcone(QWidget):
    def __init__(self, icone: str, texto: str):
        super().__init__()
        h = QHBoxLayout(self); h.setContentsMargins(0, 0, 0, 0); h.setSpacing(12)
        ic = QLabel(); ic.setPixmap(sk.icone_pix(icone, VERMELHO, 24)); ic.setFixedWidth(28)
        t = QLabel(texto); t.setFont(fonte(16, QFont.Medium))
        h.addWidget(ic); h.addWidget(t); h.addStretch()


class DialogoNova(DialogoWM):
    def __init__(self, parent, arquivo: str):
        super().__init__(parent, os.path.basename(arquivo), titulo_grande=True)
        self.setWindowTitle("Nova música")
        self.setMinimumWidth(720)
        self.arquivo = arquivo
        grade = QGridLayout(); grade.setHorizontalSpacing(24); grade.setVerticalSpacing(12)
        self.qual = QComboBox(); self.qual.addItems(["Alta (mais lenta)", "Rápida"])
        self.idioma = QComboBox(); self.idioma.addItems(["Português", "Inglês", "Espanhol", "Detectar"])
        self.letra = QCheckBox("Escrever a letra"); self.letra.setChecked(True); self.letra.setFont(fonte(16, QFont.Medium))
        self.timbre = QComboBox(); self.timbre.addItems(["Quente", "Brilhante", "Suave"])
        for c in (self.qual, self.idioma, self.timbre):
            c.setMinimumHeight(40); c.setFont(fonte(16, QFont.Medium))
        grade.addWidget(RotuloIcone("onda", "Qualidade da separação"), 0, 0)
        grade.addWidget(self.qual, 0, 1)
        grade.addWidget(RotuloIcone("idioma", "Idioma da letra"), 1, 0)
        grade.addWidget(self.idioma, 1, 1)
        grade.addWidget(self.letra, 2, 1)
        grade.addWidget(RotuloIcone("teclado", "Timbre do pad"), 3, 0)
        grade.addWidget(self.timbre, 3, 1)
        grade.setColumnStretch(1, 1)
        self.corpo.addLayout(grade)
        self.dica = QPlainTextEdit(); self.dica.setPlaceholderText(
            "Opcional: cole aqui a letra da música. Ajuda a acertar as palavras.")
        self.dica.setMinimumHeight(140)
        self.corpo.addWidget(self.dica)
        ok = Botao("Separar", tipo="vermelho", tam_fonte=18, peso=QFont.Bold); ok.setFixedSize(170, 52)
        no = Botao("Cancelar", tam_fonte=17, peso=QFont.Medium); no.setFixedSize(160, 52)
        self.rodape.lay.addStretch(); self.rodape.lay.addWidget(ok); self.rodape.lay.addWidget(no)
        ok.clicked.connect(self.accept); no.clicked.connect(self.reject)

    def opcoes(self) -> dict:
        idi = {0: "pt", 1: "en", 2: "es", 3: None}[self.idioma.currentIndex()]
        return {"qualidade": "alta" if self.qual.currentIndex() == 0 else "rapida", "idioma": idi,
                "fazer_letra": self.letra.isChecked(), "timbre_pad": self.timbre.currentText(),
                "dica_letra": self.dica.toPlainText().strip() or None}


class DialogoProgresso(DialogoWM):
    def __init__(self, parent, titulo: str):
        super().__init__(parent, "Separação de instrumentos", com_rodape=False)
        self.setWindowTitle("Separando")
        self.setMinimumWidth(720)
        self.setWindowFlag(Qt.WindowCloseButtonHint, False)
        self.corpo.setContentsMargins(32, 22, 32, 32)
        t = QLabel(titulo); t.setFont(fonte(24, QFont.Bold)); self.corpo.addWidget(t)
        self.msg = QLabel("Começando…"); self.msg.setFont(fonte(16)); self.msg.setStyleSheet(f"color:{CINZA};")
        self.corpo.addWidget(self.msg)
        self.barra = QProgressBar(); self.barra.setRange(0, 1000); self.barra.setTextVisible(False)
        self.corpo.addWidget(self.barra)

    def atualizar(self, msg: str, f: float):
        self.msg.setText(msg)
        self.barra.setValue(int(f * 1000))


class DialogoBiblioteca(DialogoWM):
    def __init__(self, parent):
        super().__init__(parent, "Biblioteca", icone="banco")
        self.setWindowTitle("Biblioteca")
        self.resize(680, 600)
        self.escolhido = None
        self.lista = QListWidget()
        self.corpo.addWidget(self.lista)
        b_abrir = Botao("Abrir", "pasta", tipo="vermelho", tam_fonte=17, peso=QFont.Bold)
        b_pasta = Botao("Mostrar pasta", "pasta", tam_fonte=16, peso=QFont.Medium)
        b_apagar = Botao("Apagar", "lixo", tam_fonte=16, peso=QFont.Medium)
        for b in (b_abrir, b_pasta, b_apagar):
            b.setMinimumHeight(48)
        b_abrir.setMinimumWidth(140)
        self.rodape.lay.addWidget(b_abrir); self.rodape.lay.addWidget(b_pasta)
        self.rodape.lay.addStretch(); self.rodape.lay.addWidget(b_apagar)
        b_abrir.clicked.connect(self.abrir)
        self.lista.itemDoubleClicked.connect(lambda *_: self.abrir())
        b_pasta.clicked.connect(self.mostrar)
        b_apagar.clicked.connect(self.apagar)
        self.recarregar()

    def recarregar(self):
        self.lista.clear()
        for p in pj.listar_biblioteca():
            it = QListWidgetItem(f'{p.get("titulo")}   •   {tempo_txt(p.get("duracao", 0))}   •   tom {p.get("tom", "?")}')
            it.setData(Qt.UserRole, p["pasta"])
            self.lista.addItem(it)
        if self.lista.count():
            self.lista.setCurrentRow(0)

    def _atual(self):
        it = self.lista.currentItem()
        return it.data(Qt.UserRole) if it else None

    def abrir(self):
        if self._atual():
            self.escolhido = self._atual()
            self.accept()

    def mostrar(self):
        abrir_no_sistema(self._atual() or pj.pasta_biblioteca())

    def apagar(self):
        p = self._atual()
        if not p:
            return
        if QMessageBox.question(self, "Apagar", f"Apagar a pasta desta música?\n\n{p}\n\nNão dá para desfazer.") == QMessageBox.Yes:
            jan = self.parent()
            if jan is not None and getattr(jan, "projeto", None) and os.path.normcase(os.path.abspath(jan.projeto["pasta"])) == os.path.normcase(os.path.abspath(p)):
                jan.fechar_projeto()
            shutil.rmtree(p, ignore_errors=True)
            self.recarregar()


# ===================================================================== janela: peças

class Faixa(QWidget):
    """Canal do mixer: nome, M/S, pan, fader com régua e medidor, valor e saída."""
    mudou = Signal()

    def __init__(self, chave: str, nome: str, saidas: int):
        super().__init__()
        self.chave = chave
        self.setFixedWidth(156)
        self.cor = CORES.get(chave, CREME)
        self.nome = nome
        lay = QVBoxLayout(self); lay.setContentsMargins(14, 44, 14, 20); lay.setSpacing(8)
        h = QHBoxLayout(); h.setSpacing(10); h.addStretch()
        self.m = Botao("M", tam_fonte=16, peso=QFont.Bold, ligado="vermelho"); self.m.setCheckable(True)
        self.s = Botao("S", tam_fonte=16, peso=QFont.Bold, ligado="ambar"); self.s.setCheckable(True)
        for b in (self.m, self.s):
            b.setFixedSize(52, 40)
        h.addWidget(self.m); h.addWidget(self.s); h.addStretch()
        lay.addLayout(h)
        self.pan = sk.Pan(); lay.addWidget(self.pan)
        self.fader = sk.Fader(); lay.addWidget(self.fader, 1, Qt.AlignHCenter)
        self.valor = QLabel("0.0 dB"); self.valor.setAlignment(Qt.AlignCenter); self.valor.setFont(fonte(16, QFont.Medium))
        lay.addWidget(self.valor)
        self.saida = QComboBox(); self.saida.setObjectName("vermelha"); self.saida.setMinimumHeight(34)
        self.saida.setFont(fonte(15, QFont.Medium))
        self.definir_saidas(saidas)
        self.saida.setToolTip("Saída da placa de som")
        lay.addWidget(self.saida)
        self.m.toggled.connect(lambda *_: self.mudou.emit())
        self.s.toggled.connect(lambda *_: self.mudou.emit())
        self.pan.mudou.connect(lambda *_: self.mudou.emit())
        self.fader.mudou.connect(self._fader)
        self.saida.currentIndexChanged.connect(lambda *_: self.mudou.emit())

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(4, 4, -4, -5)
        sk.pintar_painel(p, r, 10, laterais_vermelhas=True)
        p.save()
        g = QLinearGradient(QPointF(r.center().x() - 36, 0), QPointF(r.center().x() + 36, 0))
        g.setColorAt(0, QColor(255, 255, 255, 0)); g.setColorAt(0.5, QColor(255, 255, 255, 55)); g.setColorAt(1, QColor(255, 255, 255, 0))
        p.setPen(QPen(QBrush(g), 1.4))
        p.drawArc(QRectF(r.center().x() - 36, r.top() + 6, 72, 44), 30 * 16, 120 * 16)
        p.restore()
        p.setFont(fonte(19, QFont.Bold))
        sk.texto_brilho(p, QRectF(r.left(), r.top() + 9, r.width(), 30), Qt.AlignCenter, self.nome, self.cor, 70)

    def definir_saidas(self, canais: int):
        atual = max(0, self.saida.currentIndex())
        self.saida.blockSignals(True)
        self.saida.clear()
        for i in range(max(1, canais // 2)):
            self.saida.addItem(f"{2*i+1}-{2*i+2}")
        self.saida.setCurrentIndex(min(atual, self.saida.count() - 1))
        self.saida.blockSignals(False)

    def _fader(self, db):
        self.valor.setText("−∞" if db <= -60 else f"{db:+.1f} dB".replace("+0.0", "0.0").replace("-", "−"))
        self.mudou.emit()

    def aplicar(self, t):
        t.volume = db_para_lin(self.fader.db)
        t.pan = self.pan.valor
        t.mute = self.m.isChecked()
        t.solo = self.s.isChecked()
        t.saida = max(0, self.saida.currentIndex())

    def carregar(self, t):
        for w in (self.m, self.s, self.saida):
            w.blockSignals(True)
        self.m.setChecked(t.mute); self.s.setChecked(t.solo)
        self.pan.definir(t.pan)
        self.fader.definir(-100 if t.volume <= 0 else 20 * np.log10(t.volume))
        self.saida.setCurrentIndex(min(t.saida, self.saida.count() - 1))
        for w in (self.m, self.s, self.saida):
            w.blockSignals(False)
        self._fader(self.fader.db)


class Onda(QWidget):
    """Forma de onda, acordes em cima, cursor, clique para ir, arraste para loop."""
    ir = Signal(float)
    loop = Signal(object)

    def __init__(self):
        super().__init__()
        self.setMinimumHeight(150)
        self.picos = None
        self.dur = 1.0
        self.pos = 0.0
        self.acordes = []
        self.loop_s = None
        self._arraste = None

    def definir(self, picos, dur, acordes):
        self.picos, self.dur, self.acordes = picos, max(dur, 1e-3), acordes
        self.loop_s = None
        self.update()

    def _area(self):
        return QRectF(self.rect()).adjusted(8, 6, -8, -8)

    def _x(self, s):
        a = self._area()
        return a.left() + s / self.dur * a.width()

    def _s(self, x):
        a = self._area()
        return max(0.0, min(self.dur, (x - a.left()) / max(1, a.width()) * self.dur))

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        a = self._area()
        sk.pintar_painel(p, a.adjusted(-4, -2, 4, 2), 10, parafusos=False, fundo_escuro=True)
        p.save()
        cam = QPainterPath(); cam.addRoundedRect(a, 8, 8); p.setClipPath(cam)
        topo = 32
        if self.loop_s:
            x0, x1 = self._x(self.loop_s[0]), self._x(self.loop_s[1])
            p.fillRect(QRectF(x0, a.top(), x1 - x0, a.height()), QColor(225, 38, 44, 60))
            p.setPen(QPen(QColor(225, 38, 44, 130), 1))
            p.drawLine(QPointF(x0, a.top()), QPointF(x0, a.bottom())); p.drawLine(QPointF(x1, a.top()), QPointF(x1, a.bottom()))
        if self.picos is not None and len(self.picos):
            meio = a.top() + topo + (a.height() - topo) / 2
            amp = (a.height() - topo) / 2 - 8
            n = len(self.picos)
            xp = self._x(self.pos)
            w = int(a.width())
            for i in range(w):
                x = a.left() + i
                v = self.picos[min(n - 1, int(i / w * n))]
                if x <= xp:
                    cor = QColor("#f3e6d2")
                elif self.loop_s and self._x(self.loop_s[0]) <= x <= self._x(self.loop_s[1]):
                    cor = QColor("#8a6a66")
                else:
                    cor = QColor("#5a5550")
                p.setPen(cor)
                p.drawLine(QPointF(x, meio - v * amp), QPointF(x, meio + v * amp))
        p.setFont(fonte(16, QFont.DemiBold))
        for c in self.acordes:
            if c["nome"] == "N":
                continue
            x0, x1 = self._x(c["t0"]), self._x(c["t1"])
            p.setPen(QPen(QColor(255, 255, 255, 30), 1)); p.drawLine(QPointF(x0, a.top()), QPointF(x0, a.top() + topo + 6))
            if x1 - x0 > 24:
                ativo = c["t0"] <= self.pos < c["t1"]
                p.setPen(QColor(VERMELHO if ativo else "#d8cfc4"))
                p.drawText(QRectF(x0 + 10, a.top() + 2, x1 - x0 - 10, topo), Qt.AlignVCenter | Qt.AlignLeft, c["nome"])
        if self.picos is not None:
            x = self._x(self.pos)
            for w_, al in ((8, 35), (4, 80), (2, 255)):
                cc = QColor(VERMELHO); cc.setAlpha(al)
                p.setPen(QPen(cc, w_)); p.drawLine(QPointF(x, a.top()), QPointF(x, a.bottom()))
        else:
            for w_, al in ((5, 50), (2, 255)):
                cc = QColor(VERMELHO); cc.setAlpha(al)
                p.setPen(QPen(cc, w_)); p.drawLine(QPointF(a.left() + 3, a.top() + 4), QPointF(a.left() + 3, a.bottom() - 4))
        p.restore()

    def mousePressEvent(self, e):
        if self.picos is not None:
            self._arraste = e.position().x()

    def mouseMoveEvent(self, e):
        if self._arraste is not None and abs(e.position().x() - self._arraste) > 6:
            a, b = sorted((self._s(self._arraste), self._s(e.position().x())))
            self.loop_s = (a, b); self.update()

    def mouseReleaseEvent(self, e):
        if self._arraste is None:
            return
        if abs(e.position().x() - self._arraste) <= 6:
            self.ir.emit(self._s(e.position().x()))
        elif self.loop_s and self.loop_s[1] - self.loop_s[0] > 0.2:
            self.loop.emit(self.loop_s)
            self.ir.emit(self.loop_s[0])
        self._arraste = None


class Letra(QWidget):
    """Linha atual grande com a palavra cantada acesa; anterior e próxima em cinza.
    Sem música aberta, mostra a marca no centro (tela inicial)."""

    def __init__(self):
        super().__init__()
        self.linhas = []
        self.t = 0.0
        self.setMinimumHeight(200)
        self.aviso = ""
        self.vazio = True

    def definir(self, letra, aviso=None):
        self.vazio = False
        self.linhas = (letra or {}).get("linhas", [])
        self.aviso = aviso or ("Sem letra nesta música." if not self.linhas else "")
        self.update()

    def _indice(self):
        t = self.t + 0.15
        idx = -1
        for i, l in enumerate(self.linhas):
            if l["t0"] <= t:
                idx = i
            else:
                break
        return idx

    def _arcos(self, p, r):
        """Dois filetes vermelhos curvos, um no canto de cima à esquerda e outro embaixo à direita."""
        p.save()
        cam = QPainterPath(); cam.addRoundedRect(r, 12, 12); p.setClipPath(cam)
        L, T, W, H = r.left(), r.top(), r.width(), r.height()
        curvas = (((L - 2, T + 0.26 * H), (L + 0.05 * W, T + 0.02 * H), (L + 0.24 * W, T - 2)),
                  ((r.right() + 2, T + 0.60 * H), (r.right() - 0.05 * W, r.bottom() - 0.05 * H), (L + 0.70 * W, r.bottom() + 2)))
        for a, c, b in curvas:
            cp = QPainterPath(QPointF(*a)); cp.quadTo(QPointF(*c), QPointF(*b))
            for w_, al in ((12, 14), (6, 40), (2, 230)):
                cor = QColor(VERMELHO); cor.setAlpha(al)
                p.setPen(QPen(cor, w_, Qt.SolidLine, Qt.RoundCap)); p.setBrush(Qt.NoBrush)
                p.drawPath(cp)
        p.restore()

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing); p.setRenderHint(QPainter.SmoothPixmapTransform)
        r = QRectF(self.rect()).adjusted(4, 4, -4, -5)
        sk.pintar_painel(p, r, 12, parafusos=False, brilho_vermelho=not self.vazio)
        if self.vazio:
            self._arcos(p, r.adjusted(2, 2, -2, -2))
            pm = pix("logo-wmusic.png")
            h = min(r.height() * 0.40, 240)
            w = pm.width() * h / pm.height() if not pm.isNull() else 0
            y = r.center().y() - h * 0.82
            if not pm.isNull():
                p.drawPixmap(QRectF(r.center().x() - w / 2, y, w, h), pm, QRectF(pm.rect()))
            y += h + 10
            f = fonte(min(48, r.height() * 0.085), QFont.ExtraBold, min(18, r.height() * 0.03))
            p.setFont(f)
            fm = QFontMetricsF(f)
            tw = fm.horizontalAdvance("STEAMS")
            gt = QLinearGradient(QPointF(0, y), QPointF(0, y + fm.height()))
            gt.setColorAt(0, QColor("#ffffff")); gt.setColorAt(0.6, QColor("#d8d0c6")); gt.setColorAt(1, QColor("#8f8a84"))
            p.setPen(QPen(QBrush(gt), 1))
            p.drawText(QRectF(r.left(), y, r.width(), fm.height()), Qt.AlignHCenter | Qt.AlignVCenter, "STEAMS")
            ly = y + fm.height() / 2
            for x0, x1 in ((r.center().x() - tw / 2 - 160, r.center().x() - tw / 2 - 30),
                           (r.center().x() + tw / 2 + 30, r.center().x() + tw / 2 + 160)):
                g = QLinearGradient(QPointF(x0, ly), QPointF(x1, ly))
                fora = x0 < r.center().x()
                g.setColorAt(0, QColor(225, 38, 44, 0 if fora else 230)); g.setColorAt(1, QColor(225, 38, 44, 230 if fora else 0))
                p.setPen(QPen(QBrush(g), 2)); p.drawLine(QPointF(x0, ly), QPointF(x1, ly))
            p.setFont(fonte(min(28, r.height() * 0.048)))
            p.setPen(QColor("#b9b1a8"))
            p.drawText(QRectF(r.left(), y + fm.height() + 16, r.width(), 44), Qt.AlignHCenter | Qt.AlignTop, "Abra uma música para começar")
            return
        if not self.linhas:
            p.setPen(QColor("#b9b1a8")); p.setFont(fonte(26))
            p.drawText(r, Qt.AlignCenter, self.aviso)
            return
        i = self._indice()
        h = r.height()

        def linha_simples(txt, y, tam, cor):
            p.setFont(fonte(tam, QFont.Medium)); p.setPen(QColor(cor))
            p.drawText(QRectF(r.left() + 20, r.top() + y, r.width() - 40, tam * 1.6), Qt.AlignHCenter | Qt.AlignVCenter, txt)

        if i - 1 >= 0:
            linha_simples(self.linhas[i - 1]["texto"], h * 0.07, 23, "#b3aba2")
        if i + 1 < len(self.linhas):
            linha_simples(self.linhas[i + 1]["texto"], h * 0.68, 25, "#c9c1b7")
        if i < 0:
            linha_simples(self.linhas[0]["texto"], h * 0.38, 28, "#8a837b")
            return
        atual = self.linhas[i]
        tam = 42
        f = fonte(tam, QFont.Bold)
        fm = QFontMetricsF(f)
        palavras = atual["palavras"]
        larg = sum(fm.horizontalAdvance(w["w"] + " ") for w in palavras)
        while larg > r.width() - 60 and tam > 16:
            tam -= 1; f = fonte(tam, QFont.Bold); fm = QFontMetricsF(f)
            larg = sum(fm.horizontalAdvance(w["w"] + " ") for w in palavras)
        p.setFont(f)
        x = r.left() + (r.width() - larg) / 2
        y = r.top() + h * 0.34
        for w in palavras:
            cantada = self.t + 0.05 >= w["t0"] and self.t < atual["t1"] + 0.6
            lw = fm.horizontalAdvance(w["w"])
            rr = QRectF(x, y, lw + 6, fm.height())
            if cantada:
                sk.texto_brilho(p, rr, Qt.AlignLeft | Qt.AlignVCenter, w["w"], "#ff2b30", 150)
            else:
                p.setPen(QColor("#f6ead9")); p.drawText(rr, Qt.AlignLeft | Qt.AlignVCenter, w["w"])
            x += fm.horizontalAdvance(w["w"] + " ")


class PainelAcorde(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedWidth(276)
        self.vazio = True
        self.acorde, self.prox, self.tom = "–", "", ""
        lay = QVBoxLayout(self); lay.setContentsMargins(26, 0, 22, 22); lay.addStretch()
        h = QHBoxLayout()
        lp = QLabel("Pad"); lp.setFont(fonte(16, QFont.Medium))
        self.timbre = QComboBox(); self.timbre.addItems(["Quente", "Brilhante", "Suave"]); self.timbre.setObjectName("vermelha")
        self.timbre.setMinimumHeight(38); self.timbre.setFont(fonte(16, QFont.Medium)); self.timbre.setFixedWidth(132)
        h.addWidget(lp); h.addStretch(); h.addWidget(self.timbre)
        lay.addLayout(h)

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(4, 4, -4, -5)
        sk.pintar_painel(p, r, 12)
        x = r.left() + 22
        p.setFont(fonte(17, QFont.DemiBold, 0.5)); p.setPen(QColor(CREME))
        p.drawText(QRectF(x, r.top() + 14, 200, 28), Qt.AlignLeft | Qt.AlignVCenter, "ACORDE")
        if self.vazio:
            g = QLinearGradient(QPointF(x, 0), QPointF(x + 90, 0))
            g.setColorAt(0, QColor(225, 38, 44, 0)); g.setColorAt(0.4, QColor(225, 38, 44, 255)); g.setColorAt(1, QColor(225, 38, 44, 0))
            p.setPen(QPen(QBrush(g), 2)); p.drawLine(QPointF(x, r.top() + 48), QPointF(x + 90, r.top() + 48))
            p.setPen(Qt.NoPen); p.setBrush(QColor(VERMELHO)); p.drawRect(QRectF(x, r.top() + 90, 30, 7))
            p.setPen(QPen(QColor(255, 255, 255, 30), 1)); p.drawLine(QPointF(x, r.bottom() - 80), QPointF(r.right() - 20, r.bottom() - 80))
            return
        p.setFont(fonte(62, QFont.Black))
        sk.texto_brilho(p, QRectF(x, r.top() + 40, r.width() - 40, 74), Qt.AlignLeft | Qt.AlignVCenter, self.acorde, "#ff2b30", 120)
        p.setFont(fonte(20)); p.setPen(QColor("#d8cfc4"))
        p.drawText(QRectF(x, r.top() + 114, 230, 30), Qt.AlignLeft | Qt.AlignVCenter, self.prox)
        p.setFont(fonte(16)); p.setPen(QColor(CINZA))
        p.drawText(QRectF(x, r.top() + 146, 230, 24), Qt.AlignLeft | Qt.AlignVCenter, self.tom)


class BarraTransporte(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedHeight(86)
        self.lay = QHBoxLayout(self); self.lay.setContentsMargins(22, 12, 22, 14); self.lay.setSpacing(14)

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(4, 4, -4, -5)
        sk.pintar_painel(p, r, 10)
        g = QLinearGradient(r.topLeft(), r.topRight())
        g.setColorAt(0.3, QColor(255, 255, 255, 0)); g.setColorAt(0.5, QColor(255, 255, 255, 50)); g.setColorAt(0.7, QColor(255, 255, 255, 0))
        p.setPen(QPen(QBrush(g), 1)); p.drawLine(QPointF(r.left() + 20, r.top() + 1.5), QPointF(r.right() - 20, r.top() + 1.5))


class Separador(QWidget):
    def __init__(self, altura=44):
        super().__init__(); self.setFixedWidth(2); self.setFixedHeight(altura)

    def paintEvent(self, e):
        p = QPainter(self)
        p.fillRect(QRectF(0, 0, 1, self.height()), QColor(0, 0, 0, 200))
        p.fillRect(QRectF(1, 0, 1, self.height()), QColor(255, 255, 255, 28))


# ===================================================================== janela

class Janela(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("WMusic Steams")
        self.resize(1530, 1030)
        self.setMinimumSize(1100, 760)
        self.motor = Motor()
        self.projeto = None
        self.trabalho = None
        self.faixas: list[Faixa] = []

        central = Fundo(); self.setCentralWidget(central)
        raiz = QVBoxLayout(central); raiz.setContentsMargins(0, 0, 0, 0); raiz.setSpacing(0)

        self.cab = Cabecalho(84)
        self.cab.lay.addWidget(Logo(54))
        self.cab.lay.addSpacing(10); self.cab.lay.addWidget(Separador()); self.cab.lay.addSpacing(16)
        v = QVBoxLayout(); v.setSpacing(2)
        self.titulo = QLabel("Abra uma música para começar"); self.titulo.setFont(fonte(22, QFont.Medium))
        self.sub = QLabel(""); self.sub.setFont(fonte(14)); self.sub.setStyleSheet(f"color:{CINZA};")
        v.addStretch(); v.addWidget(self.titulo); v.addWidget(self.sub); v.addStretch()
        self.cab.lay.addLayout(v); self.cab.lay.addStretch()
        b_nova = Botao("Nova música", "mais", tipo="vermelho", tam_fonte=16, peso=QFont.Medium); b_nova.clicked.connect(self.nova)
        b_bib = Botao("Biblioteca", "pasta", tam_fonte=16, peso=QFont.Medium); b_bib.clicked.connect(self.biblioteca)
        self.b_exp = Botao("Exportar", "exportar", tam_fonte=16, peso=QFont.Medium); self.b_exp.clicked.connect(self.exportar)
        self.b_exp.setEnabled(False)
        for b in (b_nova, b_bib, self.b_exp):
            b.setMinimumHeight(50); self.cab.lay.addWidget(b)
        raiz.addWidget(self.cab)

        self.corpo = QVBoxLayout(); self.corpo.setContentsMargins(14, 12, 14, 10); self.corpo.setSpacing(8)
        raiz.addLayout(self.corpo, 1)

        self.meio = QHBoxLayout(); self.meio.setSpacing(10)
        col = QVBoxLayout(); col.setSpacing(0)
        self.p_acorde = PainelAcorde()
        self.timbre = self.p_acorde.timbre
        self.timbre.currentTextChanged.connect(self.trocar_timbre)
        col.addWidget(self.p_acorde); col.addStretch()
        self.meio.addLayout(col)
        self.letra = Letra(); self.meio.addWidget(self.letra, 1)
        self.corpo.addLayout(self.meio, 0)

        self.area = QScrollArea(); self.area.setWidgetResizable(True)
        self.area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.area.setFrameShape(QFrame.NoFrame)
        self.area.viewport().setAutoFillBackground(False)
        self.mixer = QWidget(); self.mixer.setAutoFillBackground(False)
        self.mixer_lay = QHBoxLayout(self.mixer)
        self.mixer_lay.setContentsMargins(0, 0, 0, 0); self.mixer_lay.setSpacing(2); self.mixer_lay.addStretch()
        self.area.setWidget(self.mixer)
        self.area.setMinimumHeight(420)
        self.area.setStyleSheet("QScrollArea { background: transparent; } QScrollArea > QWidget > QWidget { background: transparent; }")
        self.corpo.addWidget(self.area, 1)

        self.onda = Onda(); self.onda.ir.connect(self.ir_para); self.onda.loop.connect(self.definir_loop)
        self.corpo.addWidget(self.onda)
        self.tr = BarraTransporte()
        L = self.tr.lay
        self.b_inicio = Botao("", "inicio"); self.b_inicio.setFixedSize(72, 52); self.b_inicio.clicked.connect(lambda: self.ir_para(0))
        self.b_play = Botao("Tocar", "tocar", tipo="vermelho", tam_fonte=19, peso=QFont.DemiBold); self.b_play.setFixedSize(166, 56)
        self.b_play.clicked.connect(self.tocar_pausar)
        self.b_parar = Botao("", "parar"); self.b_parar.setFixedSize(58, 52); self.b_parar.clicked.connect(self.parar)
        self.b_loop = Botao("Loop", "loop", tam_fonte=17, peso=QFont.DemiBold); self.b_loop.setCheckable(True); self.b_loop.setFixedSize(128, 52)
        self.b_loop.toggled.connect(self.alternar_loop)
        self.b_loop.setToolTip("Arraste na forma de onda para marcar o trecho")
        self.relogio = QLabel("0:00.0 / 0:00.0"); self.relogio.setFont(sk.fonte_mono(22))
        self.relogio.setStyleSheet("color:#e9dfd2;")
        for w in (self.b_inicio, self.b_play, self.b_parar, self.b_loop):
            L.addWidget(w)
        L.addSpacing(8); L.addWidget(self.relogio); L.addSpacing(8); L.addWidget(Separador()); L.addStretch()
        lm = QLabel("Master"); lm.setFont(fonte(17, QFont.Medium))
        self.master = sk.Pan(mestre=True); self.master.setFixedWidth(240); self.master.definir(0.82)
        self.master.mudou.connect(self._master)
        ls = QLabel("Saída"); ls.setFont(fonte(17, QFont.Medium))
        self.disp = QComboBox(); self.disp.setObjectName("vermelha"); self.disp.setMinimumWidth(320); self.disp.setMinimumHeight(42)
        self.disp.setFont(fonte(16, QFont.Medium))
        self.disp.addItem("Padrão do sistema", None)
        for d in Motor.dispositivos():
            self.disp.addItem(f'{d["nome"]} · {d["canais"]} canais', d["indice"])
        self.disp.currentIndexChanged.connect(self.trocar_dispositivo)
        L.addWidget(lm); L.addWidget(self.master); L.addSpacing(16); L.addWidget(ls); L.addWidget(self.disp)
        self.corpo.addWidget(self.tr)

        QShortcut(QKeySequence(Qt.Key_Space), self, activated=self.tocar_pausar)
        QShortcut(QKeySequence(Qt.Key_Home), self, activated=lambda: self.ir_para(0))
        self.relogio_timer = QTimer(self); self.relogio_timer.timeout.connect(self.tique); self.relogio_timer.start(33)
        self.setAcceptDrops(True)
        self._modo_vazio(True)

    def _master(self, v):
        db = -60 + v / 0.82 * 60 if v <= 0.82 else (v - 0.82) / 0.18 * 6
        self.motor.master = db_para_lin(db)

    def _modo_vazio(self, vazio: bool):
        """Sem música: letra vira a tela de boas-vindas e o mixer some (como na arte)."""
        self.area.setVisible(not vazio)
        self.p_acorde.vazio = vazio
        self.letra.vazio = vazio
        self.corpo.setStretchFactor(self.meio, 1 if vazio else 0)
        if vazio:
            self.letra.setMinimumHeight(380); self.letra.setMaximumHeight(16777215)
            self.p_acorde.setFixedHeight(276)
        else:
            self.letra.setMinimumHeight(200); self.letra.setMaximumHeight(236)
            self.p_acorde.setFixedHeight(236)
        self.onda.setFixedHeight(172 if vazio else 150)

    # ---------------------------------------------------------------- ações
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        urls = e.mimeData().urls()
        if urls:
            self.nova(urls[0].toLocalFile())

    def nova(self, arquivo: str | None = None):
        if self.trabalho:
            return
        if not arquivo:
            arquivo, _ = QFileDialog.getOpenFileName(
                self, "Escolha a música", os.path.expanduser("~"),
                "Áudio e vídeo (*.mp3 *.wav *.flac *.m4a *.aac *.ogg *.mp4 *.mov *.mkv *.aif *.aiff);;Todos (*)")
        if not arquivo:
            return
        d = DialogoNova(self, arquivo)
        if d.exec() != QDialog.Accepted:
            return
        self.parar()
        self.prog = DialogoProgresso(self, os.path.basename(arquivo))
        self.trabalho = Trabalho(arquivo, d.opcoes())
        self.trabalho.progresso.connect(self.prog.atualizar)
        self.trabalho.pronto.connect(self._pronto)
        self.trabalho.erro.connect(self._erro)
        self.trabalho.start()
        self.prog.show()

    def _pronto(self, projeto):
        self.prog.close(); self.trabalho = None
        self.abrir_projeto(projeto)
        if projeto.get("aviso_letra"):
            QMessageBox.information(self, "Letra", projeto["aviso_letra"])

    def _erro(self, msg):
        self.prog.close(); self.trabalho = None
        QMessageBox.critical(self, "Não deu certo", msg)

    def biblioteca(self):
        d = DialogoBiblioteca(self)
        if d.exec() == QDialog.Accepted and d.escolhido:
            try:
                self.abrir_projeto(pj.carregar(d.escolhido))
            except Exception as e:
                QMessageBox.critical(self, "Não abriu", str(e))

    def abrir_projeto(self, projeto, manter_pos=False):
        self.salvar_mixer()
        pos = self.motor.segundos if manter_pos else 0.0
        self.projeto = projeto
        self.motor.carregar(projeto)
        if manter_pos:
            self.motor.ir_para(pos)
        self._modo_vazio(False)
        self.titulo.setText(projeto["titulo"])
        r = projeto.get("relatorio", {})
        self.sub.setText(f'{tempo_txt(projeto["duracao"])}   ·   {projeto["taxa"]} Hz   ·   '
                         f'soma dos stems = original ({r.get("nulo_db", "?")} dB)'.replace("-", "−"))
        self.p_acorde.tom = f'Tom: {projeto.get("tom", "?")}'
        self.timbre.blockSignals(True); self.timbre.setCurrentText(projeto.get("pad_timbre", "Quente")); self.timbre.blockSignals(False)
        self.letra.definir(projeto.get("letra"), projeto.get("aviso_letra"))
        for f in self.faixas:
            f.setParent(None); f.deleteLater()
        self.faixas = []
        canais = self.canais_dispositivo()
        for t in self.motor.trilhas:
            f = Faixa(t.chave, pj.NOMES_TELA.get(t.chave, t.chave), canais)
            f.carregar(t)
            f.mudou.connect(self.aplicar_mixer)
            self.mixer_lay.insertWidget(self.mixer_lay.count() - 1, f)
            self.faixas.append(f)
        orig, _ = pj.abrir_wav_float(os.path.join(projeto["pasta"], "original.wav"))
        n = len(orig); k = max(1, n // 3000)
        bloco = np.abs(np.asarray(orig[: (n // k) * k], np.float32)).max(axis=1).reshape(-1, k).max(axis=1)
        self.onda.definir(bloco / (bloco.max() or 1), projeto["duracao"], projeto.get("acordes", []))
        self.b_exp.setEnabled(True)
        self.b_loop.setChecked(False)

    def fechar_projeto(self):
        self.salvar_mixer()
        self.motor.descarregar()
        self.projeto = None
        for f in self.faixas:
            f.setParent(None); f.deleteLater()
        self.faixas = []
        self.onda.definir(None, 1.0, [])
        self.titulo.setText("Abra uma música para começar"); self.sub.setText("")
        self.b_exp.setEnabled(False)
        self._modo_vazio(True)

    def canais_dispositivo(self) -> int:
        try:
            import sounddevice as sd
            return int(sd.query_devices(self.disp.currentData(), "output")["max_output_channels"])
        except Exception:
            return 2

    def trocar_dispositivo(self, *_):
        tocando = self.motor.tocando
        self.motor.pausar()
        self.motor.escolher_dispositivo(self.disp.currentData())
        for f in self.faixas:
            f.definir_saidas(self.canais_dispositivo())
        self.aplicar_mixer()
        if tocando:
            self.tocar_pausar()

    def aplicar_mixer(self):
        for f in self.faixas:
            t = self.motor.trilha(f.chave)
            if t:
                f.aplicar(t)

    def salvar_mixer(self):
        if self.projeto:
            self.projeto["mixer"] = self.motor.estado_mixer()
            try:
                pj.salvar(self.projeto)
            except Exception:
                pass

    def tocar_pausar(self):
        if not self.projeto:
            return
        if self.motor.tocando:
            self.motor.pausar()
        else:
            try:
                self.motor.tocar()
            except Exception as e:
                QMessageBox.critical(self, "Placa de som", f"Não consegui abrir a saída de áudio:\n{e}")

    def parar(self):
        self.motor.parar()

    def ir_para(self, s):
        self.motor.ir_para(s)

    def definir_loop(self, ab):
        a, b = ab
        self.motor.loop = (int(a * self.motor.taxa), int(b * self.motor.taxa))
        self.b_loop.blockSignals(True); self.b_loop.setChecked(True); self.b_loop.blockSignals(False)

    def alternar_loop(self, ligado):
        if ligado and self.onda.loop_s:
            self.definir_loop(self.onda.loop_s)
        elif ligado:
            self.b_loop.blockSignals(True); self.b_loop.setChecked(False); self.b_loop.blockSignals(False)
            QMessageBox.information(self, "Loop", "Arraste na forma de onda para marcar o trecho.")
        else:
            self.motor.loop = None

    def trocar_timbre(self, timbre):
        if not self.projeto:
            return
        try:
            tocando = self.motor.tocando
            pos = self.motor.segundos
            self.salvar_mixer()
            self.motor.descarregar()
            pj.regerar_pad(self.projeto, timbre)
            self.abrir_projeto(self.projeto)
            self.motor.ir_para(pos)
            if tocando:
                self.motor.tocar()
        except Exception as e:
            QMessageBox.critical(self, "Pad", str(e))

    def tique(self):
        m = self.motor
        s = m.segundos
        dur = self.projeto["duracao"] if self.projeto else 0
        self.relogio.setText(f"{tempo_txt(s)} / {tempo_txt(dur)}")
        tocando = m.tocando
        if self.b_play.text() != ("Pausar" if tocando else "Tocar"):
            self.b_play.setText("Pausar" if tocando else "Tocar")
            self.b_play.definir_icone("pausar" if tocando else "tocar")
        self.onda.pos = s; self.onda.update()
        self.letra.t = s; self.letra.update()
        for f in self.faixas:
            t = m.trilha(f.chave)
            if t:
                if not tocando:
                    t.pico *= 0.8
                f.fader.nivel = t.pico; f.fader.update()
        if self.projeto:
            ac = self.projeto.get("acordes", [])
            atual = next((a for a in ac if a["t0"] <= s < a["t1"]), None)
            self.p_acorde.acorde = atual["nome"] if atual and atual["nome"] != "N" else "–"
            prox = next((a for a in ac if a["t0"] > s and a["nome"] != "N"), None)
            self.p_acorde.prox = f'depois: {prox["nome"]}' if prox else ""
            self.p_acorde.update()

    def exportar(self):
        if not self.projeto:
            return
        destino = QFileDialog.getExistingDirectory(self, "Exportar para qual pasta?", os.path.expanduser("~"))
        if not destino:
            return
        try:
            pasta = exportar_projeto(self.projeto, destino)
            QMessageBox.information(self, "Exportado", f"Stems, letra e acordes em:\n{pasta}")
            abrir_no_sistema(pasta)
        except Exception as e:
            QMessageBox.critical(self, "Exportar", str(e))

    def closeEvent(self, e):
        self.salvar_mixer()
        self.motor.fechar()
        super().closeEvent(e)


def exportar_projeto(projeto: dict, destino: str) -> str:
    """WAV 24 bits de cada trilha (todos com o mesmo início e comprimento), .lrc e acordes."""
    import soundfile as sf
    from .lyrics import para_lrc
    pasta = os.path.join(destino, pj.nome_seguro(projeto["titulo"]) + " - WMusic Steams")
    os.makedirs(pasta, exist_ok=True)
    for i, k in enumerate(projeto["trilhas"], 1):
        a, sr = pj.abrir_wav_float(os.path.join(projeto["pasta"], k + ".wav"))
        sub = "PCM_24" if float(np.max(np.abs(a))) <= 1.0 else "FLOAT"
        sf.write(os.path.join(pasta, f"{i:02d} {pj.NOMES_TELA.get(k, k)}.wav"), np.asarray(a), sr, subtype=sub)
    if projeto.get("letra", {}).get("linhas"):
        with open(os.path.join(pasta, "Letra.lrc"), "w", encoding="utf-8") as f:
            f.write(para_lrc(projeto["letra"]))
    with open(os.path.join(pasta, "Acordes.txt"), "w", encoding="utf-8") as f:
        f.write(f'Tom: {projeto.get("tom", "?")}\n\n')
        for a in projeto.get("acordes", []):
            if a["nome"] != "N":
                f.write(f'{tempo_txt(a["t0"]):>8}  {a["nome"]}\n')
    return pasta


def preparar_app(app: QApplication):
    sk.carregar_fontes()
    app.setStyleSheet(sk.estilo_global())
    ic = sk.recurso("icone.png")
    if os.path.exists(ic):
        app.setWindowIcon(QIcon(ic))


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("WMusic Steams")
    app.setOrganizationName("WMusic")
    preparar_app(app)
    j = Janela()
    j.show()
    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
        if os.path.exists(os.path.join(sys.argv[1], "projeto.json")):
            j.abrir_projeto(pj.carregar(sys.argv[1]))
    return app.exec()
