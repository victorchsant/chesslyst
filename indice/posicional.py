"""Índice de Posição: avaliação ESTÁTICA da posição (material + estrutura), explicada item a item.

Cada componente é medido como (brancas - pretas) com python-chess e multiplicado por um peso em centipeões
(`posicional.json`, ajustado por regressão contra a avaliação do Stockfish em posições calmas; valores iniciais
abaixo). Ele NÃO usa a avaliação da engine para calcular o índice: serve para explicar o que compõe a avaliação.
A diferença entre a engine e o estático é mostrada como "dinâmica / tática" (resíduo).
"""
from __future__ import annotations
import json
from pathlib import Path
import chess
from .core import win_pct
from .i18n import T, num

VAL = {chess.PAWN: 100, chess.KNIGHT: 320, chess.BISHOP: 330, chess.ROOK: 500, chess.QUEEN: 900}

ITENS = ["material", "peoes_dobrados", "peoes_isolados", "peoes_passados", "mobilidade", "desenvolvimento", "torres", "centro",
         "espaco", "par_de_bispos", "seguranca_rei", "rei_final", "pecas_em_risco", "casas_fracas", "postos_avancados"]
GRUPOS = [   # (id, componentes)
    ("material", ["material"]),
    ("estrutura", ["peoes_dobrados", "peoes_isolados", "peoes_passados"]),
    ("atividade", ["mobilidade", "desenvolvimento", "torres", "centro", "espaco", "par_de_bispos"]),
    ("rei", ["seguranca_rei", "rei_final"]),
    ("debilidades", ["pecas_em_risco", "casas_fracas"]),
    ("postos", ["postos_avancados"]),
]


def nome_item(k): return T(f"it.{k}.n")
def desc_item(k): return T(f"it.{k}.d")


PESOS0 = {"material": 1.0, "mobilidade": 4.0, "par_de_bispos": 30.0, "peoes_dobrados": -15.0, "peoes_isolados": -12.0,
          "peoes_passados": 12.0, "seguranca_rei": 10.0, "rei_final": 8.0, "centro": 8.0, "torres": 15.0,
          "desenvolvimento": -12.0, "espaco": 3.0, "pecas_em_risco": -40.0, "casas_fracas": -6.0, "postos_avancados": 25.0}
_f = Path(__file__).resolve().parent.parent / "posicional.json"
_dados = json.loads(_f.read_text(encoding="utf-8")) if _f.exists() else {}
PESOS = {**PESOS0, **_dados.get("pesos", {})}
REGRA = set(_dados.get("regra", []))   # pesos definidos por regra (não validados pelos dados)
CENTRO = [chess.D4, chess.E4, chess.D5, chess.E5]


def material(b):
    return sum(v * (len(b.pieces(t, True)) - len(b.pieces(t, False))) for t, v in VAL.items())


def _fase(b):
    """1 = abertura/meio-jogo cheio, 0 = final sem peças."""
    n = sum({1: 0, 2: 1, 3: 1, 4: 2, 5: 4}[t] * (len(b.pieces(t, True)) + len(b.pieces(t, False))) for t in range(1, 6))
    return min(1.0, n / 24)


