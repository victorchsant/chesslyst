"""PGN -> Stockfish multi-PV + Maia (via Lc0, rede da faixa de rating do jogador) -> índice por lance.

`colher(...)` guarda os dados brutos de uma posição (reutilizáveis na calibração);
`para_posicao(raw)` os converte em `Position` para o núcleo.
"""
from __future__ import annotations
import re, subprocess
from pathlib import Path
import chess, chess.engine, chess.pgn
from . import fontes
from .core import Candidate, Position, analyse, win_pct, indice_jogada, nome_classe
from .explica import explicar_lance, explicar_avaliacao, explicar_porque, marca_notacao
from .critico import momento_critico
from .i18n import T
from .posicional import indice_posicao, analise as analise_posicao, texto_debilidades, texto_postos, texto_rei, texto_pecas

from .caminhos import DADOS as ROOT       # engines baixadas ficam na pasta de dados do usuário
def _acha(nome):
    d = ROOT / "engines" / nome
    for p in (sorted(d.rglob(nome + "*")) if d.exists() else []):
        if p.is_file() and p.suffix.lower() in (".exe", "") and p.stat().st_size > 500_000: return p
    return None


SF = _acha("stockfish")            # None enquanto o usuário não baixar/cadastrar uma engine
LC0 = _acha("lc0") or ROOT / "engines/lc0/lc0.exe"
ENDGAME_PIECES = 7
PV_GUARDADA = 12                     # meios-lances de cada linha usados nas explicações: com 8, uma troca ficava pela metade
_P = re.compile(r"info string (\S+) .*?\(P:\s*([\d.]+)%\)")


def maia_nivel(rating):
    """Rede Maia mais próxima do rating (existem 1100..1900); sem rating usa 1900."""
    if not rating: return 1900
    return max(1100, min(1900, int(round(rating / 100.0)) * 100))


class Maia:
    """Lc0 com pesos Maia, 1 nó: a política da rede é a distribuição humana.
    Mantém um processo por nível de rating, aberto sob demanda."""
    def __init__(self, lc0=None, pesos=None, args=""):
        self.procs = {}
        self.lc0 = Path(lc0) if lc0 else LC0
        self.pesos = Path(pesos) if pesos else None   # rede fixa (modo personalizado)
        self.args = args.split() if args else []

    def _proc(self, nivel):
        if nivel not in self.procs:
            w = self.pesos or ROOT / f"engines/maia/maia-{nivel}.pb.gz"
            p = subprocess.Popen([str(self.lc0), f"--weights={w}", "--verbose-move-stats", *self.args],
                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                 stderr=subprocess.DEVNULL, text=True, bufsize=1, cwd=Path(self.lc0).parent)
            self.procs[nivel] = p
            self._send(p, "uci"); self._wait(p, "uciok")
        return self.procs[nivel]

    @staticmethod
    def _send(p, s): p.stdin.write(s + "\n"); p.stdin.flush()

    @staticmethod
    def _wait(p, key):
        lines = []
        while True:
            l = p.stdout.readline()
            if not l: raise RuntimeError("lc0 encerrou")
            lines.append(l.strip())
            if l.startswith(key): return lines

    def policy(self, board: chess.Board, rating=None) -> dict:
        p = self._proc(0 if self.pesos else maia_nivel(rating))
        self._send(p, "ucinewgame")
        self._send(p, f"position fen {board.fen()}")
        self._send(p, "go nodes 1")
        out = {}
        for l in self._wait(p, "bestmove"):
            m = _P.match(l)
            if m:
                try: out[board.san(chess.Move.from_uci(m.group(1)))] = float(m.group(2)) / 100
                except ValueError: pass
        return out

    def close(self):
        for p in self.procs.values():
            try: self._send(p, "quit")
            except Exception: pass


def candidates(sf, board, n, depth, tempo=None):
    """Multi-PV; devolve candidatos (ponto de vista de quem joga) e a profundidade de estabilização."""
    n = min(n, board.legal_moves.count())
    best_at = {}
    with sf.analysis(board, chess.engine.Limit(depth=depth, time=tempo), multipv=n) as an:
        last = {}
        for info in an:
            if info.get("multipv") == 1 and "pv" in info and "depth" in info:
                best_at[info["depth"]] = info["pv"][0]
            if "pv" in info and "score" in info: last[info["multipv"]] = info
    final = [last[k] for k in sorted(last)]
    cands, pvs = [], []
    for i in final:
        s = i["score"].relative
        cands.append((board.san(i["pv"][0]), s.score(), s.mate()))
        b2, sans = board.copy(), []
        for m in i["pv"][:8]:
            sans.append(b2.san(m)); b2.push(m)
        pvs.append(dict(uci=i["pv"][0].uci(), pv=sans, pv_uci=[m.uci() for m in i["pv"][:PV_GUARDADA]]))
    stable, target = None, final[0]["pv"][0]
    for d in sorted(best_at, reverse=True):
        if best_at[d] != target: break
        stable = d
    return cands, stable, pvs


