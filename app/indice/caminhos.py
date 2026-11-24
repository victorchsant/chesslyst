"""Onde ficam as coisas.

RECURSOS: código, interface e calibrações (somente leitura; ficam dentro do .exe quando empacotado).
DADOS:    engines baixadas, engines.json e caches (gravável). Em desenvolvimento é a própria pasta app/;
          no .exe é %LOCALAPPDATA%/Chesslyst; a variável CHESSLYST_DADOS troca o local nos dois casos.
"""
import os, sys
from pathlib import Path

RECURSOS = Path(__file__).resolve().parent.parent


def _dados():
    env = os.environ.get("CHESSLYST_DADOS")
    if env: return Path(env)
    if getattr(sys, "frozen", False): return Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "Chesslyst"
    return RECURSOS


DADOS = _dados()
try: DADOS.mkdir(parents=True, exist_ok=True)
except OSError: pass
