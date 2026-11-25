"""Explica um lance em linguagem natural: o que aconteceu de concreto no tabuleiro.

Simula a variante que a engine espera (depois do lance jogado e depois do melhor lance) e descreve o resultado:
material perdido ou ganho, xeque-mate permitido ou perdido, xeque, roque... Sem números sem significado.
"""
from __future__ import annotations
import re
from collections import Counter
import chess
from .i18n import T, lang
from .posicional import desc_material, material as _material, analise as _analise_pos, _fase, avalia as _avalia_pos, pc, mc
from .core import win_pct as _wp
from .aberturas import nome_da_posicao
from .i18n import num as _num, P, pontos

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


def _mlance(board, move, san=None):
    """Um lance da notação em negrito: ao passar o mouse, a tela desenha a seta e marca a casa de chegada."""
    depois = board.copy(stack=False); depois.push(move)
    return mc(san or board.san(move), [chess.square_name(move.to_square)], "B" if board.turn else "P", seta=move.uci()[:4], pos=depois.fen())


# partes já marcadas ficam como estão; no resto, procura lances (SAN) e casas
_MARCADO = re.compile(r"(<b\b[^>]*>.*?</b>|<[^>]+>)", re.S)
_SAN = re.compile(r"(?<![\w-])(O-O-O|O-O|[KQRBN][a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?|[a-h]x[a-h][1-8](?:=[QRBN])?|[a-h][1-8](?:=[QRBN])?)([+#]?)(?![\w-])")


def marca_notacao(texto, board, variantes=()):
    """Põe em negrito todo lance ou casa escrito em notação e liga ao tabuleiro. Os lances são os da posição `board`
    e, depois deles, os das `variantes` (listas de lances UCI); o que não for lance é tratado como casa."""
    if not texto: return texto
    mapa = {}

    def guarda(b, m):
        s = b.san(m).rstrip("+#")
        if s not in mapa:
            depois = b.copy(stack=False); depois.push(m)
            mapa[s] = (m, b.turn, depois.fen())
    try:
        for m in board.legal_moves: guarda(board, m)
        for pv in variantes:
            b = board.copy()
            for u in pv or []:
                m = chess.Move.from_uci(u)
                if m not in b.legal_moves: break
                guarda(b, m); b.push(m)
    except Exception:
        pass

    def troca(x):
        base, tudo = x.group(1), x.group(0)
        if base in mapa:
            m, cor, fen = mapa[base]
            return mc(tudo, [chess.square_name(m.to_square)], "B" if cor else "P", seta=m.uci()[:4], pos=fen)
        if re.fullmatch(r"[a-h][1-8]", base): return mc(tudo, [base], "B" if board.turn else "P")
        return tudo
    partes = _MARCADO.split(texto)
    return "".join(p if i % 2 else _SAN.sub(troca, p) for i, p in enumerate(partes))


def _notacao(board, ucis, limite=4):
    """'8…O-O 9.Re1 d6': a continuação que a engine espera, cada lance em negrito e ligado ao tabuleiro."""
    b, out = board.copy(), []
    for k, u in enumerate((ucis or [])[:limite]):
        m = chess.Move.from_uci(u)
        if m not in b.legal_moves: break
        num = f"{b.fullmove_number}." if b.turn else (f"{b.fullmove_number}…" if k == 0 else "")
        out.append(num + _mlance(b, m)); b.push(m)
    return " ".join(out)


