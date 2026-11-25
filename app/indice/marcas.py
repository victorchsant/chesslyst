"""Marcações de tabuleiro ligadas a cada comentário do relatório.

Uma marca é dict(fen, casas, setas, nota):
 - casas: [casa, lado, tipo], lado "B" (brancas), "P" (pretas) ou "D" (atacada ou mal defendida); tipo "anel" ou "tinta";
 - setas: [de, para, cor] ou [de, para, cor, número] (o número mostra a ordem dos lances de uma linha);
 - fen: a posição em que a marca vale (None = a do diagrama do bloco); nota: que posição é essa.
"""
from __future__ import annotations
import re
import chess

COR = {True: "#0f9d84", False: "#7c4dff"}      # brancas / pretas
BOA, RUIM = "#1e9e5a", "#e0383e"


def marca(casas=(), setas=(), fen=None, nota=""):
    vistas, cs = set(), []
    for c in casas:
        k = (c[0], c[2])
        if k not in vistas: vistas.add(k); cs.append(list(c))
    vistas, ss = set(), []
    for s in setas:
        k = (s[0], s[1])
        if k not in vistas: vistas.add(k); ss.append(list(s))
    return dict(fen=fen, casas=cs[:16], setas=ss[:9], nota=nota)


def vazia(m):
    return not m or not (m["casas"] or m["setas"] or m["fen"])


def citadas(html):
    """Peças e casas citadas no texto (o que não é lance), prontas para marcar."""
    out = []
    for atrib in re.findall(r"<b\b([^>]*)>", html or ""):
        if "data-s=" in atrib: continue
        c = re.search(r'data-c="([^"]+)"', atrib)
        if not c: continue
        lado = re.search(r'data-l="([^"]+)"', atrib)
        tipo = "tinta" if 'data-t="tinta"' in atrib else "anel"
        casas = c.group(1).split(",")
        if tipo == "anel" and atrib.count("data-i="): continue
        out += [[sq, lado.group(1) if lado else "B", tipo] for sq in (casas[:1] if tipo == "anel" else casas)]
    return out


def lances_citados(html):
    return re.findall(r'data-s="([a-h][1-8][a-h][1-8])"', html or "")


def do_texto(html, fen):
    """Marca automática de um comentário: as casas citadas e os lances citados que valem na posição do diagrama."""
    b = chess.Board(fen)
    setas = [[u[:2], u[2:4], COR[b.turn]] for u in lances_citados(html) if any(m.uci()[:4] == u for m in b.legal_moves)]
    return marca(citadas(html), setas if len(setas) <= 3 else [])


def do_lance(fen, uci, cor=BOA, casas=(), nota="", alvos=()):
    """Um lance: a seta dele e, para cada alvo que a peça passa a atacar, uma seta vermelha a partir da casa de chegada."""
    b = chess.Board(fen)
    mv = chess.Move.from_uci(uci)
    setas = [[uci[:2], uci[2:4], cor]]
    if mv in b.legal_moves:
        b2 = b.copy(); b2.push(mv)
        ataca = b2.attacks(mv.to_square)
        for a in alvos:
            sq = chess.parse_square(a)
            if sq in ataca and b2.color_at(sq) == (not b.turn): setas.append([uci[2:4], a, RUIM])
    return marca(casas, setas, fen, nota)


def da_linha(fen, ucis, cor=BOA, n=3, nota="", casas=()):
    """Os primeiros lances de uma variante, numerados: os do lado que começa em `cor`, as respostas na cor do adversário."""
    b = chess.Board(fen); setas = []
    primeiro = b.turn
    for k, u in enumerate(list(ucis)[:n]):
        mv = chess.Move.from_uci(u)
        if mv not in b.legal_moves: break
        setas.append([u[:2], u[2:4], cor if b.turn == primeiro else COR[b.turn], str(k + 1)])
        b.push(mv)
    return marca(casas, setas, fen, nota)
