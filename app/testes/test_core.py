import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # app/ (onde fica o pacote indice)
from indice.core import Candidate as C, Position as P, analyse, line_index

def show(name, pos):
    r = analyse(pos, calibrar=False)   # regras testadas na escala bruta
    print(f"--- {name}: {r.index:.0f}% [{r.band}]\n{r.headline}")
    for x in r.reasons: print("  -", x)
    return r

# abertura
r1 = show("abertura", P([C("Nf3", 30, p_human=.5), C("e4", 28, p_human=.4), C("d4", 25, p_human=.1)], book_games=400))
assert r1.index >= 90
# tática curta
r2 = show("tática", P([C("Qh7#", mate=1, p_human=.9), C("Qd3", cp=100, p_human=.1)]))
assert r2.index >= 90
# final técnico
r3 = show("final", P([C("Kd6", cp=900, p_human=.05), C("Kd5", cp=0, p_human=.55), C("Kc5", cp=0, p_human=.4)],
                    piece_count=5, tb_result="win", tb_win_moves=1, tb_legal=7, endgame_kind="final de peões"))
assert r3.index < 25 and "final_tecnico" in r3.flags
# armadilha + profundidade
r4 = show("armadilha", P([C("Rxf7", cp=400, p_human=.1), C("Qd2", cp=-100, p_human=.7), C("a3", cp=-120, p_human=.2)], depth_stable=34))
assert r4.index < 25 and "armadilha" in r4.flags
assert abs(line_index([90, 80]) - 72) < 1e-6
# com a calibração aplicada, o final técnico continua difícil (regra pós-calibração) e a teoria continua alta
rc = analyse(P([C("Kd6", cp=900, p_human=.05), C("Kd5", cp=0, p_human=.55), C("Kc5", cp=0, p_human=.4)],
               piece_count=5, tb_result="win", tb_win_moves=1, tb_legal=7))
assert rc.index < 40, rc.index
assert analyse(P([C("Nf3", 30, p_human=.5), C("e4", 28, p_human=.4)], book_games=400)).index >= 85
print("OK")

from indice.core import indice_jogada
n, c, t = indice_jogada(0.2, 20, 60, 60); assert c == "brilhante" and n >= 95, (n, c)
n, c, t = indice_jogada(40, 90, 95, 40); assert c == "grave" and n < 30 and "escapar" in t, (n, c, t)
assert indice_jogada(0, 90, 50, 50)[1] == "melhor"
import chess
from indice.posicional import indice_posicao
i0, _, _ = indice_posicao(chess.Board()); assert abs(i0 - 50) < 1, i0
print("OK2")

