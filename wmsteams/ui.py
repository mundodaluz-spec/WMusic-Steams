"""Interface do WMusic Steams (PySide6)."""
from __future__ import annotations

import os
import shutil
import sys
import traceback

import numpy as np
from PySide6.QtCore import Qt, QThread, QTimer, Signal, QRectF, QPointF, QSize
from PySide6.QtGui import (QAction, QColor, QFont, QIcon, QKeySequence, QPainter, QPainterPath,
                           QPen, QPixmap, QShortcut, QFontMetricsF)
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
                               QFileDialog, QFormLayout, QFrame, QHBoxLayout, QLabel, QListWidget,
                               QListWidgetItem, QMainWindow, QMessageBox, QPlainTextEdit,
                               QProgressBar, QPushButton, QScrollArea, QSlider, QSizePolicy,
                               QVBoxLayout, QWidget, QDial)

from . import projeto as pj
from .player import Motor

PRETO = "#0c0c0c"
PAINEL = "#151515"
PAINEL2 = "#1d1d1d"
CREME = "#F2E3CF"
VERMELHO = "#E1262C"
CINZA = "#8b8580"

CORES = {
    "voz": "#E1262C", "bateria": "#F2E3CF", "baixo": "#D98E3B", "guitarra": "#C9B27C",
    "teclas": "#8FB3C9", "outros": "#9C8FC9", "instrumental": "#C9B27C", "pad": "#6FC9A4",
    "original": "#8b8580",
}

ESTILO = f"""
* {{ font-family: 'Inter', 'Segoe UI', 'Helvetica Neue', Arial; color: {CREME}; }}
QMainWindow, QDialog {{ background: {PRETO}; }}
QWidget#painel {{ background: {PAINEL}; border-radius: 10px; }}
QLabel#sub {{ color: {CINZA}; }}
QPushButton {{ background: {PAINEL2}; border: 1px solid #2a2a2a; border-radius: 8px; padding: 7px 14px; }}
QPushButton:hover {{ border-color: {CREME}; }}
QPushButton:checked {{ background: {VERMELHO}; border-color: {VERMELHO}; color: white; }}
QPushButton#principal {{ background: {VERMELHO}; border-color: {VERMELHO}; color: white; font-weight: 600; }}
QPushButton#mini {{ padding: 3px 0px; min-width: 28px; max-width: 28px; font-weight: 700; border-radius: 6px; }}
QPushButton#mini:checked {{ background: {VERMELHO}; }}
QPushButton#solo:checked {{ background: #E8B23A; border-color: #E8B23A; color: #111; }}
QComboBox, QPlainTextEdit, QListWidget {{ background: {PAINEL2}; border: 1px solid #2a2a2a; border-radius: 6px; padding: 4px 8px; }}
QComboBox QAbstractItemView {{ background: {PAINEL2}; selection-background-color: {VERMELHO}; }}
QProgressBar {{ background: {PAINEL2}; border: none; border-radius: 5px; height: 10px; text-align: center; }}
QProgressBar::chunk {{ background: {VERMELHO}; border-radius: 5px; }}
QSlider::groove:vertical {{ background: #262626; width: 6px; border-radius: 3px; }}
QSlider::handle:vertical {{ background: {CREME}; height: 18px; margin: 0 -9px; border-radius: 4px; }}
QSlider::groove:horizontal {{ background: #262626; height: 6px; border-radius: 3px; }}
QSlider::handle:horizontal {{ background: {CREME}; width: 14px; margin: -5px 0; border-radius: 4px; }}
QScrollArea {{ border: none; background: transparent; }}
QCheckBox::indicator {{ width: 16px; height: 16px; }}
"""


def recurso(*partes) -> str:
    return os.path.join(pj.pasta_recursos(), *partes)


def tempo_txt(s: float) -> str:
    s = max(0.0, s)
    m, s = divmod(s, 60)
    return f"{int(m)}:{s:04.1f}"


def db_para_lin(db: float) -> float:
    return 0.0 if db <= -60 else 10 ** (db / 20)


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