def _lado(b, c, fase):
    own, opp = b.occupied_co[c], not c
    r = lambda sq: chess.square_rank(sq) if c else 7 - chess.square_rank(sq)  # fileira relativa 0..7
    f = dict.fromkeys((k for k in PESOS0 if k != "material"), 0.0)
    for t in (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN):
        for sq in b.pieces(t, c):
            f["mobilidade"] += chess.popcount(b.attacks_mask(sq) & ~own) / 10
    f["par_de_bispos"] = float(len(b.pieces(chess.BISHOP, c)) >= 2)
    peoes, inim = b.pieces(chess.PAWN, c), b.pieces(chess.PAWN, opp)
    cols = [0] * 8
    for sq in peoes: cols[chess.square_file(sq)] += 1
    for sq in peoes:
        fl = chess.square_file(sq)
        if not (cols[max(0, fl - 1)] * (fl > 0) + cols[min(7, fl + 1)] * (fl < 7)): f["peoes_isolados"] += 1
        frente = [s for s in inim if abs(chess.square_file(s) - fl) <= 1 and
                  (chess.square_rank(s) > chess.square_rank(sq) if c else chess.square_rank(s) < chess.square_rank(sq))]
        if not frente: f["peoes_passados"] += (r(sq) / 6) ** 2 * (1 + (1 - fase))
        if r(sq) >= 3: f["espaco"] += r(sq) - 2
    f["peoes_dobrados"] = float(sum(max(0, n - 1) for n in cols))
    k = b.king(c)
    if k is not None:
        kf, kr = chess.square_file(k), r(k)
        escudo = sum(1 for sq in peoes if abs(chess.square_file(sq) - kf) <= 1 and 0 < r(sq) - kr <= 2)
        zona = chess.SquareSet(chess.BB_KING_ATTACKS[k]) | chess.SquareSet.from_square(k)
        atq = sum(len(b.attackers(opp, s)) for s in zona)
        f["seguranca_rei"] = fase * (escudo - 0.6 * atq)
        f["rei_final"] = (1 - fase) * (3.5 - (abs(chess.square_file(k) - 3.5) + abs(chess.square_rank(k) - 3.5)) / 2)
    for sq in CENTRO:
        f["centro"] += len(b.attackers(c, sq)) * 0.5 + (1.0 if b.piece_at(sq) == chess.Piece(chess.PAWN, c) else 0)
    for sq in b.pieces(chess.ROOK, c):
        fl = chess.square_file(sq)
        if cols[fl] == 0: f["torres"] += 1.0 if not any(chess.square_file(s) == fl for s in inim) else 0.5
        if r(sq) == 6: f["torres"] += 0.8
    casa = 0 if c else 7
    f["desenvolvimento"] = fase * sum(1 for t in (chess.KNIGHT, chess.BISHOP) for sq in b.pieces(t, c)
                                      if chess.square_rank(sq) == casa)
    # --- debilidades: peças em risco (a vez de quem joga pesa metade: dá tempo de salvar)
    for t in (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN):
        for sq in b.pieces(t, c):
            atq = list(b.attackers(opp, sq))
            if not atq: continue
            v = VAL[t]
            menor = min(VAL.get(b.piece_type_at(a), 10_000) for a in atq)
            if not b.attackers(c, sq): risco = v / 100
            elif menor < v: risco = (v - menor) / 100
            else: continue
            f["pecas_em_risco"] += risco * (0.5 if b.turn == c else 1.0)
    # --- casas fracas: casas das fileiras 3-5 (relativas) que nenhum peão seu poderá defender
    for fl in range(1, 7):
        for rr in (2, 3, 4):
            if not any(abs(chess.square_file(p) - fl) == 1 and r(p) < rr for p in peoes): f["casas_fracas"] += 1
    # --- postos avançados: cavalo/bispo em casa avançada, defendido por peão, sem peão adversário que o expulse
    for t, peso in ((chess.KNIGHT, 1.0), (chess.BISHOP, 0.5)):
        for sq in b.pieces(t, c):
            if not 4 <= r(sq) <= 6: continue
            if not any(b.piece_type_at(a) == chess.PAWN for a in b.attackers(c, sq)): continue
            fl = chess.square_file(sq)
            if any(abs(chess.square_file(s) - fl) == 1 and
                   (chess.square_rank(s) > chess.square_rank(sq) if c else chess.square_rank(s) < chess.square_rank(sq))
                   for s in inim): continue
            f["postos_avancados"] += peso
    return f


def componentes(b: chess.Board) -> dict:
    fase = _fase(b)
    w, p = _lado(b, chess.WHITE, fase), _lado(b, chess.BLACK, fase)
    comp = {k: w[k] - p[k] for k in w}
    comp["material"] = float(material(b))
    return comp


def avalia(b: chess.Board):
    """-> (centipeões da avaliação estática do ponto de vista das brancas, contribuição de cada componente)."""
    comp = componentes(b)
    contrib = {k: PESOS.get(k, 0.0) * v for k, v in comp.items()}
    return sum(contrib.values()), contrib


def _lado_txt(v):
    return T("w.equilibrio") if abs(v) < 5 else (T("w.brancas") if v > 0 else T("w.pretas"))