def _consequencia(board, pv_uci):
    """O que mais melhora para quem joga entre a posição atual e o fim da variante da engine (itens do Índice de Posição),
    quando o primeiro lance sozinho não mostra a ideia. -> frase ou None."""
    try:
        b, feitos = board.copy(), 0
        for u in (pv_uci or [])[:8]:
            m = chess.Move.from_uci(u)
            if m not in b.legal_moves: break
            b.push(m); feitos += 1
        if feitos % 2: b.pop(); feitos -= 1          # compara com a mesma vez de jogar
        while feitos >= 2 and b.move_stack and b.is_check():
            b.pop(); b.pop(); feitos -= 2
        if feitos < 2: return None
        _, c0 = _avalia_pos(board); _, c1 = _avalia_pos(b)
        sg = 1 if board.turn else -1
        d = {k: (c1[k] - c0[k]) * sg for k in c0 if k in _PZ and k != "pecas_em_risco" and _PZ[k][0]}
        if not d: return None
        k, v = max(d.items(), key=lambda kv: kv[1])
        return T(_PZ[k][0]) if v >= 12 else None
    except Exception:
        return None


def _minusc(frase):
    frase = frase.rstrip(".")
    return frase if frase.startswith("<") else frase[:1].lower() + frase[1:]


def _justifica(board, linha):
    """Por que a engine gosta deste lance: o que ele faz (ou o que a variante dela consegue). -> frase ou None."""
    mv = chess.Move.from_uci(linha["uci"]); pv = linha.get("pv_uci") or [linha["uci"]]
    seq = _seq(board, pv)
    if linha.get("mate") is not None and (linha["mate"] > 0) == bool(board.turn): return None   # a avaliação ao lado já diz "mate em N"
    if seq["liquido"] >= 1.5 and seq["ganhou"]: return T("pq.j_ganha", p=_lista(seq["ganhou"]))
    if board.is_castling(mv): return T("pq.j_roque")
    if board.is_capture(mv):
        recaptura = seq["liquido"] <= 0 and len(seq["passos"]) > 1 and seq["passos"][1]["cap"]
        p = _n_peca(chess.PAWN if board.is_en_passant(mv) else board.piece_type_at(mv.to_square), 1)
        return T("pq.j_troca" if recaptura else "pq.j_captura", p=p)
    y = _ideias(board, mv)
    if y: return _minusc(y[0][1])
    if board.gives_check(mv): return _minusc(T("x.xeque"))
    ef = _efeito(board, mv)
    if ef and ef[2]: return _minusc(ef[1])
    pz = _motivo_posicional(board, mv)
    if pz and pz[2]: return _minusc(pz[1])
    fim = _consequencia(board, pv)
    return T("pq.j_fim", i=_minusc(fim)) if fim else None


def _linha_engine(board, linha):
    """'Nf3 (+0,3): desenvolve o cavalo. Continuação da engine: 8…O-O 9.Re1.'"""
    mv = chess.Move.from_uci(linha["uci"])
    txt = f"{_mlance(board, mv, linha['san'])} ({_fmt_av(linha['cp'], linha['mate'])})"
    just = _justifica(board, linha)
    if just: txt += ": " + just
    resto = (linha.get("pv_uci") or [])[1:5]
    if resto:
        b = board.copy(); b.push(mv)
        txt += ". " + T("pq.cont", l=_notacao(b, resto))
    return txt + ("" if txt.endswith(".") else ".")


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
    try:
        y = _ideias(board, chess.Move.from_uci(melhor["uci"]))
        if y: return ", " + y[0][2]
    except ValueError:
        pass
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
                return "ataca", T("x.ataca", p=pc(b2, alvo)), True
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


_COL = "abcdefgh"
_REI = ("o rei", "the king")


def _art(pt):
    """'o cavalo' / 'the knight' (e 'o rei' / 'the king')."""
    if pt == chess.KING: return _REI[1 if lang() == "en" else 0]
    return _ART_EN[pt] if lang() == "en" else _ART_PT[pt][0]


def _fracas(board, cor):
    """Casas das peças de `cor` (não rei) atacadas com ganho para o adversário: sem defesa ou atacadas por peça menor."""
    r = set()
    for sq, pc in board.piece_map().items():
        if pc.color != cor or pc.piece_type == chess.KING: continue
        atq = board.attackers(not cor, sq)
        if not atq: continue
        menor = min(VAL.get(board.piece_type_at(a), 99) for a in atq)
        if not board.is_attacked_by(cor, sq) or menor < VAL[pc.piece_type]: r.add(sq)
    return r