class DialogoNova(QDialog):
    def __init__(self, parent, arquivo: str):
        super().__init__(parent)
        self.setWindowTitle("Nova música")
        self.setMinimumWidth(520)
        self.arquivo = arquivo
        lay = QVBoxLayout(self)
        t = QLabel(os.path.basename(arquivo))
        t.setFont(QFont(t.font().family(), 14, QFont.Bold))
        lay.addWidget(t)
        f = QFormLayout()
        self.qual = QComboBox(); self.qual.addItems(["Alta (mais lenta)", "Rápida"])
        self.idioma = QComboBox(); self.idioma.addItems(["Português", "Inglês", "Espanhol", "Detectar"])
        self.letra = QCheckBox("Escrever a letra"); self.letra.setChecked(True)
        self.timbre = QComboBox(); self.timbre.addItems(["Quente", "Brilhante", "Suave"])
        self.dica = QPlainTextEdit(); self.dica.setPlaceholderText(
            "Opcional: cole aqui a letra da música. Ajuda a acertar as palavras.")
        self.dica.setFixedHeight(110)
        f.addRow("Qualidade da separação", self.qual)
        f.addRow("Idioma da letra", self.idioma)
        f.addRow("", self.letra)
        f.addRow("Timbre do pad", self.timbre)
        lay.addLayout(f)
        lay.addWidget(self.dica)
        bb = QDialogButtonBox()
        ok = bb.addButton("Separar", QDialogButtonBox.AcceptRole); ok.setObjectName("principal")
        bb.addButton("Cancelar", QDialogButtonBox.RejectRole)
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def opcoes(self) -> dict:
        idi = {0: "pt", 1: "en", 2: "es", 3: None}[self.idioma.currentIndex()]
        return {"qualidade": "alta" if self.qual.currentIndex() == 0 else "rapida", "idioma": idi,
                "fazer_letra": self.letra.isChecked(), "timbre_pad": self.timbre.currentText(),
                "dica_letra": self.dica.toPlainText().strip() or None}


class DialogoProgresso(QDialog):
    def __init__(self, parent, titulo: str):
        super().__init__(parent)
        self.setWindowTitle("Separando")
        self.setMinimumWidth(480)
        self.setWindowFlag(Qt.WindowCloseButtonHint, False)
        lay = QVBoxLayout(self)
        t = QLabel(titulo); t.setFont(QFont(t.font().family(), 13, QFont.Bold)); lay.addWidget(t)
        self.msg = QLabel("Começando…"); self.msg.setObjectName("sub"); lay.addWidget(self.msg)
        self.barra = QProgressBar(); self.barra.setRange(0, 1000); self.barra.setTextVisible(False)
        lay.addWidget(self.barra)

    def atualizar(self, msg: str, f: float):
        self.msg.setText(msg)
        self.barra.setValue(int(f * 1000))