def analise(b: chess.Board, engine_cp=None):
    """Interpretação geral item a item. engine_cp = avaliação da engine (brancas), só para mostrar o resíduo."""
    cp, contrib = avalia(b)
    mat = contrib["material"]
    grupos = []
    for gid, chaves in GRUPOS:
        itens = [dict(chave=k, nome=nome_item(k), desc=desc_item(k), cp=round(contrib[k]), lado=_lado_txt(contrib[k]),
                      regra=k in REGRA) for k in chaves]
        soma = sum(contrib[k] for k in chaves)
        grupos.append(dict(id=gid, nome=T("g." + gid), cp=round(soma), lado=_lado_txt(soma), itens=itens))
    residuo = None if engine_cp is None else round(engine_cp - cp)
    return dict(cp=round(cp), idx=win_pct(cp), material_cp=round(mat), material_idx=win_pct(mat),
                estrutura_cp=round(cp - mat), estrutura_idx=win_pct(cp - mat),
                grupos=grupos, residuo=residuo, engine_cp=engine_cp)


def desc_material(mat):
    """Vantagem material por extenso ("uma peça a mais")."""
    n = round(abs(mat) / 100)
    k = {1: "m.peao", 2: "m.dois", 3: "m.peca", 4: "m.peca_peao", 5: "m.torre", 9: "m.dama"}.get(n)
    return T(k) if k else T("m.mais", n=max(n, 1))


def indice_posicao(b: chess.Board):
    """Índice de Posição 0-100 (50 = equilibrado; >50 favorece as brancas), texto curto e contribuições."""
    cp, contrib = avalia(b)
    idx = win_pct(cp)
    maiores = sorted(((k, v) for k, v in contrib.items() if k != "material"), key=lambda kv: -abs(kv[1]))[:3]
    partes = [T("p.item", nome=nome_item(k).lower(), l=T("w.brancas") if v > 0 else T("w.pretas"), v=num(abs(v) / 100, 2))
              for k, v in maiores if abs(v) >= 8]
    mat = contrib["material"]
    pre = T("p.mat", l=T("w.brancas") if mat > 0 else T("w.pretas"), d=desc_material(mat)) if abs(mat) >= 50 else ""
    if abs(cp - mat) < 15:
        txt = pre + T("p.eq")
    else:
        lado = T("w.brancas") if cp - mat > 0 else T("w.pretas")
        grau = T("g.leve") if abs(cp - mat) < 40 else (T("g.clara") if abs(cp - mat) < 100 else T("g.grande"))
        txt = pre + T("p.vant", g=grau, l=lado)
        txt += ": " + "; ".join(partes) + "." if partes else "."
    return idx, txt, contrib