def avalia_jogado(sf, board, move, depth):
    """Avaliação (cp, mate) do lance realmente jogado, do ponto de vista de quem jogou."""
    info = sf.analyse(board, chess.engine.Limit(depth=depth), root_moves=[move])
    s = info["score"].relative
    return s.score(), s.mate(), [m.uci() for m in info.get("pv", [])[:PV_GUARDADA]]


def candidatos_simples(eng, board, n, depth, tempo):
    """Multi-PV de uma engine adicional, com tempo máximo rígido (engine que não responde vira erro)."""
    n = min(n, board.legal_moves.count())
    eng.timeout = tempo + 10
    infos = eng.analyse(board, chess.engine.Limit(depth=depth, time=tempo), multipv=n)
    cands, pvs = [], []
    for i in infos:
        if "pv" not in i or "score" not in i: continue
        s = i["score"].relative
        cands.append((board.san(i["pv"][0]), s.score(), s.mate()))
        b2, sans = board.copy(), []
        for m in i["pv"][:8]:
            sans.append(b2.san(m)); b2.push(m)
        pvs.append(dict(uci=i["pv"][0].uci(), pv=sans))
    if not cands: raise RuntimeError("a engine não devolveu linhas")
    return cands, pvs


def montar_linhas(board, cands, pvs, pol=None):
    """Linhas de cálculo com cp/mate do ponto de vista das brancas."""
    tot = (sum(pol.get(c[0], 0.0) for c in cands) or 1.0) if pol else 1.0
    sinal = 1 if board.turn else -1
    return [dict(san=c[0], uci=v["uci"], cp=None if c[1] is None else c[1] * sinal,
                 mate=None if c[2] is None else c[2] * sinal,
                 p_humano=round(pol.get(c[0], 0.0) / tot, 3) if pol else None, pv=v["pv"], pv_uci=v.get("pv_uci"))
            for c, v in zip(cands, pvs)]


def colher(board, move, sf, maia, rating=None, depth=14, multipv=5, em_livro=True, outras=None, tempo=None):
    """Dados brutos de uma posição (antes de `move`; move=None = posição ainda sem lance jogado)."""
    pcs = len(board.piece_map())
    tb = fontes.tablebase(board.fen()) if pcs <= ENDGAME_PIECES else None
    n = board.legal_moves.count() if (pcs <= ENDGAME_PIECES and not tb) else multipv
    cands, stable, pvs = candidates(sf, board, n, depth)
    pol = maia.policy(board, rating)
    bk = fontes.masters(board.fen()) if em_livro else (None, {})
    book, book_moves = bk[0], bk[1]
    san = jogado = fen_depois = uci = pv_jogado = None
    if move is not None:
        san, uci = board.san(move), move.uci()
        idx_hit = next((j for j, (s_, c_, m_) in enumerate(cands) if s_ == san), None)
        if idx_hit is not None:
            jogado, pv_jogado = [cands[idx_hit][1], cands[idx_hit][2]], pvs[idx_hit].get("pv_uci")
        else:
            r3 = avalia_jogado(sf, board, move, depth); jogado, pv_jogado = [r3[0], r3[1]], r3[2]
        b2 = board.copy(); b2.push(move); fen_depois = b2.fen()
    linhas = montar_linhas(board, cands, pvs, pol)
    out_eng = []
    for nome, eng, erro, tmax in (outras or []):
        if eng is None: out_eng.append(dict(nome=nome, erro=erro)); continue
        try:
            c2, p2 = candidatos_simples(eng, board, 3, depth, tmax)
            out_eng.append(dict(nome=nome, linhas=montar_linhas(board, c2, p2)))
        except Exception as ex:
            out_eng.append(dict(nome=nome, erro=(str(ex) or type(ex).__name__)[:100] + T("e.confira")))
    return dict(fen=board.fen(), fen_depois=fen_depois, ply=board.ply() + 1, side="B" if board.turn else "P",
                move=san, uci=uci, rating=rating, cands=cands, pol=pol, linhas=linhas, depth_stable=stable,
                book_games=book, book_moves=book_moves, piece_count=pcs, tb=tb, jogado=jogado, pv_jogado=pv_jogado, outras=out_eng, tempo=tempo, game_over=board.is_game_over())


