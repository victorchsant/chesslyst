"""Fases da partida e focos da análise.

O programa decide, a partir da própria partida, em que fases ela passou (nem toda partida chega ao final: muitas
acabam no meio-jogo, num golpe tático) e o que vale a pena comentar em cada trecho. Cada foco recebe uma nota de
relevância (0 a 100) calculada sobre a posição; só os mais relevantes entram no relatório.

 abertura:  desenvolvimento, controle do centro, mobilidade, peças protegidas
 meio-jogo: táticas, rei (proteção e ataque), debilidades (peças e casas fracas), peças soltas, mobilidade
 final:     atividade do rei, estrutura de peões, material, táticas
"""
from __future__ import annotations
import chess
from .core import win_pct
from .explica import _mlance, _seq, _ideias, _lista, _linha_longa, _linha_do_mate
from .posicional import (mc, CENTRO, VAL, peoes_passados, peoes_isolados, peoes_dobrados, ilhas, cavalos, cavalo_mal,
                         bispos_maus, pecas_desprotegidas, destaques, _raiox, _fuga, _PESO_ATQ, _NOME_PT, _NOME_EN)
from .i18n import T, P, lang
from .marcas import marca, do_lance, citadas, COR, BOA, RUIM

ABERTURA, MEIO, FINAL = "abertura", "meio", "final"
MENORES_EM_CASA = {True: (chess.B1, chess.G1, chess.C1, chess.F1), False: (chess.B8, chess.G8, chess.C8, chess.F8)}
MAX_PECAS_FINAL = 13          # final: cada lado com no máximo 13 pontos de peças (sem contar peões)


def _lado(c): return T("w.brancas") if c else T("w.pretas")
def _L(c): return "B" if c else "P"
def _cap(s): return s[:1].upper() + s[1:]


def _junta(itens):
    return itens[0] if len(itens) == 1 else ", ".join(itens[:-1]) + T("db.e") + itens[-1]


def _casas(quadro, c, maximo=4):
    nomes = [chess.square_name(s) for s in quadro][:maximo]
    return mc(_junta(nomes), nomes, _L(c)) if nomes else ""


def _peca(b, s):
    p = b.piece_at(s); nome = chess.square_name(s)
    n = _NOME_EN[p.piece_type] if lang() == "en" else _NOME_PT[p.piece_type][0]
    return mc(f"{n} {nome}", [nome], _L(p.color))


def _foco(chave, nota, frases, casas=(), setas=(), extra=(), fen=None, nota_pos=""):
    """`casas` = [(casa, cor da peça)] viram anéis; `extra` já vem no formato da marca; `fen` quando a marca vale em outra posição."""
    texto = " ".join(f for f in frases if f)
    if not texto: return None
    aneis = [[chess.square_name(s), _L(c), "anel"] for s, c in casas]
    return dict(id=chave, nome=T("fc." + chave), nota=min(100, round(nota)), html=texto,
                marca=marca(list(extra) + aneis, setas, fen, nota_pos))


def _seta(a, z, cor): return [chess.square_name(a), chess.square_name(z), cor]
def _tinta(s, lado): return [chess.square_name(s), lado, "tinta"]