def _ideias(board, move):
    """Ideias claras por trás de um lance, reconhecidas por regras (nada de palpite): [(id, frase, gerúndio)].
    Quem chama só mostra quando a engine confirma (o lance é o preferido dela ou está entre os bons)."""
    out = []

    def add(k, **kw): out.append((k, T("y." + k, **kw), T("yg." + k, **kw)))
    try:
        cor = board.turn; pt = board.piece_type_at(move.from_square)
        if pt is None or board.is_castling(move): return out
        b2 = board.copy(); b2.push(move)
        to, de = move.to_square, move.from_square
        fl = chess.square_file(to); col = _COL[fl]
        captura = board.is_capture(move)
        rel = lambda sq: chess.square_rank(sq) if cor else 7 - chess.square_rank(sq)
        seguro = not (b2.is_attacked_by(not cor, to) and not b2.is_attacked_by(cor, to))
        # 1) ataque duplo
        if not captura and seguro and pt != chess.KING:
            alvos = [s for s in b2.attacks(to) if (p := b2.piece_at(s)) and p.color != cor
                     and (p.piece_type == chess.KING or (p.piece_type != chess.PAWN and (VAL[p.piece_type] >= VAL.get(pt, 0) or not b2.is_attacked_by(not cor, s))))]
            if len(alvos) >= 2:
                alvos.sort(key=lambda s: -(99 if b2.piece_type_at(s) == chess.KING else VAL[b2.piece_type_at(s)]))
                add("garfo", a=pc(b2, alvos[0]), b=pc(b2, alvos[1]))
        # 2) cravada contra o rei
        if pt in (chess.BISHOP, chess.ROOK, chess.QUEEN) and seguro:
            for s in b2.attacks(to):
                p = b2.piece_at(s)
                if p and p.color != cor and p.piece_type in (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN) and b2.is_pinned(not cor, s) \
                        and (b2.pin(not cor, s) >> to) & 1:
                    add("cravada", p=pc(b2, s)); break
        # 3) tira uma peça do ataque / protege uma peça atacada
        if not captura:
            f0, f1 = _fracas(board, cor), _fracas(b2, cor)
            if de in f0 and to not in f1: add("salva", p=pc(b2, to))
            else:
                for s in f0:
                    if s != de and s not in f1 and board.piece_type_at(s) != chess.PAWN:
                        add("protege", p=pc(b2, s)); break
        # 4) torres
        coluna = mc(col, [col + str(n) for n in range(1, 9)], "B" if cor else "P", tipo="tinta")
        if pt == chess.ROOK and chess.square_file(de) != fl and not captura:
            outras = [s for s in b2.pieces(chess.ROOK, cor) if s != to and chess.square_file(s) == fl
                      and not any(b2.piece_at(chess.square(fl, r)) for r in range(min(chess.square_rank(s), chess.square_rank(to)) + 1, max(chess.square_rank(s), chess.square_rank(to))))]
            if outras: add("dobra", c=coluna)
            else:
                meus = [s for s in b2.pieces(chess.PAWN, cor) if chess.square_file(s) == fl]
                deles = [s for s in b2.pieces(chess.PAWN, not cor) if chess.square_file(s) == fl]
                if not meus and not deles: add("aberta", c=coluna)
                elif not meus: add("semi", c=coluna)
        if pt == chess.ROOK and rel(to) == 6 and rel(de) != 6 and not captura:
            inim7 = [s for s in b2.pieces(chess.PAWN, not cor) if rel(s) == 6]
            rei = b2.king(not cor)
            if inim7 or (rei is not None and rel(rei) == 7): add("setima")
        # 5) cavalo/bispo em posto avançado
        if pt in (chess.KNIGHT, chess.BISHOP) and 4 <= rel(to) <= 5 and not captura:
            if any(b2.piece_type_at(a) == chess.PAWN for a in b2.attackers(cor, to)) and not any(
                    abs(chess.square_file(s) - fl) == 1 and ((chess.square_rank(s) > chess.square_rank(to)) if cor else (chess.square_rank(s) < chess.square_rank(to)))
                    for s in b2.pieces(chess.PAWN, not cor)):
                add("posto", o=_art(pt), s=mc(chess.square_name(to), [chess.square_name(to)], "B" if cor else "P"))
        # 6) fianchetto
        if pt == chess.BISHOP and to in ((chess.G2, chess.B2) if cor else (chess.G7, chess.B7)):
            frente = chess.square(fl, 2 if cor else 5)
            if b2.piece_type_at(frente) == chess.PAWN and b2.color_at(frente) == cor: add("fianchetto")
        # 7) peões: peão passado avançando / quebra de peões
        if pt == chess.PAWN and not captura:
            inim = b2.pieces(chess.PAWN, not cor)
            passado = not any(abs(chess.square_file(s) - fl) <= 1 and ((chess.square_rank(s) > chess.square_rank(to)) if cor else (chess.square_rank(s) < chess.square_rank(to))) for s in inim)
            if passado and rel(to) >= 4: add("passado")
            elif any(b2.piece_type_at(s) == chess.PAWN and b2.color_at(s) != cor for s in b2.attacks(to)) and b2.is_attacked_by(cor, to): add("quebra")
        # 8) rei no final
        if pt == chess.KING and not captura and _fase(board) < 0.35:
            dc = lambda sq: abs(chess.square_file(sq) - 3.5) + abs(chess.square_rank(sq) - 3.5)
            if dc(to) < dc(de): add("rei")
    except Exception:
        return []
    ordem = ["garfo", "cravada", "dobra", "aberta", "semi", "setima", "posto", "fianchetto", "passado", "quebra", "salva", "protege", "rei"]
    return sorted(out, key=lambda x: ordem.index(x[0]) if x[0] in ordem else 99)   # a ideia mais marcante primeiro


