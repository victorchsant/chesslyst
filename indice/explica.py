"""Explica um lance em linguagem natural: o que aconteceu de concreto no tabuleiro.

Simula a variante que a engine espera (depois do lance jogado e depois do melhor lance) e descreve o resultado:
material perdido ou ganho, xeque-mate permitido ou perdido, xeque, roque... Sem números sem significado.
"""
from __future__ import annotations
from collections import Counter
import chess
from .i18n import T, lang
from .posicional import desc_material, material as _material, analise as _analise_pos

VAL = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9}
# (artigo+singular, plural, feminino?)
PT = {chess.PAWN: ("um peão", "peões", False), chess.KNIGHT: ("um cavalo", "cavalos", False), chess.BISHOP: ("um bispo", "bispos", False),
      chess.ROOK: ("uma torre", "torres", True), chess.QUEEN: ("a dama", "damas", True)}
EN = {chess.PAWN: ("a pawn", "pawns"), chess.KNIGHT: ("a knight", "knights"), chess.BISHOP: ("a bishop", "bishops"),
      chess.ROOK: ("a rook", "rooks"), chess.QUEEN: ("the queen", "queens")}
NUM_PT = {2: ("dois", "duas"), 3: ("três", "três")}
NUM_EN = {2: "two", 3: "three"}


def _n_peca(pt, n):
    if lang() == "en":
        sing, plur = EN[pt]
        return sing if n == 1 else f"{NUM_EN.get(n, n)} {plur}"
    sing, plur, fem = PT[pt]
    if n == 1: return sing
    num = NUM_PT.get(n)
    return f"{num[1] if fem else num[0]} {plur}" if num else f"{n} {plur}"


def _lista(tipos):
    """'um cavalo e um peão' (no máximo dois grupos, do mais valioso ao menos)."""
    c = Counter(tipos)
    itens = sorted(c.items(), key=lambda kv: -VAL[kv[0]])[:2]
    return (" and " if lang() == "en" else " e ").join(_n_peca(pt, n) for pt, n in itens)


def _seq(board, ucis, limite=8):
    """Simula a variante. Material do ponto de vista de quem joga na posição inicial."""
    b = board.copy(); eu = b.turn
    perdeu, ganhou, passos = [], [], []
    todos = list(ucis or [])
    for k, u in enumerate(todos):
        # corta em `limite` lances, mas não no meio de uma troca: segue enquanto o último lance foi captura (até +4)
        if k >= limite and not (passos and passos[-1]["cap"] and k < limite + 4): break
        try: m = chess.Move.from_uci(u)
        except ValueError: break
        if m not in b.legal_moves: break
        quem = b.turn
        cap = chess.PAWN if b.is_en_passant(m) else (b.piece_type_at(m.to_square) if b.is_capture(m) else None)
        if cap: (ganhou if quem == eu else perdeu).append(cap)
        passos.append(dict(meu=(quem == eu), move=m, cap=cap, destino=m.to_square))
        b.push(m)
    p_net, g_net = Counter(perdeu) - Counter(ganhou), Counter(ganhou) - Counter(perdeu)
    return dict(perdeu=list(p_net.elements()), ganhou=list(g_net.elements()), passos=passos, n_ganhou=len(ganhou),
                liquido=sum(VAL[t] for t in ganhou) - sum(VAL[t] for t in perdeu))


def _cap(s):
    return s[:1].upper() + s[1:]


def _ideia(board, melhor, seq_b, mate_b, net_j, eval_antes, permitiu_mate=False):
    """Complemento do 'O melhor era X': o que o melhor lance fazia."""
    if permitiu_mate: return T("x.i_evita_mate")
    if mate_b is not None and mate_b > 0: return T("x.i_mate", n=mate_b)
    if seq_b["liquido"] >= 1.5 and seq_b["ganhou"]: return T("x.i_ganha", p=_lista(seq_b["ganhou"]))
    try:
        m = chess.Move.from_uci(melhor["uci"])
        if board.gives_check(m): return T("x.i_xeque")
        if board.is_capture(m):
            return T("x.i_captura", p=_n_peca(chess.PAWN if board.is_en_passant(m) else board.piece_type_at(m.to_square), 1))
    except ValueError:
        pass
    if net_j <= -1: return T("x.i_evita")
    return T("x.i_vant") if eval_antes >= 60 else (T("x.i_seg") if eval_antes <= 40 else T("x.i_eq"))