# ---------------------------------------------------------------- fases
def _pecas_pontos(b, c):
    return sum(VAL[t] // 100 if t != chess.BISHOP else 3 for t in (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN) for _ in b.pieces(t, c))


def _em_casa(b, c):
    return [s for s in MENORES_EM_CASA[c] if b.color_at(s) == c and b.piece_type_at(s) in (chess.KNIGHT, chess.BISHOP)]


def fases(rows, fens, fim_teoria=0):
    """-> [(fase, início, fim)] em índices de meio-lance (fim exclusivo), cobrindo os lances jogados."""
    n = sum(1 for r in rows if r.get("move"))
    if not n: return []
    boards = [chess.Board(f) for f in fens[:n + 1]]
    fim_ab = n
    for i, b in enumerate(boards):
        if i >= 12 and (len(_em_casa(b, True)) + len(_em_casa(b, False)) <= 2 or b.fullmove_number >= 13):
            fim_ab = i; break
    fim_ab = min(n, max(fim_ab, min(fim_teoria, 30)))
    inicio_final = None
    for i in range(len(boards) - 1, fim_ab - 1, -1):
        if max(_pecas_pontos(boards[i], True), _pecas_pontos(boards[i], False)) <= MAX_PECAS_FINAL: inicio_final = i
        else: break
    if inicio_final is not None and n - inicio_final < 4: inicio_final = None      # só os últimos lances: não conta como fase
    out = [(ABERTURA, 0, fim_ab)]
    meio_fim = inicio_final if inicio_final is not None else n
    if meio_fim > fim_ab: out.append((MEIO, fim_ab, meio_fim))
    if inicio_final is not None: out.append((FINAL, max(inicio_final, fim_ab), n))
    return [x for x in out if x[2] > x[1]]


def fase_de(lista, i):
    for nome, a, b in lista:
        if a <= i < b: return nome
    return lista[-1][0] if lista else ABERTURA


# ---------------------------------------------------------------- medidas
def _centro(b, c):
    return sum(len(b.attackers(c, s)) for s in CENTRO) + 2 * sum(1 for s in CENTRO if b.piece_at(s) == chess.Piece(chess.PAWN, c))


def _mob(b, c):
    return sum(chess.popcount(b.attacks_mask(s) & ~b.occupied_co[c]) for t in (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN) for s in b.pieces(t, c))


def _soltas(b, c):
    """Peças (sem peões) atacadas mais vezes do que defendidas, e peças sem nenhuma defesa."""
    atacadas, soltas = [], []
    for s in pecas_desprotegidas(b, c):
        if b.piece_type_at(s) == chess.PAWN: continue
        (atacadas if len(b.attackers(not c, s)) > len(b.attackers(c, s)) else soltas).append(s)
    return atacadas, [s for s in soltas if s not in MENORES_EM_CASA[c] and b.piece_type_at(s) != chess.ROOK]


def _pressao(b, c):
    """Quanto o rei de `c` está pressionado. -> (índice, atacantes na zona, escudo, casas de fuga, raios-x, casas atacadas)"""
    k = b.king(c)
    if k is None: return 0, [], 0, 0, 0, []
    zona = chess.SquareSet(chess.BB_KING_ATTACKS[k]) | chess.SquareSet.from_square(k)
    atacantes, atacadas = set(), []
    for s in zona:
        ats = [a for a in b.attackers(not c, s) if b.piece_type_at(a) != chess.KING]
        if ats: atacadas.append(s); atacantes.update(ats)
    r = lambda s: chess.square_rank(s) if c else 7 - chess.square_rank(s)
    escudo = sum(1 for s in b.pieces(chess.PAWN, c) if abs(chess.square_file(s) - chess.square_file(k)) <= 1 and 0 < r(s) - r(k) <= 2)
    fuga, raios = len(_fuga(b, k, c)), len(_raiox(b, k, not c))
    peso = sum(_PESO_ATQ[b.piece_type_at(a)] for a in atacantes)
    indice = peso + 2 * raios + max(0, 2 - fuga) + max(0, 2 - escudo) if len(atacantes) >= 2 else len(atacantes)
    return indice, sorted(atacantes), escudo, fuga, raios, atacadas


# ---------------------------------------------------------------- focos da abertura
def _desenvolvimento(b):
    partes, falta, rocou = [], {}, {}
    for c in (True, False):
        casa = _em_casa(b, c); falta[c] = len(casa)
        k = b.king(c)
        rocou[c] = k in ((chess.G1, chess.C1, chess.B1) if c else (chess.G8, chess.C8, chess.B8))
        rei = T("fc.rocado") if rocou[c] else (T("fc.pode_rocar") if b.has_castling_rights(c) else T("fc.sem_roque"))
        pend = T("fc.falta", p=_junta([_peca(b, s) for s in casa])) if casa else T("fc.completo")
        partes.append(T("fc.dev_lado", l=_cap(_lado(c)), n=4 - len(casa), p=pend, r=rei))
    d = falta[False] - falta[True]
    if abs(d) >= 1 or rocou[True] != rocou[False]:
        frente = d > 0 if d else rocou[True]
        partes.append(T("fc.dev_frente", l=_lado(frente)))
    casas = [(sq, c) for c in (True, False) for sq in _em_casa(b, c)] + [(b.king(c), c) for c in (True, False)]
    return _foco("desenvolvimento", 70 + 10 * abs(d), partes, casas)


def _controle_centro(b):
    w, p = _centro(b, True), _centro(b, False)
    partes = []
    for c in (True, False):
        peoes = [s for s in CENTRO if b.piece_at(s) == chess.Piece(chess.PAWN, c)]
        if peoes: partes.append(T("fc.peoes_centro", l=_cap(_lado(c)), s=_casas(peoes, c)))
    partes.append(T("fc.centro_igual", a=w, b=p) if abs(w - p) <= 1 else T("fc.centro_mais", l=_lado(w > p), a=max(w, p), b=min(w, p)))
    setas = []
    for c in (True, False):            # quem aponta para as casas centrais (peões e peças menores primeiro)
        meus = []
        for alvo in CENTRO:
            meus += [(b.piece_type_at(a), a, alvo) for a in b.attackers(c, alvo) if b.piece_type_at(a) in (chess.PAWN, chess.KNIGHT, chess.BISHOP)]
        setas += [_seta(a, alvo, COR[c]) for _, a, alvo in sorted(meus)[:4]]
    return _foco("centro", 55 + 6 * abs(w - p), partes, setas=setas, extra=[_tinta(sq, "B") for sq in CENTRO])


def _mobilidade(b):
    w, p = _mob(b, True), _mob(b, False)
    partes = [T("fc.mob_igual", a=w, b=p) if abs(w - p) <= 3 else T("fc.mob_mais", l=_lado(w > p), a=max(w, p), b=min(w, p))]
    presas = []
    for c in (True, False):
        presas += [(s, c) for s, uteis in cavalos(b, c) if cavalo_mal(s, uteis)]
        presas += [(s, c) for s, _ in bispos_maus(b, c)]
    if presas: partes.append(T("fc.presas", p=_junta([_peca(b, s) for s, _ in presas[:3]])))
    casas_livres = []
    for sq, c in presas[:3]:
        uteis = b.attacks(sq) & ~b.occupied_co[c]
        casas_livres += [_tinta(x, _L(c)) for x in uteis]
    return _foco("mobilidade", 25 + 2.5 * abs(w - p) + 18 * len(presas), partes, presas, extra=casas_livres)


def _protecao(b):
    partes, casas, nota = [], [], 15
    for c in (True, False):
        atacadas, soltas = _soltas(b, c)
        if atacadas:
            partes.append(T("fc.atacadas", l=_cap(_lado(c)), p=_junta([_peca(b, s) for s in atacadas[:3]]))); nota += 30 * len(atacadas)
        if soltas:
            partes.append(T("fc.soltas", l=_cap(_lado(c)), p=_junta([_peca(b, s) for s in soltas[:3]]))); nota += 8 * len(soltas)
        casas += [(s, c) for s in atacadas + soltas]
    vermelhas, setas = [], []
    for sq, c in casas:
        vermelhas.append([chess.square_name(sq), "D", "anel"])
        ats = list(b.attackers(not c, sq))
        if ats: setas.append(_seta(min(ats, key=lambda a: VAL.get(b.piece_type_at(a), 10_000)), sq, RUIM))
    return _foco("protecao", nota, partes or [T("fc.protegidas")], setas=setas, extra=vermelhas)


# ---------------------------------------------------------------- focos do meio-jogo e do final
def taticas(rows, fens, a, b, limite=2):
    """Golpes que a engine viu no trecho: ganho de material, mate, ataque duplo ou cravada no melhor lance."""
    achados = []
    for i in range(a, min(b, len(rows))):
        r = rows[i]; linhas = r.get("linhas") or []
        if not linhas or not linhas[0].get("pv_uci"): continue
        tab = chess.Board(fens[i]); L0 = linhas[0]; mv = chess.Move.from_uci(L0["uci"])
        ant = rows[i - 1] if i else None
        if ant and ant.get("uci") and tab.is_capture(mv) and ant["uci"][2:4] == L0["uci"][2:4]: continue     # simples retomada
        mate = L0.get("mate")
        tipo = None; extra = ""
        if mate is not None and (mate > 0) == tab.turn and abs(mate) <= 6:
            tipo, extra, peso = "mate", abs(mate), 100 - abs(mate)
        else:
            seq = _seq(tab, L0["pv_uci"], 5)
            y = _ideias(tab, mv)
            if y and y[0][0] in ("garfo", "cravada"): tipo, extra, peso = y[0][0], y[0][1], 60 + 5 * max(0, seq["liquido"])
            elif seq["liquido"] >= 2 and seq["ganhou"] and len(seq["passos"]) >= 3: tipo, extra, peso = "ganho", _lista(seq["ganhou"]), 55 + 5 * seq["liquido"]
        if not tipo: continue
        jogou = r.get("uci") == L0["uci"]
        if not jogou and (r.get("jogado_perda") or 0) < 5: continue          # havia outro caminho igualmente bom
        achados.append((peso + (0 if jogou else 15), i, tipo, extra, jogou))
    out, vistos = [], set()
    for peso, i, tipo, extra, jogou in sorted(achados, key=lambda x: -x[0]):
        if any(abs(i - j) <= 2 for j in vistos): continue
        vistos.add(i); out.append((i, tipo, extra, jogou, peso))
        if len(out) == limite: break
    return sorted(out)


def _foco_taticas(rows, fens, a, b):
    L = taticas(rows, fens, a, b)
    itens = []
    for i, tipo, extra, jogou, _ in L:
        tab = chess.Board(fens[i]); r = rows[i]; L0 = r["linhas"][0]
        num = f"{tab.fullmove_number}." if tab.turn else f"{tab.fullmove_number}…"
        m = num + _mlance(tab, chess.Move.from_uci(L0["uci"]), L0["san"])
        o_que = T("fc.t_mate", n=extra) if tipo == "mate" else (T("fc.t_ganho", p=extra) if tipo == "ganho" else extra[:1].lower() + extra[1:].rstrip("."))
        frase = T("fc.t_feito" if jogou else "fc.t_perdido", m=m, l=_lado(tab.turn), o=o_que)
        alvos = [x[0] for x in citadas(frase)]
        mk = do_lance(fens[i], L0["uci"], BOA, citadas(frase), T("mk.antes", x=num + L0["san"]), alvos)
        if not jogou and r.get("uci") and r["uci"] != L0["uci"]: mk["setas"].append([r["uci"][:2], r["uci"][2:4], RUIM])
        if tipo == "mate": frase += _linha_do_mate(tab, L0.get("pv_uci"))       # depois das marcas: a linha não marca casas
        elif tipo == "ganho": frase += _linha_longa(tab, _seq(tab, L0["pv_uci"], 5))
        itens.append(dict(html=frase, marca=mk))
    if not itens: return None
    return dict(id="taticas", nome=T("fc.taticas"), nota=min(100, round(max(p for *_, p in L) + 10)), html="", itens=itens, marca=itens[0]["marca"])


def _foco_rei(rows, fens, a, b):
    melhor = None
    xeques = {True: 0, False: 0}
    for i in range(a, min(b + 1, len(fens))):
        tab = chess.Board(fens[i])
        if tab.is_check(): xeques[not tab.turn] += 1
        for c in (True, False):
            p = _pressao(tab, c)
            if melhor is None or p[0] > melhor[0][0]: melhor = (p, c, i, tab)
    if not melhor: return None
    (indice, atacantes, escudo, fuga, raios, atacadas), c, i, tab = melhor
    frases, casas, setas, zona = [], [], [], []
    if indice >= 6:
        k = tab.king(c)
        frases.append(T("fc.rei_pressao", l=_lado(c), k=mc(chess.square_name(k), [chess.square_name(x) for x in [k] + atacadas], _L(c)),
                        n=tab.fullmove_number, a=_junta([_peca(tab, s) for s in atacantes[:3]]), e=escudo, pe=P(escudo, "fc.peao"), f=fuga, fc_=P(fuga, "pos.casa")))
        if raios: frases.append(T("fc.rei_raiox"))
        casas = [(k, c)]
        zona = [_tinta(x, "D") for x in atacadas]
        for a_ in atacantes[:5]:
            alvo = [x for x in atacadas if x in tab.attacks(a_)]
            if alvo: setas.append(_seta(a_, k if k in alvo else alvo[0], RUIM))
    else:
        frases.append(T("fc.rei_seguro"))
    if sum(xeques.values()): frases.append(T("fc.xeques", a=xeques[True], b=xeques[False]))
    return _foco("rei", indice * 7 if indice >= 6 else 18 + 6 * sum(xeques.values()), frases, casas, setas, zona,
                 tab.fen() if indice >= 6 else None, T("mk.no_lance", n=tab.fullmove_number) if indice >= 6 else "")


def _foco_debilidades(b):
    frases, casas, peso, vermelhas = [], [], {}, []
    marcas = destaques(b, "casas_fracas")["casas"]
    for c in (True, False):
        fracas = [chess.parse_square(x[0]) for x in marcas if x[1] == _L(c) and x[2] == "tinta"]
        ocupadas = [s for s in fracas if (p := b.piece_at(s)) and p.color != c and p.piece_type != chess.PAWN]
        iso, dob = peoes_isolados(b, c), peoes_dobrados(b, c)
        itens = []
        if iso: itens.append(T("fc.deb_iso" if len(iso) == 1 else "fc.deb_isos", s=_casas(iso, c)))
        if dob: itens.append(T("fc.deb_dob", s=_casas(dob, c)))
        if ocupadas:
            itens.append(T("fc.deb_ocupada", p=_junta([_peca(b, s) for s in ocupadas[:2]])))
            vermelhas += [[chess.square_name(s), "D", "anel"] for s in ocupadas[:2]]
        peso[c] = len(iso) + len(dob) + 2 * len(ocupadas)
        casas += [(s, c) for s in list(iso) + [x for x in dob if x not in iso]]
        vermelhas += [_tinta(s, _L(c)) for s in fracas[:5]]
        if itens: frases.append(T("fc.deb_lado", l=_cap(_lado(c)), i=_junta(itens)))
    return _foco("debilidades", 30 + 9 * abs(peso[True] - peso[False]) + 4 * max(peso.values()), frases, casas, extra=vermelhas)


def _foco_rei_final(b):
    dist = lambda s: max(abs(chess.square_file(s) - 3.5), abs(chess.square_rank(s) - 3.5))
    frases, d = [], {}
    for c in (True, False):
        k = b.king(c); d[c] = dist(k)
        mov = len(_fuga(b, k, c))
        perto = [s for s in b.pieces(chess.PAWN, c) | b.pieces(chess.PAWN, not c) if chess.square_distance(k, s) <= 2]
        frases.append(T("fc.reif_lado", l=_cap(_lado(c)), k=mc(chess.square_name(k), [chess.square_name(k)], _L(c)), m=mov, c=P(mov, "pos.casa"), n=len(perto)))
    if abs(d[True] - d[False]) >= 1: frases.append(T("fc.reif_ativo", l=_lado(d[True] < d[False])))
    livres = [_tinta(x, _L(c)) for c in (True, False) for x in _fuga(b, b.king(c), c)]
    return _foco("rei_final", 66 + 8 * abs(d[True] - d[False]), frases, [(b.king(c), c) for c in (True, False)], extra=livres)


def _foco_peoes(b):
    frases, casas, nota = [], [], 55
    for c in (True, False):
        itens = []
        pas, iso, dob = peoes_passados(b, c), peoes_isolados(b, c), peoes_dobrados(b, c)
        if pas: itens.append(T("fc.pe_passado" if len(pas) == 1 else "fc.pe_passados", s=_casas(pas, c))); nota += 15; casas += [(s, c) for s in pas]
        if iso: itens.append(T("fc.deb_iso" if len(iso) == 1 else "fc.deb_isos", s=_casas(iso, c)))
        if dob: itens.append(T("fc.deb_dob", s=_casas(dob, c)))
        n = len(ilhas(b, c))
        itens.append(T("fc.pe_ilhas", n=n, i=P(n, "fc.ilha")))
        frases.append(T("fc.deb_lado", l=_cap(_lado(c)), i=_junta(itens)))
    for chave, colunas in (("fc.ala_dama", range(0, 4)), ("fc.ala_rei", range(4, 8))):
        w, p = (sum(1 for s in b.pieces(chess.PAWN, c) if chess.square_file(s) in colunas) for c in (True, False))
        if w != p: frases.append(T("fc.maioria", l=_lado(w > p), a=T(chave), x=max(w, p), y=min(w, p))); nota += 4
    setas = []
    for c in (True, False):             # o caminho dos peões passados até a promoção
        for sq in peoes_passados(b, c):
            setas.append(_seta(sq, chess.square(chess.square_file(sq), 7 if c else 0), COR[c]))
        casas += [(s, c) for s in peoes_isolados(b, c)]
    return _foco("peoes", nota, frases, casas, setas)


def _material_lado(b, c):
    out = []
    for t, chave in ((chess.QUEEN, "dama"), (chess.ROOK, "torre"), (chess.BISHOP, "bispo"), (chess.KNIGHT, "cavalo"), (chess.PAWN, "peao")):
        n = len(b.pieces(t, c))
        if n: out.append(f"{n} {P(n, 'fc.m_' + chave)}")
    return _junta(out) if out else T("fc.so_rei")


def _foco_material(b):
    frases = [T("fc.mat_lado", l=_cap(_lado(c)), m=_material_lado(b, c)) for c in (True, False)]
    pontos = {c: _pecas_pontos(b, c) + len(b.pieces(chess.PAWN, c)) for c in (True, False)}
    dif = pontos[True] - pontos[False]
    nota = 48
    if dif: frases.append(T("fc.mat_dif", l=_lado(dif > 0), n=abs(dif), p=P(abs(dif), "fc.ponto"))); nota += 22
    bw, bp = b.pieces(chess.BISHOP, True), b.pieces(chess.BISHOP, False)
    if len(bw) == 1 and len(bp) == 1 and sum(divmod(list(bw)[0], 8)) % 2 != sum(divmod(list(bp)[0], 8)) % 2:
        frases.append(T("fc.bispos_opostos")); nota += 22
    casas = [(s, c) for c in (True, False) for t in (chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT) for s in b.pieces(t, c)]
    return _foco("material", nota, frases, casas)


def focos(rows, fens, fase, a, b, maximo=3):
    """Os focos mais relevantes do trecho [a, b) na sua fase. A posição medida é a do fim do trecho."""
    if b < len(fens): tab = chess.Board(fens[b])
    else:
        tab = chess.Board(fens[b - 1]); tab.push(chess.Move.from_uci(rows[b - 1]["uci"]))
    if fase == ABERTURA:      # na abertura os quatro focos sempre entram: são o que define se ela correu bem
        return [f for f in (_desenvolvimento(tab), _controle_centro(tab), _mobilidade(tab), _protecao(tab)) if f]
    if fase == MEIO:
        L = [_foco_taticas(rows, fens, a, b), _foco_rei(rows, fens, a, b), _foco_debilidades(tab), _protecao(tab), _mobilidade(tab)]
    else:
        L = [_foco_taticas(rows, fens, a, b), _foco_rei_final(tab), _foco_peoes(tab), _foco_material(tab)]
    L = sorted((f for f in L if f and f["nota"] >= 35), key=lambda f: -f["nota"])
    return L[:maximo]


# ---------------------------------------------------------------- o perfil da partida
def perfil(rows, fens, lista, resultado):
    """Como a partida se decidiu, em uma ou duas frases. -> (frase das fases, frase do desfecho)"""
    if not lista: return "", ""
    nomes = []
    for fase, a, b in lista:
        n1, n2 = chess.Board(fens[a]).fullmove_number, chess.Board(fens[b - 1]).fullmove_number
        nomes.append(T("fc.fase_faixa", f=T("fc.f_" + fase), a=n1, b=n2))
    fases_txt = _junta(nomes) + "."
    ultima = lista[-1][0]
    if ultima != FINAL: fases_txt += " " + T("fc.sem_final", f=T("fc.f_" + ultima).lower())
    viradas = [i for i, r in enumerate(rows) if r.get("critico") and r["critico"]["tipo"] == "virada"]
    ult = rows[-1]
    mate = chess.Board(ult["fen"]).is_checkmate() or (ult.get("fen_depois") and chess.Board(ult["fen_depois"]).is_checkmate())
    if resultado == "1/2-1/2":
        des = T("fc.d_empate_limpo") if not viradas else T("fc.d_empate", n=len(viradas), v=P(len(viradas), "rel.virada"))
    elif resultado in ("1-0", "0-1"):
        venc = resultado == "1-0"
        if viradas:
            i = viradas[-1]; fase = fase_de(lista, i)
            golpe = taticas(rows, fens, max(0, i - 1), i + 3, 1)
            chave = "fc.d_golpe" if golpe or mate else "fc.d_virada"
            tab = chess.Board(fens[i])
            des = T(chave, l=_lado(venc), f=T("fc.f_" + fase).lower(), n=tab.fullmove_number)
        else:
            des = T("fc.d_gradual", l=_lado(venc))
        if mate: des += " " + T("fc.d_mate")
    else:
        des = ""
    return fases_txt, des