_PZ = {   # item da análise de posição -> (frase se melhora, frase se piora)
    "mobilidade": ("pz.mob_mais", "pz.mob_menos"), "desenvolvimento": ("pz.desenv_mais", "pz.desenv_menos"),
    "centro": ("pz.centro_mais", "pz.centro_menos"), "espaco": ("pz.espaco_mais", "pz.espaco_menos"),
    "seguranca_rei": ("pz.rei_mais", "pz.rei_menos"), "rei_final": ("pz.reif_mais", "pz.reif_menos"),
    "rei_zona": ("pz.rzona_mais", "pz.rzona_menos"), "rei_raiox": ("pz.raiox_mais", "pz.raiox_menos"), "rei_fuga": ("pz.fuga_mais", "pz.fuga_menos"),
    "torres": ("pz.torres_mais", "pz.torres_menos"), "par_de_bispos": (None, "pz.bispos_menos"),
    "peoes_dobrados": ("pz.dob_mais", "pz.dob_menos"), "peoes_isolados": ("pz.iso_mais", "pz.iso_menos"),
    "peoes_passados": ("pz.pas_mais", "pz.pas_menos"), "pecas_em_risco": ("pz.risco_mais", "pz.risco_menos"),
    "casas_fracas": ("pz.fracas_mais", "pz.fracas_menos"), "postos_avancados": ("pz.posto_mais", "pz.posto_menos"),
    "ilhas_peoes": ("pz.ilhas_mais", "pz.ilhas_menos"), "mobilidade_cavalos": ("pz.cav_mais", "pz.cav_menos"),
    "bispos_maus": ("pz.bmau_mais", "pz.bmau_menos"),
}