def para_posicao(raw, div_peso=0.0) -> Position:
    cl = [Candidate(s, cp, m, raw["pol"].get(s, 0.0)) for s, cp, m in raw["cands"]]
    pos = Position(cl, depth_stable=raw["depth_stable"], piece_count=raw["piece_count"],
                   book_games=raw["book_games"], rating=raw.get("rating"))
    pos.div_peso = div_peso
    t = raw.get("tempo") or {}
    pos.tempo_gasto, pos.tempo_restante = t.get("gasto"), t.get("restante")
    pos.outras = [dict(nome=o["nome"], san=o["linhas"][0]["san"]) for o in (raw.get("outras") or []) if o.get("linhas")]
    tb = raw["tb"]
    if tb:
        pos.tb_result, pos.tb_legal = tb["result"], tb["legal"]
        pos.tb_win_moves, pos.tb_hold_moves = tb["win_moves"], tb["hold_moves"]
    elif raw["piece_count"] <= ENDGAME_PIECES:  # sem tablebase: estima pelo multi-PV exaustivo
        bw = win_pct(cl[0].cp, cl[0].mate)
        pos.tb_legal = len(cl)
        pos.tb_win_moves = sum(1 for c in cl if bw - win_pct(c.cp, c.mate) <= 3)
        pos.tb_result = "win" if bw >= 90 else ("draw" if bw > 10 else "loss")
    return pos


def ratings(game):
    h = game.headers
    def r(k):
        try: return int(h.get(k, ""))
        except ValueError: return None
    return {"B": r("WhiteElo"), "P": r("BlackElo")}


def analyse_game(game, depth=16, multipv=5, maia=None, sf=None):
    own = []
    if sf is None: sf = chess.engine.SimpleEngine.popen_uci(str(SF)); own.append(sf)
    if maia is None: maia = Maia(); own.append(maia)
    rt = ratings(game)
    rows, board, em_livro = [], game.board(), True
    try:
        for node in game.mainline():
            side = "B" if board.turn else "P"
            raw = colher(board, node.move, sf, maia, rt[side], depth, multipv, em_livro)
            if em_livro: em_livro = bool(raw["book_games"] and raw["book_games"] >= 20)
            pos = para_posicao(raw)
            r = analyse(pos)
            rows.append(linha(raw, pos, r))
            board.push(node.move)
    finally:
        for e in own: (e.quit() if hasattr(e, "quit") else e.close())
    return rows


def motivos_do_porque(raw, pos, r, ap):
    """Lista do 'Por quê': os motivos gerais do índice, com a teoria explicada e os motivos concretos da posição."""
    base = [m for m in r.reasons[1:] if m != T("r.teoria")]
    novos = explicar_porque(raw, pos, ap)
    return novos[:1] + base + novos[1:] if novos and "teoria" in r.flags else base + novos