def destaques(b: chess.Board, chaves):
    """O que marcar no tabuleiro para um item (ou grupo) do Índice de Posição, calculado com as mesmas regras de `_lado`.
    -> dict(casas=[[casa, lado, tipo]], setas=[[de, para, lado]]); lado 'B'/'P' (cor de quem é a característica);
    tipo 'anel' (peça ou casa em destaque) ou 'tinta' (casas de uma região)."""
    if isinstance(chaves, str): chaves = [c for c in chaves.split(",") if c]
    casas, setas = [], []
    nm = chess.square_name
    fase = _fase(b)

    def casa(sq, c, tipo="anel"):
        x = [nm(sq), "B" if c else "P", tipo]
        if x not in casas: casas.append(x)

    def seta(a, z, c):
        x = [nm(a), nm(z), "B" if c else "P"]
        if x not in setas and len(setas) < 14: setas.append(x)

    for chave in chaves:
        if chave == "material":
            for t in VAL:
                nb, np_ = len(b.pieces(t, True)), len(b.pieces(t, False))
                if nb != np_:
                    c = nb > np_
                    for sq in list(b.pieces(t, c))[: abs(nb - np_)]: casa(sq, c)
            continue
        if chave == "centro":
            for sq in CENTRO: casa(sq, True, "tinta")
        for c in (True, False):
            own, opp = b.occupied_co[c], not c
            r = lambda sq: chess.square_rank(sq) if c else 7 - chess.square_rank(sq)
            peoes, inim = b.pieces(chess.PAWN, c), b.pieces(chess.PAWN, opp)
            cols = [0] * 8
            for sq in peoes: cols[chess.square_file(sq)] += 1
            if chave == "peoes":                       # grupo Estrutura de peões: todos os peões
                for sq in peoes: casa(sq, c)
            elif chave == "peoes_dobrados":
                for sq in peoes:
                    if cols[chess.square_file(sq)] > 1: casa(sq, c)
            elif chave == "peoes_isolados":
                for sq in peoes:
                    fl = chess.square_file(sq)
                    if not (cols[max(0, fl - 1)] * (fl > 0) + cols[min(7, fl + 1)] * (fl < 7)): casa(sq, c)
            elif chave == "peoes_passados":
                for sq in peoes:
                    fl = chess.square_file(sq)
                    if not [s for s in inim if abs(chess.square_file(s) - fl) <= 1 and
                            (chess.square_rank(s) > chess.square_rank(sq) if c else chess.square_rank(s) < chess.square_rank(sq))]: casa(sq, c)
            elif chave == "mobilidade":
                for t in (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN):
                    for sq in b.pieces(t, c):
                        alvo = b.attacks_mask(sq) & ~own
                        for d in chess.SquareSet(alvo): casa(d, c, "tinta")
                        if chess.popcount(alvo) <= 2: casa(sq, c)        # peça com pouquíssimas casas
            elif chave == "desenvolvimento":
                base = 0 if c else 7
                for t in (chess.KNIGHT, chess.BISHOP):
                    for sq in b.pieces(t, c):
                        if chess.square_rank(sq) == base: casa(sq, c)
            elif chave == "torres":
                for sq in b.pieces(chess.ROOK, c):
                    fl = chess.square_file(sq)
                    if cols[fl] == 0 or r(sq) == 6:
                        casa(sq, c)
                        if cols[fl] == 0:
                            for rk in range(8): casa(chess.square(fl, rk), c, "tinta")
            elif chave == "centro":
                for sq in CENTRO:
                    for a in b.attackers(c, sq): seta(a, sq, c)
            elif chave == "espaco":
                for sq in peoes:
                    if r(sq) >= 3: casa(sq, c)
            elif chave == "par_de_bispos":
                if len(b.pieces(chess.BISHOP, c)) >= 2:
                    for sq in b.pieces(chess.BISHOP, c): casa(sq, c)
            elif chave == "seguranca_rei":
                k = b.king(c)
                if k is not None:
                    kf, kr = chess.square_file(k), r(k)
                    zona = chess.SquareSet(chess.BB_KING_ATTACKS[k]) | chess.SquareSet.from_square(k)
                    for sq in zona: casa(sq, c, "tinta")
                    for sq in peoes:
                        if abs(chess.square_file(sq) - kf) <= 1 and 0 < r(sq) - kr <= 2: casa(sq, c)
                    for sq in zona:
                        for a in b.attackers(opp, sq): seta(a, sq, opp)
            elif chave == "rei_final":
                k = b.king(c)
                if k is not None: casa(k, c)
            elif chave == "pecas_em_risco":
                for t in (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN):
                    for sq in b.pieces(t, c):
                        atq = list(b.attackers(opp, sq))
                        if not atq: continue
                        menor = min(VAL.get(b.piece_type_at(a), 10_000) for a in atq)
                        if not b.attackers(c, sq) or menor < VAL[t]:
                            casa(sq, c)
                            seta(min(atq, key=lambda a: VAL.get(b.piece_type_at(a), 10_000)), sq, opp)
            elif chave == "casas_fracas":
                for fl in range(1, 7):
                    for rr in (2, 3, 4):
                        if not any(abs(chess.square_file(p) - fl) == 1 and r(p) < rr for p in peoes):
                            casa(chess.square(fl, rr if c else 7 - rr), c, "tinta")
            elif chave == "postos_avancados":
                for t in (chess.KNIGHT, chess.BISHOP):
                    for sq in b.pieces(t, c):
                        if not 4 <= r(sq) <= 6: continue
                        if not any(b.piece_type_at(a) == chess.PAWN for a in b.attackers(c, sq)): continue
                        fl = chess.square_file(sq)
                        if any(abs(chess.square_file(s) - fl) == 1 and
                               (chess.square_rank(s) > chess.square_rank(sq) if c else chess.square_rank(s) < chess.square_rank(sq)) for s in inim): continue
                        casa(sq, c)
    return dict(casas=casas, setas=setas)