def _motivo_posicional(board, move, limiar=8.0):
    """Compara a análise de posição (os mesmos itens da tabela) antes e depois do lance e diz o que mais mudou para quem jogou:
    (id, texto, positivo) ou None. Material fica de fora (capturas já têm explicação própria)."""
    try:
        cor = board.turn; b2 = board.copy(); b2.push(move)
        _, c0 = _avalia_pos(board); _, c1 = _avalia_pos(b2)
        sg = 1 if cor == chess.WHITE else -1
        d = {k: (c1[k] - c0[k]) * sg for k in c0 if k != "material" and k in _PZ and not (k == "pecas_em_risco" and board.is_capture(move))}   # troca: o "risco" some na recaptura
        k_mais, v_mais = max(d.items(), key=lambda kv: kv[1])
        k_menos, v_menos = min(d.items(), key=lambda kv: kv[1])
        if v_mais >= limiar and _PZ[k_mais][0] and v_mais >= -v_menos: return k_mais, T(_PZ[k_mais][0]), True
        if v_menos <= -limiar: return k_menos, T(_PZ[k_menos][1]), False
        if v_mais >= limiar and _PZ[k_mais][0]: return k_mais, T(_PZ[k_mais][0]), True
    except Exception:
        return None
    return None


def _fmt_av(cp, mate):
    """Avaliação para o texto: '+1,2' ou 'mate em 3'."""
    if mate is not None: return T("x.mate_em", n=abs(mate)) if mate > 0 else "−" + T("x.mate_em", n=abs(mate))
    return ("+" if cp >= 0 else "−") + _num(abs(cp) / 100)


def explicar_subida(prev, raw):
    """Quando a avaliação sobe muito depois do lance (a engine confirma): mostra a ideia seguinte, ex.: 'a ideia de Kd4+'.
    `prev` = análise da posição antes do lance; `raw` = análise da posição depois."""
    try:
        if not prev or prev.get("terminal") or raw.get("terminal") or not prev.get("move") or not raw.get("linhas"): return None
        a_cp, a_m = prev["cands"][0][1], prev["cands"][0][2]                  # de quem jogou, antes
        d_cp, d_m = raw["cands"][0][1], raw["cands"][0][2]                    # de quem vai jogar agora (o adversário)
        antes, depois = _wp(a_cp, a_m), 100 - _wp(d_cp, d_m)
        if depois - antes < 10: return None
        a_txt = _fmt_av(a_cp, a_m)
        b_txt = _fmt_av(-d_cp if d_cp is not None else 0, -d_m if d_m is not None else None)
        ln = raw["linhas"][0]; pv = ln.get("pv") or []; pvu = ln.get("pv_uci") or []
        if len(pv) >= 2:
            ideia, lance = "", pv[1]
            try:
                b = chess.Board(raw["fen"]); b.push(chess.Move.from_uci(pvu[0]))
                lance = _mlance(b, chess.Move.from_uci(pvu[1]), pv[1])
                y = _ideias(b, chess.Move.from_uci(pvu[1]))
                if y: ideia = ", " + y[0][2]
            except Exception: pass
            return T("x.sobe_i", a=a_txt, b=b_txt, m=lance, i=ideia)
        return T("x.sobe", a=a_txt, b=b_txt)
    except Exception:
        return None