class DialogoBiblioteca(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Biblioteca")
        self.resize(560, 460)
        self.escolhido = None
        lay = QVBoxLayout(self)
        self.lista = QListWidget()
        lay.addWidget(self.lista)
        h = QHBoxLayout()
        b_abrir = QPushButton("Abrir"); b_abrir.setObjectName("principal")
        b_pasta = QPushButton("Mostrar pasta")
        b_apagar = QPushButton("Apagar")
        h.addWidget(b_abrir); h.addWidget(b_pasta); h.addStretch(); h.addWidget(b_apagar)
        lay.addLayout(h)
        b_abrir.clicked.connect(self.abrir)
        self.lista.itemDoubleClicked.connect(lambda *_: self.abrir())
        b_pasta.clicked.connect(self.mostrar)
        b_apagar.clicked.connect(self.apagar)
        self.recarregar()

    def recarregar(self):
        self.lista.clear()
        for p in pj.listar_biblioteca():
            it = QListWidgetItem(f'{p.get("titulo")}   ·   {tempo_txt(p.get("duracao", 0))}   ·   tom {p.get("tom", "?")}')
            it.setData(Qt.UserRole, p["pasta"])
            self.lista.addItem(it)

    def _atual(self):
        it = self.lista.currentItem()
        return it.data(Qt.UserRole) if it else None

    def abrir(self):
        if self._atual():
            self.escolhido = self._atual()
            self.accept()

    def mostrar(self):
        p = self._atual() or pj.pasta_biblioteca()
        abrir_no_sistema(p)

    def apagar(self):
        p = self._atual()
        if not p:
            return
        if QMessageBox.question(self, "Apagar", f"Apagar a pasta desta música?\n\n{p}\n\nNão dá para desfazer.") == QMessageBox.Yes:
            shutil.rmtree(p, ignore_errors=True)
            self.recarregar()


def abrir_no_sistema(caminho: str):
    import subprocess
    if sys.platform == "win32":
        os.startfile(caminho)  # noqa
    elif sys.platform == "darwin":
        subprocess.Popen(["open", caminho])
    else:
        subprocess.Popen(["xdg-open", caminho])


# ===================================================================== widgets

class Medidor(QWidget):
    def __init__(self):
        super().__init__()
        self.valor = 0.0
        self.setFixedWidth(8)

    def paintEvent(self, e):
        p = QPainter(self)
        r = self.rect()
        p.fillRect(r, QColor("#262626"))
        db = 20 * np.log10(self.valor + 1e-9)
        f = min(1.0, max(0.0, (db + 48) / 54))
        h = int(r.height() * f)
        cor = QColor(VERMELHO) if db > -1 else QColor(CREME)
        p.fillRect(0, r.height() - h, r.width(), h, cor)


class Faixa(QWidget):
    """Canal do mixer."""
    mudou = Signal()

    def __init__(self, chave: str, nome: str, saidas: int):
        super().__init__()
        self.chave = chave
        self.setObjectName("painel")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFixedWidth(104)
        lay = QVBoxLayout(self); lay.setContentsMargins(8, 10, 8, 10); lay.setSpacing(6)
        cor = CORES.get(chave, CREME)
        tag = QLabel(nome); tag.setAlignment(Qt.AlignCenter)
        tag.setStyleSheet(f"font-weight:700; color:{cor}; border-bottom: 3px solid {cor}; padding-bottom:4px;")
        lay.addWidget(tag)
        h = QHBoxLayout(); h.setSpacing(4)
        self.m = QPushButton("M"); self.m.setObjectName("mini"); self.m.setCheckable(True)
        self.s = QPushButton("S"); self.s.setObjectName("mini"); self.s.setCheckable(True)
        self.s.setProperty("class", "solo"); self.s.setObjectName("solo")
        self.s.setStyleSheet("padding:3px 0; min-width:28px; max-width:28px; font-weight:700; border-radius:6px;")
        h.addWidget(self.m); h.addWidget(self.s)
        lay.addLayout(h)
        self.pan = QSlider(Qt.Horizontal); self.pan.setRange(-100, 100); self.pan.setValue(0)
        self.pan.setToolTip("Pan (duplo clique = centro)")
        hp = QHBoxLayout(); hp.setSpacing(4)
        le, ld = QLabel("E"), QLabel("D")
        for l in (le, ld): l.setObjectName("sub"); l.setStyleSheet("font-size:10px;")
        hp.addWidget(le); hp.addWidget(self.pan, 1); hp.addWidget(ld)
        lay.addLayout(hp)
        h2 = QHBoxLayout(); h2.setSpacing(6)
        self.fader = QSlider(Qt.Vertical); self.fader.setRange(-600, 60); self.fader.setValue(0)
        self.fader.setMinimumHeight(150)
        self.medidor = Medidor()
        h2.addStretch(); h2.addWidget(self.fader); h2.addWidget(self.medidor); h2.addStretch()
        lay.addLayout(h2, 1)
        self.valor = QLabel("0.0 dB"); self.valor.setAlignment(Qt.AlignCenter); self.valor.setObjectName("sub")
        lay.addWidget(self.valor)
        self.saida = QComboBox()
        self.definir_saidas(saidas)
        self.saida.setToolTip("Saída da placa de som")
        lay.addWidget(self.saida)
        self.m.toggled.connect(lambda *_: self.mudou.emit())
        self.s.toggled.connect(lambda *_: self.mudou.emit())
        self.pan.valueChanged.connect(lambda *_: self.mudou.emit())
        self.fader.valueChanged.connect(self._fader)
        self.saida.currentIndexChanged.connect(lambda *_: self.mudou.emit())
        self.fader.mouseDoubleClickEvent = lambda e: self.fader.setValue(0)
        self.pan.mouseDoubleClickEvent = lambda e: self.pan.setValue(0)

    def definir_saidas(self, canais: int):
        atual = max(0, self.saida.currentIndex())
        self.saida.blockSignals(True)
        self.saida.clear()
        for i in range(max(1, canais // 2)):
            self.saida.addItem(f"{2*i+1}-{2*i+2}")
        self.saida.setCurrentIndex(min(atual, self.saida.count() - 1))
        self.saida.blockSignals(False)

    def _fader(self, v):
        db = v / 10
        self.valor.setText("−∞" if db <= -60 else f"{db:+.1f} dB".replace("+0.0", "0.0"))
        self.mudou.emit()

    def aplicar(self, t):
        t.volume = db_para_lin(self.fader.value() / 10)
        t.pan = self.pan.value() / 100
        t.mute = self.m.isChecked()
        t.solo = self.s.isChecked()
        t.saida = max(0, self.saida.currentIndex())

    def carregar(self, t):
        for w in (self.m, self.s, self.pan, self.fader, self.saida):
            w.blockSignals(True)
        self.m.setChecked(t.mute); self.s.setChecked(t.solo)
        self.pan.setValue(int(round(t.pan * 100)))
        db = -60 if t.volume <= 0 else 20 * np.log10(t.volume)
        self.fader.setValue(int(round(db * 10)))
        self.saida.setCurrentIndex(min(t.saida, self.saida.count() - 1))
        for w in (self.m, self.s, self.pan, self.fader, self.saida):
            w.blockSignals(False)
        self._fader(self.fader.value())


class Onda(QWidget):
    """Forma de onda da música, acordes em cima, cursor, clique para ir, arraste para loop."""
    ir = Signal(float)
    loop = Signal(object)

    def __init__(self):
        super().__init__()
        self.setMinimumHeight(110)
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

    def _x(self, s):
        return s / self.dur * self.width()

    def _s(self, x):
        return max(0.0, min(self.dur, x / max(1, self.width()) * self.dur))

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(self.rect(), QColor(PAINEL))
        topo = 22
        if self.loop_s:
            a, b = self.loop_s
            p.fillRect(QRectF(self._x(a), 0, self._x(b) - self._x(a), h), QColor(225, 38, 44, 45))
        if self.picos is not None and len(self.picos):
            meio = topo + (h - topo) / 2
            amp = (h - topo) / 2 - 4
            n = len(self.picos)
            xp = self._x(self.pos)
            for i in range(w):
                v = self.picos[min(n - 1, int(i / w * n))]
                cor = QColor(CREME) if i <= xp else QColor("#4a4440")
                p.setPen(cor)
                p.drawLine(QPointF(i, meio - v * amp), QPointF(i, meio + v * amp))
        p.setFont(QFont(self.font().family(), 9, QFont.Bold))
        for a in self.acordes:
            if a["nome"] == "N":
                continue
            x0, x1 = self._x(a["t0"]), self._x(a["t1"])
            p.setPen(QPen(QColor("#333"), 1)); p.drawLine(QPointF(x0, 0), QPointF(x0, topo))
            if x1 - x0 > 22:
                ativo = a["t0"] <= self.pos < a["t1"]
                p.setPen(QColor(VERMELHO if ativo else CINZA))
                p.drawText(QRectF(x0 + 3, 2, x1 - x0 - 4, topo - 4), Qt.AlignVCenter | Qt.AlignLeft, a["nome"])
        p.setPen(QPen(QColor(VERMELHO), 2))
        x = self._x(self.pos)
        p.drawLine(QPointF(x, 0), QPointF(x, h))

    def mousePressEvent(self, e):
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
    """Linha atual grande, palavra cantada acesa; linha anterior e próxima em cinza."""

    def __init__(self):
        super().__init__()
        self.linhas = []
        self.t = 0.0
        self.setMinimumHeight(170)
        self.aviso = ""

    def definir(self, letra, aviso=None):
        self.linhas = (letra or {}).get("linhas", [])
        self.aviso = aviso or ("Sem letra nesta música." if not self.linhas else "")
        self.update()

    def _indice(self):
        t = self.t + 0.15  # mostra a linha um pouquinho antes de começar
        idx = -1
        for i, l in enumerate(self.linhas):
            if l["t0"] <= t:
                idx = i
            else:
                break
        return idx

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        r = self.rect()
        p.fillRect(r, QColor(PAINEL))
        fam = self.font().family()
        if not self.linhas:
            p.setPen(QColor(CINZA)); p.setFont(QFont(fam, 13))
            p.drawText(r, Qt.AlignCenter, self.aviso)
            return
        i = self._indice()
        h = r.height()
        def linha_simples(txt, y, tam, cor):
            p.setFont(QFont(fam, tam)); p.setPen(QColor(cor))
            p.drawText(QRectF(16, y, r.width() - 32, tam * 2.2), Qt.AlignHCenter | Qt.AlignVCenter, txt)
        if i - 1 >= 0:
            linha_simples(self.linhas[i - 1]["texto"], h * 0.08, 13, "#5d5853")
        if i + 1 < len(self.linhas):
            linha_simples(self.linhas[i + 1]["texto"], h * 0.70, 15, CINZA)
        if i < 0:
            linha_simples(self.linhas[0]["texto"], h * 0.36, 22, "#5d5853")
            return
        atual = self.linhas[i]
        tam = 24
        f = QFont(fam, tam, QFont.Bold)
        fm = QFontMetricsF(f)
        palavras = atual["palavras"]
        larg = sum(fm.horizontalAdvance(w["w"] + " ") for w in palavras)
        while larg > r.width() - 40 and tam > 12:
            tam -= 1; f = QFont(fam, tam, QFont.Bold); fm = QFontMetricsF(f)
            larg = sum(fm.horizontalAdvance(w["w"] + " ") for w in palavras)
        p.setFont(f)
        x = (r.width() - larg) / 2
        y = h * 0.36 + fm.ascent() + 6
        for w in palavras:
            cantada = self.t + 0.05 >= w["t0"]
            p.setPen(QColor(VERMELHO if cantada and self.t < atual["t1"] + 0.6 else CREME))
            p.drawText(QPointF(x, y), w["w"])
            x += fm.horizontalAdvance(w["w"] + " ")


# ===================================================================== janela

class Janela(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("WMusic Steams")
        self.resize(1200, 820)
        self.motor = Motor()
        self.projeto = None
        self.trabalho = None
        self.faixas: list[Faixa] = []

        central = QWidget(); self.setCentralWidget(central)
        raiz = QVBoxLayout(central); raiz.setContentsMargins(16, 12, 16, 12); raiz.setSpacing(10)

        # cabeçalho
        cab = QHBoxLayout()
        logo = QLabel()
        pm = QPixmap(recurso("assets", "logo-360.png"))
        if not pm.isNull():
            logo.setPixmap(pm.scaledToHeight(54, Qt.SmoothTransformation))
        cab.addWidget(logo)
        nome = QLabel("STEAMS"); nome.setStyleSheet(f"font-size:22px; font-weight:800; letter-spacing:6px; color:{CREME};")
        cab.addWidget(nome); cab.addSpacing(18)
        self.titulo = QLabel("Abra uma música para começar"); self.titulo.setStyleSheet("font-size:16px; font-weight:600;")
        self.sub = QLabel(""); self.sub.setObjectName("sub")
        v = QVBoxLayout(); v.addWidget(self.titulo); v.addWidget(self.sub)
        cab.addLayout(v); cab.addStretch()
        b_nova = QPushButton("Nova música"); b_nova.setObjectName("principal"); b_nova.clicked.connect(self.nova)
        b_bib = QPushButton("Biblioteca"); b_bib.clicked.connect(self.biblioteca)
        self.b_exp = QPushButton("Exportar"); self.b_exp.clicked.connect(self.exportar); self.b_exp.setEnabled(False)
        cab.addWidget(b_nova); cab.addWidget(b_bib); cab.addWidget(self.b_exp)
        raiz.addLayout(cab)

        # acorde + letra
        meio = QHBoxLayout(); meio.setSpacing(10)
        cx = QWidget(); cx.setObjectName("painel"); cx.setFixedWidth(200)
        cx.setAttribute(Qt.WA_StyledBackground, True)
        vl = QVBoxLayout(cx); vl.setContentsMargins(14, 12, 14, 12)
        l1 = QLabel("ACORDE"); l1.setObjectName("sub"); vl.addWidget(l1)
        self.acorde = QLabel("–"); self.acorde.setStyleSheet(f"font-size:46px; font-weight:800; color:{VERMELHO};")
        vl.addWidget(self.acorde)
        self.prox = QLabel(""); self.prox.setObjectName("sub"); self.prox.setStyleSheet("font-size:15px;")
        vl.addWidget(self.prox); vl.addStretch()
        self.tom = QLabel(""); self.tom.setObjectName("sub"); vl.addWidget(self.tom)
        h_pad = QHBoxLayout(); lp = QLabel("Pad"); lp.setObjectName("sub")
        self.timbre = QComboBox(); self.timbre.addItems(["Quente", "Brilhante", "Suave"])
        self.timbre.currentTextChanged.connect(self.trocar_timbre)
        h_pad.addWidget(lp); h_pad.addWidget(self.timbre); vl.addLayout(h_pad)
        meio.addWidget(cx)
        self.letra = Letra(); meio.addWidget(self.letra, 1)
        raiz.addLayout(meio)

        # mixer
        self.area = QScrollArea(); self.area.setWidgetResizable(True)
        self.area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.mixer = QWidget(); self.mixer.setObjectName("mixer")
        self.mixer.setStyleSheet("QWidget#mixer { background: transparent; }")
        self.area.viewport().setObjectName("vp"); self.area.viewport().setStyleSheet("QWidget#vp { background: transparent; }")
        self.mixer_lay = QHBoxLayout(self.mixer)
        self.mixer_lay.setContentsMargins(0, 0, 0, 0); self.mixer_lay.setSpacing(8); self.mixer_lay.addStretch()
        self.area.setWidget(self.mixer)
        self.area.setMinimumHeight(330)
        raiz.addWidget(self.area, 1)

        # onda + transporte
        self.onda = Onda(); self.onda.ir.connect(self.ir_para); self.onda.loop.connect(self.definir_loop)
        raiz.addWidget(self.onda)
        tr = QHBoxLayout()
        self.b_inicio = QPushButton("⏮"); self.b_inicio.clicked.connect(lambda: self.ir_para(0))
        self.b_play = QPushButton("▶  Tocar"); self.b_play.setObjectName("principal"); self.b_play.setMinimumWidth(120)
        self.b_play.clicked.connect(self.tocar_pausar)
        self.b_parar = QPushButton("⏹"); self.b_parar.clicked.connect(self.parar)
        self.b_loop = QPushButton("Loop"); self.b_loop.setCheckable(True); self.b_loop.toggled.connect(self.alternar_loop)
        self.b_loop.setToolTip("Arraste na forma de onda para marcar o trecho")
        self.relogio = QLabel("0:00.0 / 0:00.0"); self.relogio.setStyleSheet("font-size:16px; font-weight:600; font-family: monospace;")
        tr.addWidget(self.b_inicio); tr.addWidget(self.b_play); tr.addWidget(self.b_parar); tr.addWidget(self.b_loop)
        tr.addSpacing(14); tr.addWidget(self.relogio); tr.addStretch()
        lm = QLabel("Master"); lm.setObjectName("sub")
        self.master = QSlider(Qt.Horizontal); self.master.setRange(-600, 60); self.master.setValue(0); self.master.setFixedWidth(160)
        self.master.valueChanged.connect(lambda v: setattr(self.motor, "master", db_para_lin(v / 10)))
        ls = QLabel("Saída"); ls.setObjectName("sub")
        self.disp = QComboBox(); self.disp.setMinimumWidth(260)
        self.disp.addItem("Padrão do sistema", None)
        for d in Motor.dispositivos():
            self.disp.addItem(f'{d["nome"]} · {d["canais"]} canais', d["indice"])
        self.disp.currentIndexChanged.connect(self.trocar_dispositivo)
        tr.addWidget(lm); tr.addWidget(self.master); tr.addSpacing(10); tr.addWidget(ls); tr.addWidget(self.disp)
        raiz.addLayout(tr)

        QShortcut(QKeySequence(Qt.Key_Space), self, activated=self.tocar_pausar)
        QShortcut(QKeySequence(Qt.Key_Home), self, activated=lambda: self.ir_para(0))
        self.relogio_timer = QTimer(self); self.relogio_timer.timeout.connect(self.tique); self.relogio_timer.start(33)
        self.setAcceptDrops(True)

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
        self.titulo.setText(projeto["titulo"])
        r = projeto.get("relatorio", {})
        self.sub.setText(f'{tempo_txt(projeto["duracao"])}  ·  {projeto["taxa"]} Hz  ·  soma dos stems = original ({r.get("nulo_db", "?")} dB)')
        self.tom.setText(f'Tom: {projeto.get("tom", "?")}')
        self.timbre.blockSignals(True); self.timbre.setCurrentText(projeto.get("pad_timbre", "Quente")); self.timbre.blockSignals(False)
        self.letra.definir(projeto.get("letra"), projeto.get("aviso_letra"))
        # mixer
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
        # onda
        orig, _ = pj.abrir_wav_float(os.path.join(projeto["pasta"], "original.wav"))
        n = len(orig); k = max(1, n // 3000)
        bloco = np.abs(np.asarray(orig[: (n // k) * k], np.float32)).max(axis=1).reshape(-1, k).max(axis=1)
        self.onda.definir(bloco / (bloco.max() or 1), projeto["duracao"], projeto.get("acordes", []))
        self.b_exp.setEnabled(True)
        self.b_loop.setChecked(False)

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
            pj.regerar_pad(self.projeto, timbre)
            tocando = self.motor.tocando
            self.abrir_projeto(self.projeto, manter_pos=True)
            if tocando:
                self.motor.tocar()
        except Exception as e:
            QMessageBox.critical(self, "Pad", str(e))

    def tique(self):
        m = self.motor
        s = m.segundos
        dur = self.projeto["duracao"] if self.projeto else 0
        self.relogio.setText(f"{tempo_txt(s)} / {tempo_txt(dur)}")
        self.b_play.setText("⏸  Pausar" if m.tocando else "▶  Tocar")
        self.onda.pos = s; self.onda.update()
        self.letra.t = s; self.letra.update()
        for f in self.faixas:
            t = m.trilha(f.chave)
            if t:
                if not m.tocando:
                    t.pico *= 0.8
                f.medidor.valor = t.pico; f.medidor.update()
        if self.projeto:
            ac = self.projeto.get("acordes", [])
            atual = next((a for a in ac if a["t0"] <= s < a["t1"]), None)
            self.acorde.setText(atual["nome"] if atual and atual["nome"] != "N" else "–")
            prox = next((a for a in ac if a["t0"] > s and a["nome"] != "N"), None)
            self.prox.setText(f'depois: {prox["nome"]}' if prox else "")

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


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("WMusic Steams")
    app.setOrganizationName("WMusic")
    ic = recurso("assets", "icone.png")
    if os.path.exists(ic):
        app.setWindowIcon(QIcon(ic))
    app.setStyleSheet(ESTILO)
    j = Janela()
    j.show()
    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
        if os.path.exists(os.path.join(sys.argv[1], "projeto.json")):
            j.abrir_projeto(pj.carregar(sys.argv[1]))
    return app.exec()
