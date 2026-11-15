"""Programa aberto pelo ícone (sem console): stdout/stderr None não podem derrubar nada."""
import os, sys, logging
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
real = sys.__stderr__
sys.stdout = None; sys.stderr = None
import wmusic_steams
wmusic_steams._saidas_seguras()
from tqdm import tqdm
for _ in tqdm(range(3)):
    pass
print("print ok")
logging.getLogger("x").addHandler(logging.StreamHandler()); logging.getLogger("x").warning("log ok")
real.write("1/1 testes OK\n")
