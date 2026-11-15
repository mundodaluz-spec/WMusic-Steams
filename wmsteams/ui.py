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
                               QGridLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
                               QMainWindow, QMessageBox, QPlainTextEdit, QProgressBar, QScrollArea,
                               QVBoxLayout, QWidget)

from . import projeto as pj
from . import skin as sk
from .player import Motor
from . import smpte as tc
from .skin import CREME, VERMELHO, CINZA, Botao, fonte, pix

CORES = {
    "voz": "#F0353A", "bateria": "#F2E3CF", "baixo": "#F2A12E", "guitarra": "#E6C27A",
    "teclas": "#8EC5EA", "outros": "#A99BF0", "instrumental": "#E6C27A", "pad": "#6FE0A8",
    "smpte": "#7FD7FF", "original": "#9a938c",
    "backs": "#FF8A7A", "sopros": "#F5D547", "bumbo": "#EDE1D0", "caixa": "#E2D3BF", "tons": "#D6C5AE",
    "chimbal": "#CBB89E", "pratos": "#BFAB8F",
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
        self.qual = QComboBox(); self.qual.addItems(["Alta: voz RoFormer + 6 stems (mais lenta)", "Rápida: só 6 stems"])
        self.idioma = QComboBox(); self.idioma.addItems(["Português", "Inglês", "Espanhol", "Detectar"])
        self.letra = QCheckBox("Escrever a letra"); self.letra.setChecked(True); self.letra.setFont(fonte(16, QFont.Medium))
        cfg = pj.ler_config().get("separacao", {})
        self.backs = QCheckBox("Separar voz principal e backs"); self.backs.setChecked(cfg.get("backs", True))
        self.sopros = QCheckBox("Procurar sopros e metais"); self.sopros.setChecked(cfg.get("sopros", True))
        self.pecas = QCheckBox("Bateria por peça (bumbo, caixa, tons, chimbal, pratos)"); self.pecas.setChecked(cfg.get("bateria_pecas", False))
        for c in (self.backs, self.sopros, self.pecas):
            c.setFont(fonte(15, QFont.Medium))
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
        grade.addWidget(RotuloIcone("mais", "Canais extras"), 4, 0, Qt.AlignTop)
        extras = QVBoxLayout(); extras.setSpacing(6)
        for c in (self.backs, self.sopros, self.pecas):
            extras.addWidget(c)
        nota = QLabel("Canal que a música não tiver (ex.: sem sopros) nem aparece. Os modelos extras "
                      "são baixados na primeira vez que forem usados.")
        nota.setWordWrap(True); nota.setFont(fonte(12)); nota.setStyleSheet(f"color:{CINZA};")
        extras.addWidget(nota)
        grade.addLayout(extras, 4, 1)
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
        self.dica.setMinimumHeight(110)
        self.layout().activate()
        self.setMinimumHeight(self.sizeHint().height())
        self.resize(max(self.width(), 720), self.sizeHint().height())

    def opcoes(self) -> dict:
        idi = {0: "pt", 1: "en", 2: "es", 3: None}[self.idioma.currentIndex()]
        sep = {"backs": self.backs.isChecked(), "sopros": self.sopros.isChecked(), "bateria_pecas": self.pecas.isChecked()}
        pj.gravar_config({"separacao": sep})
        return {"qualidade": "alta" if self.qual.currentIndex() == 0 else "rapida", "idioma": idi,
                "fazer_letra": self.letra.isChecked(), "timbre_pad": self.timbre.currentText(),
                "dica_letra": self.dica.toPlainText().strip() or None, **sep}


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


class FaixaSMPTE(Faixa):
    """Canal de timecode: liga/desliga, início e fps da música, nível e saída própria."""
    configurar = Signal()

    def __init__(self, saidas: int):
        super().__init__("smpte", "SMPTE", saidas)
        self.s.hide()
        self.pan.hide()
        self.ligado = False
        self.b_cfg = Botao("01:00:00:00", None, tam_fonte=12, peso=QFont.DemiBold)
        self.b_cfg.setFixedHeight(34)
        self.b_cfg.setToolTip("Timecode no início desta música e quadros por segundo")
        self.b_cfg.clicked.connect(self.configurar.emit)
        self.layout().insertWidget(1, self.b_cfg)
        self.b_ligar = Botao("Ligar SMPTE", "relogio", tipo="metal", tam_fonte=13)
        self.b_ligar.setFixedHeight(40)
        self.b_ligar.clicked.connect(self.configurar.emit)
        self.layout().insertWidget(3, self.b_ligar)
        self.fader.definir(-6.0)

    def mostrar(self, cfg: dict | None):
        self.ligado = bool(cfg and cfg.get("ligado"))
        for w in (self.m, self.fader, self.valor, self.saida, self.b_cfg):
            w.setVisible(self.ligado)
        self.b_ligar.setVisible(not self.ligado)
        if self.ligado:
            self.b_cfg.setText(f'{cfg.get("inicio")}')
            self.b_cfg.setToolTip(f'Início {cfg.get("inicio")} · {cfg.get("fps")} fps (clique para mudar)')
            self.m.blockSignals(True); self.m.setChecked(bool(cfg.get("mute"))); self.m.blockSignals(False)
            self.fader.blockSignals(True); self.fader.definir(float(cfg.get("volume_db", -6.0))); self.fader.blockSignals(False)
            self.saida.blockSignals(True); self.saida.setCurrentIndex(min(int(cfg.get("saida", 0)), self.saida.count() - 1)); self.saida.blockSignals(False)
            self._fader(self.fader.db)
        self.update()

    def aplicar(self, t):
        t.volume = db_para_lin(self.fader.db) / 0.5
        t.mute = self.m.isChecked()
        t.saida = max(0, self.saida.currentIndex())

    def carregar(self, t):
        if t is None:
            return
        for w in (self.m, self.saida):
            w.blockSignals(True)
        self.m.setChecked(t.mute)
        self.fader.definir(-100 if t.volume <= 0 else 20 * np.log10(t.volume * 0.5))
        self.saida.setCurrentIndex(min(t.saida, self.saida.count() - 1))
        for w in (self.m, self.saida):
            w.blockSignals(False)
        self._fader(self.fader.db)

    def paintEvent(self, e):
        super().paintEvent(e)
        if not self.ligado:
            p = QPainter(self)
            p.setFont(fonte(13)); p.setPen(QColor(CINZA))
            r = QRectF(self.rect()).adjusted(16, 150, -16, -40)
            p.drawText(r, Qt.AlignHCenter | Qt.AlignTop | Qt.TextWordWrap,
                       "Timecode LTC gerado junto com a música, numa saída da placa.\n\nOpcional.")


class DialogoSMPTE(DialogoWM):
    def __init__(self, parent, cfg: dict, titulo_musica: str):
        super().__init__(parent, "SMPTE · timecode", icone="relogio")
        self.setWindowTitle("SMPTE")
        self.setMinimumWidth(640)
        info = QLabel(f"<b>{titulo_musica}</b>"); info.setFont(fonte(18)); self.corpo.addWidget(info)
        self.ligado = QCheckBox("Gerar timecode SMPTE (LTC) nesta música"); self.ligado.setFont(fonte(16, QFont.Medium))
        self.ligado.setChecked(bool(cfg.get("ligado")))
        self.corpo.addWidget(self.ligado)
        grade = QGridLayout(); grade.setHorizontalSpacing(24); grade.setVerticalSpacing(12)
        self.inicio = QLineEdit(cfg.get("inicio", "01:00:00:00"))
        self.inicio.setInputMask("99:99:99:99")
        self.inicio.setFont(sk.fonte_mono(22)); self.inicio.setMinimumHeight(46)
        self.inicio.setStyleSheet("QLineEdit{background:rgba(8,8,8,220);border:1px solid rgba(225,38,44,140);border-radius:8px;"
                                  "padding:4px 12px;color:#ff4a45;letter-spacing:2px;}")
        self.fps = QComboBox(); self.fps.addItems(list(tc.TAXAS)); self.fps.setCurrentText(cfg.get("fps", "30"))
        self.fps.setMinimumHeight(40); self.fps.setFont(fonte(16, QFont.Medium))
        grade.addWidget(RotuloIcone("relogio", "Timecode no início da música"), 0, 0); grade.addWidget(self.inicio, 0, 1)
        grade.addWidget(RotuloIcone("onda", "Quadros por segundo"), 1, 0); grade.addWidget(self.fps, 1, 1)
        grade.setColumnStretch(1, 1)
        self.corpo.addLayout(grade)
        self.padrao = QCheckBox("Usar estes valores nas próximas músicas"); self.padrao.setFont(fonte(14))
        self.corpo.addWidget(self.padrao)
        dica = QLabel("O timecode anda junto com a música: pular, voltar ou repetir um loop muda o "
                      "timecode no mesmo instante. Escolha a saída do canal SMPTE no mixer (ex.: 7-8) "
                      "e ligue na entrada de timecode da mesa, da luz ou do vídeo.")
        dica.setWordWrap(True); dica.setFont(fonte(13)); dica.setStyleSheet(f"color:{CINZA};")
        self.corpo.addWidget(dica)
        self.erro = QLabel(""); self.erro.setStyleSheet("color:#ff6a62;"); self.corpo.addWidget(self.erro)
        ok = Botao("Salvar", tipo="vermelho", tam_fonte=17, peso=QFont.Bold); ok.setFixedSize(160, 50)
        no = Botao("Cancelar", tam_fonte=16, peso=QFont.Medium); no.setFixedSize(150, 50)
        self.rodape.lay.addStretch(); self.rodape.lay.addWidget(ok); self.rodape.lay.addWidget(no)
        ok.clicked.connect(self._ok); no.clicked.connect(self.reject)
        self.cfg = dict(cfg)

    def _ok(self):
        try:
            ini = tc.validar_tc(self.inicio.text(), self.fps.currentText())
        except ValueError:
            self.erro.setText("Timecode inválido para essa taxa (ex.: 01:00:00:00).")
            return
        self.cfg.update({"ligado": self.ligado.isChecked(), "inicio": ini, "fps": self.fps.currentText()})
        if self.padrao.isChecked():
            pj.gravar_config({"smpte_padrao": {"ligado": self.cfg["ligado"], "inicio": ini, "fps": self.cfg["fps"]}})
        self.accept()


class QRCode(QWidget):
    def __init__(self, texto: str, lado=230):
        super().__init__()
        self.setFixedSize(lado, lado)
        self.definir(texto)

    def definir(self, texto: str):
        try:
            import qrcode
            q = qrcode.QRCode(border=2, error_correction=qrcode.constants.ERROR_CORRECT_M)
            q.add_data(texto); q.make(fit=True)
            self.matriz = q.get_matrix()
        except Exception:
            self.matriz = None
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#f6eee2"))
        if not self.matriz:
            return
        n = len(self.matriz)
        c = self.width() / n
        p.setPen(Qt.NoPen); p.setBrush(QColor("#0b0b0b"))
        for y, linha in enumerate(self.matriz):
            for x, v in enumerate(linha):
                if v:
                    p.drawRect(QRectF(x * c, y * c, c + 0.5, c + 0.5))


class DialogoRemoto(DialogoWM):
    def __init__(self, parent, janela):
        super().__init__(parent, "Controle remoto", icone="wifi")
        self.setWindowTitle("Controle remoto")
        self.setMinimumWidth(760)
        self.j = janela
        h = QHBoxLayout(); h.setSpacing(24)
        self.qr = QRCode("http://0.0.0.0")
        h.addWidget(self.qr, 0, Qt.AlignTop)
        v = QVBoxLayout(); v.setSpacing(10)
        self.status = QLabel(); self.status.setFont(fonte(16, QFont.DemiBold)); v.addWidget(self.status)
        t = QLabel("No iPhone, iPad ou Android, na mesma rede Wi-Fi do computador, aponte a câmera para o "
                   "código ou abra o endereço:")
        t.setWordWrap(True); t.setFont(fonte(14)); t.setStyleSheet(f"color:{CINZA};"); v.addWidget(t)
        self.url = QLabel(); self.url.setFont(sk.fonte_mono(20)); self.url.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.url.setStyleSheet("color:#ff4a45;"); v.addWidget(self.url)
        self.outras = QLabel(); self.outras.setFont(fonte(12)); self.outras.setStyleSheet(f"color:{CINZA};"); self.outras.setWordWrap(True)
        v.addWidget(self.outras)
        hp = QHBoxLayout()
        lp = QLabel("PIN para controlar:"); lp.setFont(fonte(15, QFont.Medium))
        self.pin = QLabel(); self.pin.setFont(sk.fonte_mono(30, QFont.Bold)); self.pin.setStyleSheet("color:#F2E3CF; letter-spacing:6px;")
        b_pin = Botao("Trocar PIN", tam_fonte=13); b_pin.setFixedHeight(38); b_pin.clicked.connect(self._trocar_pin)
        hp.addWidget(lp); hp.addWidget(self.pin); hp.addStretch(); hp.addWidget(b_pin)
        v.addLayout(hp)
        d = QLabel("Sem o PIN, a pessoa só VÊ a letra, o acorde e o tempo. Com o PIN ela também toca, para, "
                   "troca de música e mexe no mixer. O som sai só do computador: a rede leva só os comandos.")
        d.setWordWrap(True); d.setFont(fonte(13)); d.setStyleSheet(f"color:{CINZA};"); v.addWidget(d)
        v.addStretch()
        h.addLayout(v, 1)
        self.corpo.addLayout(h)
        self.b_liga = Botao("", tipo="vermelho", tam_fonte=16, peso=QFont.Bold); self.b_liga.setFixedSize(220, 50)
        self.b_liga.clicked.connect(self._alternar)
        fechar = Botao("Fechar", tam_fonte=16, peso=QFont.Medium); fechar.setFixedSize(140, 50); fechar.clicked.connect(self.accept)
        self.rodape.lay.addWidget(self.b_liga); self.rodape.lay.addStretch(); self.rodape.lay.addWidget(fechar)
        self.timer = QTimer(self); self.timer.timeout.connect(self.atualizar); self.timer.start(700)
        self.atualizar()

    def _trocar_pin(self):
        self.j.remoto.novo_pin(); self.atualizar()

    def _alternar(self):
        if self.j.remoto.ativo:
            self.j.parar_remoto()
        else:
            self.j.iniciar_remoto(avisar=True)
        self.atualizar()

    def atualizar(self):
        r = self.j.remoto
        if r.ativo:
            urls = r.urls()
            self.url.setText(urls[0]); self.qr.definir(urls[0]); self.qr.setVisible(True)
            self.outras.setText(("Outros endereços deste computador: " + "  ·  ".join(urls[1:])) if len(urls) > 1 else "")
            n = r.clientes
            self.status.setText(f"Ligado  ·  {n} aparelho{'s' if n != 1 else ''} conectado{'s' if n != 1 else ''}")
            self.pin.setText(r.pin)
            self.b_liga.tipo = "metal"; self.b_liga.setText("Desligar"); self.b_liga.update()
        else:
            self.url.setText("—"); self.qr.setVisible(False); self.outras.setText(r.erro or "")
            self.status.setText("Desligado"); self.pin.setText(r.pin)
            self.b_liga.tipo = "vermelho"; self.b_liga.setText("Ligar controle remoto"); self.b_liga.update()



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
    comando_remoto = Signal(dict)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("WMusic Steams")
        self.resize(1530, 1030)
        self.setMinimumSize(1100, 760)
        self.motor = Motor()
        self.projeto = None
        self.trabalho = None
        self.faixas: list[Faixa] = []
        self.f_smpte: FaixaSMPTE | None = None
        from .remoto import Remoto
        self.remoto = Remoto(self._estado_remoto, lambda: self.projeto, self.comando_remoto.emit,
                             porta=int(pj.ler_config().get("remoto_porta", 8800)))
        self.comando_remoto.connect(self._executar_remoto)

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
        self.b_remoto = Botao("Remoto", "wifi", tam_fonte=16, peso=QFont.Medium, ligado="vermelho")
        self.b_remoto.setCheckable(True); self.b_remoto.setToolTip("Controle pelo iPhone, iPad ou celular na rede Wi-Fi")
        self.b_remoto.clicked.connect(self.abrir_remoto)
        self.b_exp = Botao("Exportar", "exportar", tam_fonte=16, peso=QFont.Medium); self.b_exp.clicked.connect(self.exportar)
        self.b_exp.setEnabled(False)
        for b in (b_nova, b_bib, self.b_remoto, self.b_exp):
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
        self.tc_label = QLabel(""); self.tc_label.setFont(sk.fonte_mono(19)); self.tc_label.setStyleSheet("color:#ff4a45;")
        self.tc_label.setToolTip("Timecode SMPTE que está saindo agora")
        L.addSpacing(8); L.addWidget(self.relogio); L.addSpacing(10); L.addWidget(self.tc_label); L.addSpacing(8)
        L.addWidget(Separador()); L.addStretch()
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
        if pj.ler_config().get("remoto_ligado"):
            QTimer.singleShot(300, lambda: self.iniciar_remoto(avisar=False))

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
        if self.f_smpte is not None:
            self.f_smpte.setParent(None); self.f_smpte.deleteLater()
        self.f_smpte = FaixaSMPTE(canais)
        self.f_smpte.mostrar(projeto.get("smpte"))
        self.f_smpte.mudou.connect(self.aplicar_mixer)
        self.f_smpte.configurar.connect(self.configurar_smpte)
        self.mixer_lay.insertWidget(self.mixer_lay.count() - 1, self.f_smpte)
        orig, _ = pj.abrir_wav_float(os.path.join(projeto["pasta"], "original.wav"))
        n = len(orig); k = max(1, n // 3000)
        bloco = np.abs(np.asarray(orig[: (n // k) * k], np.float32)).max(axis=1).reshape(-1, k).max(axis=1)
        del orig
        picos = bloco / (bloco.max() or 1)
        self.onda.definir(picos, projeto["duracao"], projeto.get("acordes", []))
        idx = np.linspace(0, len(picos) - 1, min(800, len(picos))).astype(int)
        projeto["_picos_web"] = [round(float(v), 3) for v in picos[idx]]
        self.remoto.projeto_mudou()
        self.b_exp.setEnabled(True)
        self.b_loop.setChecked(False)

    def fechar_projeto(self):
        self.salvar_mixer()
        self.motor.descarregar()
        self.projeto = None
        for f in self.faixas:
            f.setParent(None); f.deleteLater()
        self.faixas = []
        if self.f_smpte is not None:
            self.f_smpte.setParent(None); self.f_smpte.deleteLater(); self.f_smpte = None
        self.onda.definir(None, 1.0, [])
        self.remoto.projeto_mudou()
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
        if self.f_smpte is not None and self.motor.smpte is not None:
            self.f_smpte.aplicar(self.motor.smpte)

    def configurar_smpte(self):
        if not self.projeto:
            return
        atual = dict(tc.PADRAO); atual.update(self.projeto.get("smpte") or {})
        est = self.motor.estado_smpte()
        if est:
            atual.update(est)
        d = DialogoSMPTE(self, atual, self.projeto["titulo"])
        if d.exec() != QDialog.Accepted:
            return
        self.projeto["smpte"] = d.cfg
        self.motor.configurar_smpte(d.cfg)
        self.f_smpte.mostrar(d.cfg)
        self.aplicar_mixer()
        self.salvar_mixer()
        self.remoto.projeto_mudou()

    def salvar_mixer(self):
        if self.projeto:
            est = self.motor.estado_smpte()
            if est:
                self.projeto["smpte"] = est
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
        if self.f_smpte is not None and m.smpte is not None:
            if not tocando:
                m.smpte.pico *= 0.8
            self.f_smpte.fader.nivel = m.smpte.pico; self.f_smpte.fader.update()
        tcs = m.tc_atual()
        self.tc_label.setText(f"TC {tcs}" if tcs else "")
        self.b_remoto.blockSignals(True); self.b_remoto.setChecked(self.remoto.ativo); self.b_remoto.blockSignals(False)
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

    # ---------------------------------------------------------------- controle remoto
    def abrir_remoto(self):
        if not self.remoto.ativo:
            self.iniciar_remoto(avisar=True)
        DialogoRemoto(self, self).exec()

    def iniciar_remoto(self, avisar=True):
        ok = self.remoto.iniciar()
        pj.gravar_config({"remoto_ligado": ok})
        if not ok and avisar:
            QMessageBox.warning(self, "Controle remoto",
                                f"Não consegui abrir a porta {self.remoto.porta}.\n{self.remoto.erro or ''}")
        return ok

    def parar_remoto(self):
        self.remoto.parar()
        pj.gravar_config({"remoto_ligado": False})

    def _estado_remoto(self) -> dict:
        m = self.motor
        mix = {}
        for t in list(m.trilhas):
            if t.chave != "original":
                mix[t.chave] = {"mute": t.mute, "solo": t.solo,
                                "volume_db": -60.0 if t.volume <= 0 else round(20 * float(np.log10(t.volume)), 1)}
        sm = m.smpte
        if sm is not None:
            mix["smpte"] = {"mute": sm.mute, "solo": False,
                            "volume_db": round(20 * float(np.log10(max(1e-6, sm.volume * 0.5))), 1)}
        return {"pos": round(m.segundos, 3), "tocando": bool(m.tocando), "tc": m.tc_atual(), "mixer": mix,
                "loop": [m.loop[0] / m.taxa, m.loop[1] / m.taxa] if m.loop else None}

    def _executar_remoto(self, c: dict):
        cmd = c.get("cmd")
        if cmd == "tocar":
            if not self.motor.tocando:
                self.tocar_pausar()
        elif cmd == "pausar":
            self.motor.pausar()
        elif cmd == "parar":
            self.parar()
        elif cmd == "ir":
            try:
                self.ir_para(float(c.get("s", 0)))
            except (TypeError, ValueError):
                pass
        elif cmd == "abrir":
            try:
                self.abrir_projeto(pj.carregar(c["pasta"]))
            except Exception:
                pass
        elif cmd == "loop" and self.projeto:
            try:
                a, b = sorted((float(c["a"]), float(c["b"])))
                self.onda.loop_s = (a, b); self.definir_loop((a, b))
            except Exception:
                pass
        elif cmd == "loop_off":
            self.b_loop.setChecked(False)
        elif cmd == "mixer":
            k, campo, v = c.get("chave"), c.get("campo"), c.get("valor")
            t = self.motor.trilha(k)
            if t is None:
                return
            if campo == "mute":
                t.mute = bool(v)
            elif campo == "solo" and k != "smpte":
                t.solo = bool(v)
            elif campo == "volume_db":
                try:
                    db = max(-60.0, min(12.0, float(v)))
                except (TypeError, ValueError):
                    return
                lin = db_para_lin(db)
                t.volume = lin / 0.5 if k == "smpte" else lin
            f = self.f_smpte if k == "smpte" else next((x for x in self.faixas if x.chave == k), None)
            if f is not None:
                f.carregar(t)

    def closeEvent(self, e):
        self.salvar_mixer()
        self.remoto.parar()
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
    sm = projeto.get("smpte") or {}
    if sm.get("ligado"):
        from .smpte import gerar_arquivo
        ltc = gerar_arquivo(projeto["amostras"], projeto["taxa"], sm.get("fps", "30"), sm.get("inicio", "01:00:00:00"))
        sf.write(os.path.join(pasta, f"{len(projeto['trilhas']) + 1:02d} SMPTE {sm.get('inicio')} {sm.get('fps')}.wav".replace(":", "-")),
                 ltc, projeto["taxa"], subtype="PCM_24")
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