def linha(raw, pos, r):
    """Linha de resultados de uma posição. Sem lance jogado (posição atual), os campos de jogada ficam vazios."""
    brancas = raw["side"] == "B"
    _l0 = raw["linhas"][0] if raw.get("linhas") else None
    ip, tp, contrib = indice_posicao(chess.Board(raw["fen"]), (_l0["cp"] if _l0 and _l0.get("mate") is None else None))
    postos = texto_postos(chess.Board(raw["fen"]))   # postos avançados, em uma frase curta
    rei_txt = texto_rei(chess.Board(raw["fen"]))     # rei sob pressão (xeque, casas de fuga, raio-x)
    pecas_txt = texto_pecas(chess.Board(raw["fen"]))   # cavalos mal colocados, bispos ruins, peões passados avançados
    deb = texto_debilidades(chess.Board(raw["fen"]))   # quem tem mais debilidades e se estão sendo aproveitadas
    ecp = raw["linhas"][0]["cp"] if raw["linhas"] else None   # avaliação ORIGINAL da engine (brancas), só para o resíduo
    ap = analise_posicao(chess.Board(raw["fen"]), ecp)
    d = dict(ply=raw["ply"], side=raw["side"], move=raw["move"], uci=raw["uci"], rating=raw["rating"],
             fen=raw["fen"], fen_depois=raw["fen_depois"],
             engine_brancas=round(r.eval_pct if brancas else 100 - r.eval_pct, 1),
             engine_cp=raw["linhas"][0]["cp"] if raw["linhas"] else None,
             engine_mate=raw["linhas"][0]["mate"] if raw["linhas"] else None,
             indice=round(r.index, 1), indice_bruto=round(r.index_bruto, 1), faixa=r.band,
             posicao_brancas=round(ip, 1), posicao_texto=(tp + (" " + deb if deb else "") + (" " + postos if postos else "") + (" " + pecas_txt if pecas_txt else "") + (" " + rei_txt if rei_txt else "")),
             material_brancas=round(ap["material_idx"], 1), estrutura_brancas=round(ap["estrutura_idx"], 1),
             posicao_cp=ap["cp"], material_cp=ap["material_cp"], posicao_grupos=ap["grupos"], posicao_residuo=ap["residuo"],
             posicao_componentes={k: round(v) for k, v in contrib.items() if abs(v) >= 3},
             aval_pct=round(r.eval_pct, 1), melhor=pos.candidates[0].san, melhor_uci=raw["linhas"][0]["uci"],
             linhas=raw["linhas"], outras=raw.get("outras") or [], flags=r.flags,
             fonte_final=("tablebase" if raw["tb"] else ("estimado" if raw["piece_count"] <= ENDGAME_PIECES else "")),
             teoria_partidas=raw["book_games"], resumo=r.headline, motivos=" | ".join(motivos_do_porque(raw, pos, r, ap)),
             indice_tempo=(None if r.index_tempo is None else round(r.index_tempo, 1)), tempo_texto=r.tempo_texto,
             tempo_gasto=(raw.get("tempo") or {}).get("gasto"), tempo_restante=(raw.get("tempo") or {}).get("restante"),
             jogada_indice=None, jogada_classe=None, jogada_classe_id=None, jogada_texto=None, jogado_perda=None)
    tab = chess.Board(raw["fen"])
    variantes = [l.get("pv_uci") for l in raw.get("linhas") or []]
    d["motivos"] = marca_notacao(d["motivos"], tab, variantes)          # lances e casas citados: negrito, marcados no tabuleiro
    d["avaliacao_texto"] = marca_notacao(explicar_avaliacao(raw) or "", tab, variantes)   # por que a engine avalia assim (não altera o valor dela)
    if raw["jogado"] is not None:
        cp, mate = raw["jogado"]
        depois = win_pct(cp, mate)  # de quem jogou, depois do lance
        perda = round(r.eval_pct - depois, 1)
        nota, cid, txt = indice_jogada(perda, r.index, r.eval_pct, depois)
        txt = explicar_lance(raw, cid, r.index, r.eval_pct, depois) or txt   # explicação concreta (material, mate, xeque...)
        txt = marca_notacao(txt, tab, variantes + [raw.get("pv_jogado")])
        d.update(jogada_indice=round(nota, 1), jogada_classe=nome_classe(cid), jogada_classe_id=cid, jogada_texto=txt, jogado_perda=perda)
    d["critico"] = momento_critico(raw, r.index)      # posição em que a partida se decide (ou None)
    return d


def linha_final(board, rating=None, tempo=None):
    """Posição final da partida (xeque-mate, afogamento, empate): sem lances, a engine não é consultada."""
    if board.is_checkmate():
        brancas_vencem = not board.turn
        resumo = T("f.mate", l=T("w.brancas") if brancas_vencem else T("w.pretas"))
        eng = 100.0 if brancas_vencem else 0.0
    else:
        resumo, eng = T("f.empate"), 50.0
    ip, tp, _ = indice_posicao(board)
    ap = analise_posicao(board, None)
    return dict(ply=board.ply() + 1, side="B" if board.turn else "P", move=None, uci=None, rating=rating, fen=board.fen(), fen_depois=None,
                engine_brancas=eng, engine_cp=None, engine_mate=None, indice=100.0, indice_bruto=100.0, faixa=T("f.faixa"),
                posicao_brancas=round(ip, 1), posicao_texto=tp, material_brancas=round(ap["material_idx"], 1),
                estrutura_brancas=round(ap["estrutura_idx"], 1), posicao_cp=ap["cp"], material_cp=ap["material_cp"],
                posicao_grupos=ap["grupos"], posicao_residuo=None, aval_pct=eng, melhor=None, melhor_uci=None, linhas=[], outras=[],
                flags=["fim"], fonte_final="", teoria_partidas=None, resumo=resumo, motivos="", indice_tempo=None, tempo_texto="",
                tempo_gasto=None, tempo_restante=(tempo or {}).get("restante"), jogada_indice=None, jogada_classe=None, jogada_classe_id=None,
                jogada_texto=None, jogado_perda=None, critico=None)


def paineis(rows):
    """Os 4 índices de cada momento: Engine, Chance de Acerto, Posição e Jogada (do lance anterior)."""
    out = []
    for i, r in enumerate(rows):
        ant = rows[i - 1] if i else None
        out.append(dict(ply=r["ply"], vez=r["side"], engine_brancas=r["engine_brancas"], acerto=r["indice"],
                        posicao_brancas=r["posicao_brancas"],
                        jogada_anterior=(ant["jogada_indice"] if ant else None),
                        jogada_anterior_classe=(ant["jogada_classe"] if ant else None),
                        jogada_anterior_lance=(ant["move"] if ant else None)))
    return out