def explicar_porque(raw, pos, ap=None):
    """'Por quê' concreto da dificuldade da posição: teoria explicada, natureza do melhor lance, quantos lances são bons e tensão tática."""
    out = []
    try:
        board = chess.Board(raw["fen"]); ln = raw["linhas"][0]; san = ln["san"]
        # 1) teoria de abertura, com o nome e os lances mais jogados pelos mestres
        bg = raw.get("book_games")
        if bg and bg >= 20:
            ab = nome_da_posicao(raw["fen"])
            tot = f"{bg:,}".replace(",", ".") if lang() != "en" else f"{bg:,}"
            txt = T("pq.teoria", ab=(f" ({ab[0]} {ab[1]})" if ab else ""), n=tot)
            top = [(s, n) for s, n in sorted((raw.get("book_moves") or {}).items(), key=lambda kv: -kv[1])[:3] if n / bg >= 0.08]
            if top: txt += " " + T("pq.teoria_m", l=", ".join(f"{s} ({round(100 * n / bg)}%)" for s, n in top))
            out.append(txt)
        # 2) o que a engine mostra: se há vários lances equivalentes, justifica cada um; senão, justifica o melhor
        L = raw["linhas"]
        bons, resto = [], []
        if pos is not None:
            bw = _wp(pos.candidates[0].cp, pos.candidates[0].mate)
            perda = {c.san: bw - _wp(c.cp, c.mate) for c in pos.candidates}
            bons = [l for l in L if perda.get(l["san"], 99) <= 3]
            resto = [l for l in L if perda.get(l["san"], 99) > 3]
        em_teoria = bool(bg and bg >= 20)
        if len(bons) >= 3:
            mostra = bons[:3]
            dif = max(perda[l["san"]] for l in mostra)
            txt = T("pq.varios", n=len(bons), d=_num(max(dif, 0.0)), u=pontos(max(dif, 0.0))) + "".join("<br>• " + _linha_engine(board, l) for l in mostra)
            if resto:
                r0 = resto[0]
                txt += "<br>" + T("pq.fora", m=_mlance(board, chess.Move.from_uci(r0["uci"]), r0["san"]), a=_fmt_av(r0["cp"], r0["mate"]), d=_num(perda[r0["san"]], 0))
            out.append(txt)
        else:
            mate = raw["cands"][0][2]
            mv = chess.Move.from_uci(ln["uci"]); seq = _seq(board, ln.get("pv_uci"))
            primeiro = next((k for k, p in enumerate(seq["passos"]) if p["meu"] and p["cap"]), None)
            if not (mate is not None and mate > 0) and seq["liquido"] >= 1.5 and seq["ganhou"] and primeiro is not None:
                out.append(T("pq.ganha", m=san, p=_lista(seq["ganhou"]), n=primeiro // 2 + 1, l=_notacao(board, ln.get("pv_uci"), primeiro + 2)))
            elif not em_teoria or _justifica(board, ln):
                out.append(T("pq.ideia", i=_linha_engine(board, ln)))
            if resto and len(bons) == 1 and perda[resto[0]["san"]] >= 5:        # o preço de não achar o lance
                r0 = resto[0]
                b2 = board.copy(); b2.push(chess.Move.from_uci(r0["uci"]))
                resposta = (r0.get("pv_uci") or [])[1:4]
                out.append(T("pq.segundo", m=_mlance(board, chess.Move.from_uci(r0["uci"]), r0["san"]), a=_fmt_av(r0["cp"], r0["mate"]),
                             d=_num(perda[r0["san"]], 0)) + (" " + T("pq.resposta", l=_notacao(b2, resposta, 3)) if resposta else ""))
        # 4) peças em risco na posição: tática
        if ap:
            risco = next((i for g in ap["grupos"] for i in g["itens"] if i["chave"] == "pecas_em_risco"), None)
            if risco and abs(risco["cp"]) >= 50: out.append(T("pq.risco"))
    except Exception:
        pass
    return out[:4]


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
        y = _ideias(board, move)
        if y: return _r(info, "melhor_generico+ideia_" + y[0][0], T("j.melhor") + " " + y[0][1])
        if not ef:
            pz = _motivo_posicional(board, move)
            if pz and pz[2]: return _r(info, "melhor_generico+pz_" + pz[0], T("j.melhor") + " " + pz[1])
        return _r(info, "melhor_generico" + ("+" + ef[0] if ef else ""), T("j.melhor") + (" " + ef[1] if ef else ""))

    permitiu = (mate_j is not None and mate_j < 0) or bool(jog["passos"] and _mate_contra(board, raw["pv_jogado"]))
    perdeu_mate = mate_b is not None and mate_b > 0 and (mate_j is None or mate_j <= 0)
    ideia = "" if perdeu_mate and not permitiu else _ideia(board, melhor, best, mate_b, net_j, eval_antes, permitiu)
    melhor_era = T("x.melhor_era", m=san_melhor, i=ideia)
    ef = _efeito(board, move)
    ef = ef if ef and ef[2] else None
    y = _ideias(board, move)
    if y: ef = (  "ideia_" + y[0][0], y[0][1], True)          # ideia clara, confirmada pela engine (lance entre os melhores)
    elif not ef:
        pz = _motivo_posicional(board, move)
        if pz and pz[2]: ef = ("pz_" + pz[0], pz[1], True)
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
        pz = _motivo_posicional(board, move)
        if ef and not ef[2]: k, causa = "piorou+" + ef[0], T("x.piorou_mob", e=ef[1])
        elif pz and not pz[2]: k, causa = "piorou+pz_" + pz[0], T("x.piorou_mob", e=pz[1])
        else: k, causa = "piorou", T("x.piorou")
    if k in ("perdeu", "perdeu_troca") and idx_perda is not None and idx_perda >= 3:      # perda que não vem logo: diz em quantos lances
        causa = T("x.perde_em", p=_lista(jog["perdeu"]), n=(idx_perda + 1) // 2)
    texto = causa + (T("x.melhor_era", m=san_melhor, i="") if omite else melhor_era)   # sem repetir o que já foi dito
    if acerto >= 75 and cid in ("erro", "grave"): texto += T("j.facil")
    return _r(info, k, texto)


def _quando(k):
    return T("a.q_prox") if k <= 1 else (T("a.q_pouco") if k <= 3 else T("a.q_adiante"))


def _nome_vantagem(g):
    """Nome do grupo da análise de posição em linguagem natural, para dizer de onde vem a vantagem (ex.: 'rei longe de ataques')."""
    if g["id"] == "rei":
        it = max(g["itens"], key=lambda i: abs(i["cp"]))
        return T({"rei_final": "gv.reif", "rei_fuga": "gv.fuga"}.get(it["chave"], "gv.rei"))
    return T("gv." + g["id"])


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
            if len(grupos) >= 2: causa, k = T("a.c_pos", a=_nome_vantagem(grupos[0]), b=_nome_vantagem(grupos[1])), "posicional"
            elif grupos: causa, k = T("a.c_pos1", a=_nome_vantagem(grupos[0])), "posicional"
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


def texto_repeticao(fens, lances, i):
    """A posição i já apareceu antes na partida? Repetição de lances e xeque perpétuo (empate)."""
    try:
        if i < 4 or i >= len(fens): return ""
        ep = lambda f: " ".join(f.split()[:4])
        n = sum(1 for f in fens[:i + 1] if ep(f) == ep(fens[i]))
        if n < 2: return ""
        lado_xeque = None
        for lado in (0, 1):                  # 0 = brancas jogaram o lance j (j par), 1 = pretas
            if sum(1 for j in range(max(0, i - 6), min(i, len(lances))) if j % 2 == lado and lances[j].endswith(("+", "#"))) >= 2: lado_xeque = lado
        b = chess.Board(fens[i])
        if lado_xeque is not None:
            quem = T("w.brancas") if lado_xeque == 0 else T("w.pretas")
            resp = b.legal_moves.count() if b.is_check() else None
            extra = T("rp.so", n=resp, v=P(resp, "rp.resp")) if resp is not None and resp <= 2 else ""
            return T("rp.perpetuo", l=quem, n=n, e=extra)
        return T("rp.rep3" if n >= 3 else "rp.rep2", n=n)
    except Exception:
        return ""