def _em_risco(board, cor):
    """Casas das peças (não peões/rei) de `cor` que podem ser capturadas com ganho: sem defesa, ou atacadas por peça menor."""
    r = set()
    for sq, pc in board.piece_map().items():
        if pc.color != cor or pc.piece_type in (chess.PAWN, chess.KING): continue
        atac = board.attackers(not cor, sq)
        if not atac: continue
        menor = min(VAL[board.piece_type_at(a)] if board.piece_type_at(a) != chess.KING else 99 for a in atac)
        if not board.is_attacked_by(cor, sq) or menor < VAL[pc.piece_type]: r.add(sq)
    return r


_ART_PT = {chess.PAWN: ("o peão", "ao peão", "do peão"), chess.KNIGHT: ("o cavalo", "ao cavalo", "do cavalo"),
           chess.BISHOP: ("o bispo", "ao bispo", "do bispo"), chess.ROOK: ("a torre", "à torre", "da torre"), chess.QUEEN: ("a dama", "à dama", "da dama")}
_ART_EN = {chess.PAWN: "the pawn", chess.KNIGHT: "the knight", chess.BISHOP: "the bishop", chess.ROOK: "the rook", chess.QUEEN: "the queen"}


def _mobilidade(board, sq):
    """Casas para onde a peça em `sq` pode ir (sem contar as ocupadas por peças da mesma cor)."""
    pc = board.piece_at(sq)
    return len(board.attacks(sq) & ~board.occupied_co[pc.color]) if pc else 0


def _no_centro(sq):
    return 2 <= chess.square_file(sq) <= 5 and 2 <= chess.square_rank(sq) <= 5


def _efeito(board, move):
    """O que o lance faz de concreto na posição (não é material): (id, texto, positivo) ou None.
    Ex.: 'Desenvolve o cavalo.', 'Dá mais mobilidade ao bispo.', 'Ataca a dama.'"""
    try:
        pt = board.piece_type_at(move.from_square)
        if pt not in _ART_EN or board.is_castling(move): return None
        cor = board.turn
        b2 = board.copy(); b2.push(move)
        art, a_, de_ = (_ART_EN[pt],) * 3 if lang() == "en" else _ART_PT[pt]
        if not board.is_capture(move):                      # ataca uma peça maior ou sem defesa
            alvos = [s for s in b2.attacks(move.to_square) if (p := b2.piece_at(s)) and p.color != cor and p.piece_type not in (chess.KING, chess.PAWN)
                     and (VAL[p.piece_type] > VAL.get(pt, 0) or not b2.is_attacked_by(not cor, s))]
            if alvos and not (b2.is_attacked_by(not cor, move.to_square) and not b2.is_attacked_by(cor, move.to_square)):
                alvo = max(alvos, key=lambda s: VAL[b2.piece_type_at(s)])
                return "ataca", T("x.ataca", p=_n_peca(b2.piece_type_at(alvo), 1)), True
        recuo = 0 if cor == chess.WHITE else 7
        if pt in (chess.KNIGHT, chess.BISHOP) and chess.square_rank(move.from_square) == recuo and chess.square_rank(move.to_square) != recuo:
            return "desenvolve", T("x.desenv", o=art), True
        if pt == chess.KNIGHT and _no_centro(move.to_square) and not _no_centro(move.from_square):
            return "centraliza", T("x.centraliza", o=art), True
        if pt != chess.PAWN:
            d = _mobilidade(b2, move.to_square) - _mobilidade(board, move.from_square)
            if d >= 3: return "mob_mais", T("x.mob_mais", o=a_), True
            if d <= -3: return "mob_menos", T("x.mob_menos", o=de_), False
    except Exception:
        return None
    return None


def _r(info, causa, texto):
    """Devolve o texto e, se pedido, registra qual causa foi usada (serve para calibrar)."""
    if info is not None: info["causa"] = causa
    return texto


