"""Inicia o Chesslyst SEM janela de terminal (Windows: dois cliques neste arquivo).

Faz o mesmo que iniciar.py, mas o servidor roda oculto e se encerra sozinho cerca de 90 s depois de fechar a página
(ou pelo botão ⏻ Encerrar da interface). Se algo der errado, aparece uma caixa de mensagem; o registro fica em servidor.log.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.argv.append("--silencioso")
import iniciar

iniciar.main()