def explicar_lance(raw, cid, acerto, eval_antes, eval_depois, info=None):
    """Texto do lance jogado, ou None se faltam dados (partidas analisadas por versões antigas).
    Se `info` (dict) for dado, grava nele a causa escolhida e as variáveis usadas."""
    if not raw.get("pv_jogado") or not raw.get("linhas") or not raw.get("uci"): return None
    board = chess.Board(raw["fen"])
    move = chess.Move.from_uci(raw["uci"])
    melhor = raw["linhas"][0]
    san_melhor = melhor["san"]
    mate_b = raw["cands"][0][2]
    cp_j, mate_j = raw["jogado"]
    jog, best = _seq(board, raw["pv_jogado"]), _seq(board, melhor.get("pv_uci"))
    net_j, net_b = jog["liquido"], best["liquido"]
    jogou_melhor = raw["move"] == san_melhor
    pm = board.piece_type_at(move.from_square)
    if info is not None: info.update(net_j=net_j, net_b=net_b, cid=cid)

    # ---- o melhor lance (ou brilhante): descreve o que ele faz
    if cid in ("melhor", "brilhante") or jogou_melhor:
        b2 = board.copy(); b2.push(move)
        if b2.is_checkmate(): return _r(info, "mate1", T("x.mate1"))
        if cid == "brilhante" and net_j <= -2 and eval_depois >= 55 and jog["perdeu"]:
            return _r(info, "sacrificio", T("x.sacrificio", p=_lista(jog["perdeu"])))
        if mate_b is not None and mate_b > 0: return _r(info, "mate_forcado", T("x.mate_forcado", n=mate_b))
        if cid == "brilhante": return _r(info, "preciso", T("x.preciso"))
        if board.is_castling(move): return _r(info, "roque", T("x.roque"))
        if move.promotion: return _r(info, "promove", T("x.promove"))
        if board.is_capture(move):
            return _r(info, "captura", T("x.captura", p=_n_peca(chess.PAWN if board.is_en_passant(move) else board.piece_type_at(move.to_square), 1)))
        if board.gives_check(move): return _r(info, "xeque", T("x.xeque"))
        ef = _efeito(board, move)
        ef = ef if ef and ef[2] else None          # só efeitos positivos num bom lance
        return _r(info, "melhor_generico" + ("+" + ef[0] if ef else ""), T("j.melhor") + (" " + ef[1] if ef else ""))

    permitiu = (mate_j is not None and mate_j < 0) or bool(jog["passos"] and _mate_contra(board, raw["pv_jogado"]))
    perdeu_mate = mate_b is not None and mate_b > 0 and (mate_j is None or mate_j <= 0)
    ideia = "" if perdeu_mate and not permitiu else _ideia(board, melhor, best, mate_b, net_j, eval_antes, permitiu)
    melhor_era = T("x.melhor_era", m=san_melhor, i=ideia)
    ef = _efeito(board, move)
    ef = ef if ef and ef[2] else None
    if cid == "excelente": return _r(info, "quase" + ("+" + ef[0] if ef else ""), T("x.quase", m=san_melhor) + (" " + ef[1] if ef else ""))
    if cid == "bom": return _r(info, "bom" + ("+" + ef[0] if ef else ""), T("x.bom", m=san_melhor) + (" " + ef[1] if ef and ef[2] else ""))

    # ---- imprecisão / erro / erro grave: a causa, em ordem de importância
    falta_ganhar = net_b - net_j
    primeira = next((p for p in jog["passos"] if not p["meu"] and p["cap"]), None)
    if info is not None: info["falta_ganhar"] = falta_ganhar

    idx_perda = next((k for k, p in enumerate(jog["passos"]) if not p["meu"] and p["cap"]), None)   # 1 = logo depois, 3 = dois lances...

    def perdeu_algo():
        if jog["n_ganhou"] == 0 and primeira and primeira["destino"] == move.to_square and pm in VAL:
            return "perdeu_sem_defesa", T("x.sem_defesa", p=_n_peca(pm, 1))
        if jog["n_ganhou"] > 0: return "perdeu_troca", T("x.perdeu_troca", p=_lista(jog["perdeu"]))
        return "perdeu", T("x.perdeu", p=_lista(jog["perdeu"]))

    omite = False
    perda = -net_j
    ja_risco = _em_risco(board, board.turn)
    b2 = board.copy(); b2.push(move)
    novo_risco = [sq for sq in _em_risco(b2, board.turn) if sq not in ja_risco or sq == move.to_square]
    if permitiu:
        k, causa = "permitiu_mate", T("x.permitiu_mate", n=abs(mate_j) if mate_j else 1)
    elif perdeu_mate:
        k, causa = "perdeu_mate", T("x.perdeu_mate", n=mate_b)
    elif perda >= 1 and jog["perdeu"] and falta_ganhar >= 1 and perda >= falta_ganhar / 2:
        k, causa = perdeu_algo()          # o lance custa material (e o melhor lance não custava o mesmo)
    elif falta_ganhar >= 1.5 and best["ganhou"]:
        k, causa, omite = "deixou_ganhar", T("x.deixou_ganhar", p=_lista(best["ganhou"])), True
    elif eval_antes >= 90 and eval_depois < 60: k, causa = "escapar", T("x.escapar")
    elif eval_antes >= 40 and eval_depois < 15: k, causa = "perdida", T("x.perdida")
    elif eval_antes >= 60 and eval_depois < 45: k, causa = "vantagem", T("x.vantagem")
    elif novo_risco and not board.is_capture(move) and not board.gives_check(move): k, causa = "peca_risco", T("x.risco", p=_n_peca(b2.piece_type_at(novo_risco[0]), 1))
    elif board.has_castling_rights(board.turn) and not b2.has_castling_rights(board.turn) and not board.is_castling(move):
        k, causa = "perdeu_roque", T("x.perdeu_roque")
    else:
        ef = _efeito(board, move)
        if ef and not ef[2]: k, causa = "piorou+" + ef[0], T("x.piorou_mob", e=ef[1])
        else: k, causa = "piorou", T("x.piorou")
    if k in ("perdeu", "perdeu_troca") and idx_perda is not None and idx_perda >= 3:      # perda que não vem logo: diz em quantos lances
        causa = T("x.perde_em", p=_lista(jog["perdeu"]), n=(idx_perda + 1) // 2)
    texto = causa + (T("x.melhor_era", m=san_melhor, i="") if omite else melhor_era)   # sem repetir o que já foi dito
    if acerto >= 75 and cid in ("erro", "grave"): texto += T("j.facil")
    return _r(info, k, texto)


def _quando(k):
    return T("a.q_prox") if k <= 1 else (T("a.q_pouco") if k <= 3 else T("a.q_adiante"))


def explicar_avaliacao(raw, info=None):
    """Por que a engine avalia a posição assim, lendo a linha principal dela (sem alterar o valor da engine).
    Ex.: 'Vantagem das brancas: as pretas perdem a dama no próximo lance.'"""
    L = raw.get("linhas") or []
    if not L or not L[0].get("pv_uci"): return None
    board = chess.Board(raw["fen"])
    cp, mate = L[0]["cp"], L[0]["mate"]          # do ponto de vista das brancas
    if mate is not None:
        quem = T("w.brancas") if mate > 0 else T("w.pretas")
        return _r(info, "mate", T("a.mate", l=quem, n=abs(mate)))
    if cp is None: return None
    if abs(cp) < 40: return _r(info, "equilibrio", T("a.eq") + ".")
    fav = chess.WHITE if cp > 0 else chess.BLACK
    quem, outro = (T("w.brancas"), T("w.pretas")) if fav == chess.WHITE else (T("w.pretas"), T("w.brancas"))
    cabeca = T("a.lev", l=quem) if abs(cp) < 150 else (T("a.clara", l=quem) if abs(cp) < 400 else T("a.dec", l=quem))
    seq = _seq(board, L[0]["pv_uci"])
    do_lado = (fav == board.turn)                  # o favorecido é quem joga na posição?
    ganhou = seq["ganhou"] if do_lado else seq["perdeu"]     # peças que o favorecido ganha (saldo)
    liquido = seq["liquido"] if do_lado else -seq["liquido"]
    causa, k = None, "posicional"
    if liquido >= 1.5 and ganhou:
        # primeiro lance da variante em que o favorecido captura uma dessas peças
        quando = next((i for i, p in enumerate(seq["passos"]) if p["cap"] in ganhou and p["meu"] == do_lado), len(seq["passos"]))
        causa, k = T("a.c_perde", l=outro, p=_lista(ganhou), w=_quando(quando)), "perde_material"
    else:
        mat = _material(board) * (1 if fav == chess.WHITE else -1)
        if mat >= 150:
            causa, k = T("a.c_material", l=quem, d=desc_material(mat)), "material"
        else:
            grupos = [g for g in _analise_pos(board)["grupos"] if g["id"] != "material" and (g["cp"] > 0) == (fav == chess.WHITE) and abs(g["cp"]) >= 15]
            grupos.sort(key=lambda g: -abs(g["cp"]))
            if len(grupos) >= 2: causa, k = T("a.c_pos", a=grupos[0]["nome"].lower(), b=grupos[1]["nome"].lower()), "posicional"
            elif grupos: causa, k = T("a.c_pos1", a=grupos[0]["nome"].lower()), "posicional"
            else: causa, k = T("a.c_pos0"), "sem_causa"
    return _r(info, k, cabeca + ": " + causa + ".")


def _mate_contra(board, ucis):
    b = board.copy()
    for u in ucis[:8]:
        try: m = chess.Move.from_uci(u)
        except ValueError: return False
        if m not in b.legal_moves: return False
        b.push(m)
    return b.is_checkmate() and b.turn == board.turn
