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
from .i18n import T, num, P, lang

VAL = {chess.PAWN: 100, chess.KNIGHT: 320, chess.BISHOP: 330, chess.ROOK: 500, chess.QUEEN: 900}

ITENS = ["material", "peoes_dobrados", "peoes_isolados", "peoes_passados", "ilhas_peoes", "mobilidade", "mobilidade_cavalos", "bispos_maus", "desenvolvimento", "torres", "centro",
         "espaco", "par_de_bispos", "seguranca_rei", "rei_zona", "rei_raiox", "rei_fuga", "rei_final", "pecas_em_risco", "casas_fracas", "postos_avancados"]
GRUPOS = [   # (id, componentes)
    ("material", ["material"]),
    ("estrutura", ["peoes_isolados", "peoes_passados", "peoes_dobrados", "ilhas_peoes"]),
    ("atividade", ["mobilidade", "mobilidade_cavalos", "bispos_maus", "desenvolvimento", "torres", "centro", "espaco", "par_de_bispos"]),
    ("rei", ["seguranca_rei", "rei_zona", "rei_raiox", "rei_fuga", "rei_final"]),
    ("debilidades", ["pecas_em_risco", "casas_fracas"]),
    ("postos", ["postos_avancados"]),
]


def nome_item(k): return T(f"it.{k}.n")
def desc_item(k): return T(f"it.{k}.d")


PESOS0 = {"material": 1.0, "mobilidade": 4.0, "par_de_bispos": 30.0, "peoes_dobrados": -15.0, "peoes_isolados": -12.0,
          "peoes_passados": 12.0, "seguranca_rei": 10.0, "rei_zona": -6.0, "rei_raiox": -15.0, "rei_fuga": 8.0, "rei_final": 8.0, "centro": 8.0, "torres": 15.0,
          "desenvolvimento": -12.0, "espaco": 3.0, "pecas_em_risco": -40.0, "casas_fracas": -6.0, "postos_avancados": 25.0,
          "ilhas_peoes": -8.0, "mobilidade_cavalos": 10.0, "bispos_maus": -25.0}
_f = Path(__file__).resolve().parent.parent / "calibracao" / "posicional.json"
_dados = json.loads(_f.read_text(encoding="utf-8")) if _f.exists() else {}
PESOS = {**PESOS0, **_dados.get("pesos", {})}
REGRA = set(_dados.get("regra", []))   # pesos definidos por regra (não validados pelos dados)
CENTRO = [chess.D4, chess.E4, chess.D5, chess.E5]

_NOME_PT = {chess.PAWN: ("peão", "m"), chess.KNIGHT: ("cavalo", "m"), chess.BISHOP: ("bispo", "m"), chess.ROOK: ("torre", "f"),
            chess.QUEEN: ("dama", "f"), chess.KING: ("rei", "m")}
_NOME_EN = {chess.PAWN: "pawn", chess.KNIGHT: "knight", chess.BISHOP: "bishop", chess.ROOK: "rook", chess.QUEEN: "queen", chess.KING: "king"}


def mc(txt, casas=None, lado=None, item=None, seta=None, tipo=None, pos=None):
    """Trecho em negrito da interpretação. Ao passar o mouse, a tela marca no tabuleiro as `casas` (ou o item de posição `item`)."""
    at = ' class="mc"'
    if casas: at += ' data-c="' + ",".join(casas) + '"'
    if lado: at += f' data-l="{lado}"'
    if item: at += f' data-i="{item}"'
    if seta: at += f' data-s="{seta}"'          # lance: a tela desenha a seta
    if pos: at += f' data-f="{pos}"'            # posição depois do lance: a tela a mostra numa janela pequena
    if tipo: at += f' data-t="{tipo}"'
    return f"<b{at}>{txt}</b>"


def pc(b, sq, extra=None, cap=False):
    """'o bispo preto em b4' em negrito, ligado à casa (e a casas extras) no tabuleiro."""
    p = b.piece_at(sq)
    nome = chess.square_name(sq)
    if p is None: return mc(nome, [nome])
    if lang() == "en":
        txt = f"the {'white' if p.color else 'black'} {_NOME_EN[p.piece_type]} on {nome}"
    else:
        n, g = _NOME_PT[p.piece_type]
        cor = ("branca" if g == "f" else "branco") if p.color else ("preta" if g == "f" else "preto")
        txt = f"{'a' if g == 'f' else 'o'} {n} {cor} em {nome}"
    if cap: txt = txt[:1].upper() + txt[1:]
    return mc(txt, [nome] + [chess.square_name(x) for x in (extra or [])], "B" if p.color else "P")


def _lista_casas(nomes):
    nomes = list(nomes)
    return nomes[0] if len(nomes) == 1 else ", ".join(nomes[:-1]) + T("db.e") + nomes[-1]


def material(b):
    return sum(v * (len(b.pieces(t, True)) - len(b.pieces(t, False))) for t, v in VAL.items())


def _fase(b):
    """1 = abertura/meio-jogo cheio, 0 = final sem peças."""
    n = sum({1: 0, 2: 1, 3: 1, 4: 2, 5: 4}[t] * (len(b.pieces(t, True)) + len(b.pieces(t, False))) for t in range(1, 6))
    return min(1.0, n / 24)


def _a_frente(a, sq, c):
    """A casa `a` está em fileira à frente de `sq`, do ponto de vista de `c`."""
    return chess.square_rank(a) > chess.square_rank(sq) if c else chess.square_rank(a) < chess.square_rank(sq)


def peoes_isolados(b, c):
    colunas = {chess.square_file(s) for s in b.pieces(chess.PAWN, c)}
    return [s for s in b.pieces(chess.PAWN, c) if not {chess.square_file(s) - 1, chess.square_file(s) + 1} & colunas]


def peoes_passados(b, c):
    inim = b.pieces(chess.PAWN, not c)
    return [s for s in b.pieces(chess.PAWN, c)
            if not any(abs(chess.square_file(a) - chess.square_file(s)) <= 1 and _a_frente(a, s, c) for a in inim)]


def peoes_dobrados(b, c):
    colunas = [chess.square_file(s) for s in b.pieces(chess.PAWN, c)]
    return [s for s in b.pieces(chess.PAWN, c) if colunas.count(chess.square_file(s)) > 1]


def ilhas(b, c):
    """Grupos de peões em colunas vizinhas, da coluna a para a h. -> [[casas de cada ilha]]"""
    out, ant = [], None
    for s in sorted(b.pieces(chess.PAWN, c), key=lambda s: (chess.square_file(s), chess.square_rank(s))):
        if ant is None or chess.square_file(s) - ant > 1: out.append([])
        out[-1].append(s); ant = chess.square_file(s)
    return out


def casas_do_cavalo(b, sq, c):
    """Casas úteis do cavalo em `sq`: sem peça própria e sem ataque de peão adversário."""
    return [a for a in b.attacks(sq) if b.color_at(a) != c
            and not any(b.piece_type_at(x) == chess.PAWN for x in b.attackers(not c, a))]


def cavalos(b, c):
    """-> [(casa, casas úteis)] dos cavalos fora da casa de origem (quem não saiu já conta em Desenvolvimento)."""
    origem = (chess.B1, chess.G1) if c else (chess.B8, chess.G8)
    return [(s, casas_do_cavalo(b, s, c)) for s in b.pieces(chess.KNIGHT, c) if s not in origem]


def cavalo_mal(sq, casas):
    """Cavalo na borda (colunas a/h ou fileiras 1/8) com até 2 casas úteis, ou em qualquer lugar com no máximo 1."""
    borda = chess.square_file(sq) in (0, 7) or chess.square_rank(sq) in (0, 7)
    return len(casas) <= (2 if borda else 1)


def bispos_maus(b, c):
    """Bispo preso pelos próprios peões: dois ou mais peões centrais (colunas c-f) na cor das suas casas, ao menos um travado
    por um peão à frente, o bispo atrás dessa cadeia e com no máximo 3 casas. -> [(casa do bispo, [peões que o atrapalham])]"""
    cor_casa = lambda s: (chess.square_file(s) + chess.square_rank(s)) % 2
    rel = lambda s: chess.square_rank(s) if c else 7 - chess.square_rank(s)
    out = []
    for sq in b.pieces(chess.BISHOP, c):
        meus = [p for p in b.pieces(chess.PAWN, c) if 2 <= chess.square_file(p) <= 5 and cor_casa(p) == cor_casa(sq)]
        travados = [p for p in meus if 0 <= p + (8 if c else -8) < 64 and b.piece_type_at(p + (8 if c else -8)) == chess.PAWN]
        # o bispo tem de estar ATRÁS de um peão travado: o bispo que já saiu da cadeia (como o de f4 no Sistema Londres) não conta
        if len(meus) >= 2 and travados and rel(sq) < max(map(rel, travados)) and chess.popcount(b.attacks_mask(sq) & ~b.occupied_co[c]) <= 3:
            out.append((sq, meus))
    return out


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
    f["peoes_isolados"] = float(len(peoes_isolados(b, c)))
    for sq in peoes_passados(b, c): f["peoes_passados"] += (r(sq) / 6) ** 2 * (1 + (1 - fase))
    for sq in peoes:
        if r(sq) >= 3: f["espaco"] += r(sq) - 2
    f["peoes_dobrados"] = float(sum(max(0, n - 1) for n in cols))
    f["ilhas_peoes"] = float(len(ilhas(b, c)))
    f["mobilidade_cavalos"] = sum(len(casas) - 4 for _, casas in cavalos(b, c)) / 4   # 4 casas = neutro; na borda e no canto fica negativo
    f["bispos_maus"] = float(len(bispos_maus(b, c)))
    k = b.king(c)
    if k is not None:
        kf, kr = chess.square_file(k), r(k)
        escudo = sum(1 for sq in peoes if abs(chess.square_file(sq) - kf) <= 1 and 0 < r(sq) - kr <= 2)
        zona = chess.SquareSet(chess.BB_KING_ATTACKS[k]) | chess.SquareSet.from_square(k)
        f["seguranca_rei"] = fase * escudo                                   # escudo de peões
        f["rei_zona"] = fase * sum(_PESO_ATQ[b.piece_type_at(a)] for s in zona for a in b.attackers(opp, s)) / 4   # casas da zona sob ataque
        f["rei_raiox"] = (0.5 + 0.5 * fase) * len(_raiox(b, k, opp))         # peças de longo alcance apontadas ao rei com uma peça no meio
        f["rei_fuga"] = fase * min(4, len(_fuga(b, k, c)))                   # casas de fuga livres e não atacadas
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
            if not tem_defesa(b, sq, c): risco = v / 100
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


_PESO_ATQ = {chess.PAWN: 1, chess.KNIGHT: 2, chess.BISHOP: 2, chess.ROOK: 3, chess.QUEEN: 5, chess.KING: 0}


def _raiox(b, k, opp):
    """Peças de longo alcance de `opp` alinhadas com o rei em `k` (na linha certa para o seu movimento) com exatamente uma peça no meio."""
    out = []
    for sq in b.pieces(chess.BISHOP, opp) | b.pieces(chess.ROOK, opp) | b.pieces(chess.QUEEN, opp):
        pt = b.piece_type_at(sq)
        df, dr = abs(chess.square_file(sq) - chess.square_file(k)), abs(chess.square_rank(sq) - chess.square_rank(k))
        diag, reta = df == dr, df == 0 or dr == 0
        if not ((pt == chess.BISHOP and diag) or (pt == chess.ROOK and reta) or (pt == chess.QUEEN and (diag or reta))): continue
        meio = chess.between(sq, k) & b.occupied
        if chess.popcount(meio) == 1: out.append((sq, chess.msb(meio)))
    return out


def _fuga(b, k, c):
    """Casas vizinhas ao rei livres (sem peça própria) e não atacadas pelo adversário."""
    return [s for s in chess.SquareSet(chess.BB_KING_ATTACKS[k]) if not (b.occupied_co[c] >> s) & 1 and not b.is_attacked_by(not c, s)]


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


# itens informativos (contagem e casas): aparecem na tabela e no tabuleiro, mas NÃO entram no valor do índice
ITENS_INFO = {"debilidades": ["pecas_desprotegidas", "casas_desprotegidas"]}


_VALOR_TROCA = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 100}


def _troca_em(b, casa):
    """A troca em `casa` para quem tem a vez, simulada lance a lance (a peça de menor valor primeiro; cada um para quando
    continuar não compensa; quem estava atrás numa linha entra quando ela se abre). -> material que se ganha capturando."""
    opcoes = [m for m in b.legal_moves if m.to_square == casa and b.is_capture(m) and m.promotion in (None, chess.QUEEN)]
    if not opcoes: return 0
    m = min(opcoes, key=lambda m: _VALOR_TROCA[b.piece_type_at(m.from_square)])
    vitima = _VALOR_TROCA.get(b.piece_type_at(casa), 0)
    depois = b.copy(stack=False); depois.push(m)
    return max(0, vitima - _troca_em(depois, casa))


def ganho_ao_capturar(b, sq, por):
    """Quanto o lado `por` ganha de material se começar a troca na casa `sq` (0 se não compensa)."""
    t = b.copy(stack=False); t.turn = por; t.ep_square = None
    return _troca_em(t, sq)


def tem_defesa(b, sq, c):
    """A peça de `c` em `sq` tem quem a retome? Contra cada atacante é preciso haver uma retomada, inclusive através dele:
    uma dama atrás da dama adversária protege, porque a linha se abre quando esta captura."""
    atacantes = b.attackers(not c, sq)
    if not atacantes: return bool(b.attackers(c, sq))
    for a in atacantes:
        sem_ele = b.occupied & ~chess.BB_SQUARES[a]      # o atacante saiu da casa de origem e está em `sq`
        if not b.attackers_mask(c, sq, sem_ele) & sem_ele & ~chess.BB_SQUARES[sq]: return False
    return True


def desprotegida(b, sq, c):
    """Sem quem a retome, ou o adversário ganha material ao capturá-la."""
    if not tem_defesa(b, sq, c): return True
    return bool(b.attackers(not c, sq)) and ganho_ao_capturar(b, sq, not c) > 0


def pecas_desprotegidas(b, c):
    """Peças e peões de `c` sem nenhuma proteção, ou que o adversário ganha material ao capturar. O rei não entra."""
    out = []
    for sq, p in sorted(b.piece_map().items()):
        if p.color != c or p.piece_type == chess.KING: continue
        if desprotegida(b, sq, c): out.append(sq)
    return out


def casas_desprotegidas(b, c):
    """Casas do campo de `c` (suas três primeiras fileiras), sem peça sua, que nenhuma peça ou peão seu defende."""
    fileiras = (0, 1, 2) if c == chess.WHITE else (7, 6, 5)
    out = []
    for fileira in fileiras:
        for coluna in range(8):
            sq = chess.square(coluna, fileira)
            if b.color_at(sq) != c and not b.is_attacked_by(c, sq): out.append(sq)
    return sorted(out)


def _item_info(b, chave):
    d = dict(chave=chave, nome=nome_item(chave), desc=desc_item(chave), cp=0, lado="", regra=False, info=True)
    d.update(_listas(b, chave))
    return d


COM_LISTA = ("peoes_isolados", "peoes_passados", "peoes_dobrados", "ilhas_peoes", "mobilidade_cavalos", "bispos_maus",
             "pecas_desprotegidas", "casas_desprotegidas")


def _listas(b, chave):
    """O que o item encontrou de cada lado: {"B": [[casas "a1,b2", rótulo], ...], "P": [...], "mostra": vale exibir mesmo empatado}."""
    nm = chess.square_name
    peca = lambda sq: f"{_NOME_EN[b.piece_type_at(sq)] if lang() == 'en' else _NOME_PT[b.piece_type_at(sq)][0]} {nm(sq)}"
    d, mostra = {}, False
    for c, lado in ((chess.WHITE, "B"), (chess.BLACK, "P")):
        if chave == "pecas_desprotegidas": l = [[nm(s), peca(s)] for s in pecas_desprotegidas(b, c)]
        elif chave == "casas_desprotegidas": l = [[nm(s), nm(s)] for s in casas_desprotegidas(b, c)]
        elif chave in ("peoes_isolados", "peoes_passados", "peoes_dobrados"):
            funcao = {"peoes_isolados": peoes_isolados, "peoes_passados": peoes_passados, "peoes_dobrados": peoes_dobrados}[chave]
            l = [[nm(s), nm(s)] for s in funcao(b, c)]; mostra = mostra or bool(l)
        elif chave == "ilhas_peoes":
            grupos = ilhas(b, c)
            l = [[",".join(map(nm, g)), " ".join(map(nm, g))] for g in grupos]; mostra = mostra or len(grupos) >= 3
        elif chave == "mobilidade_cavalos":
            l = []
            for s, uteis in cavalos(b, c):
                mal = cavalo_mal(s, uteis); mostra = mostra or mal
                l.append([nm(s), f"{peca(s)}: {len(uteis)} {P(len(uteis), 'pos.casa')}" + (T("pos.mal") if mal else "")])
        elif chave == "bispos_maus":
            l = [[",".join([nm(s)] + [nm(a) for a in meus]), peca(s)] for s, meus in bispos_maus(b, c)]; mostra = mostra or bool(l)
        else:
            return {}
        d[lado] = l
    d["mostra"] = mostra
    return d


def analise(b: chess.Board, engine_cp=None):
    """Interpretação geral item a item. engine_cp = avaliação da engine (brancas), só para mostrar o resíduo."""
    cp, contrib = avalia(b)
    mat = contrib["material"]
    grupos = []
    for gid, chaves in GRUPOS:
        itens = [dict(chave=k, nome=nome_item(k), desc=desc_item(k), cp=round(contrib[k]), lado=_lado_txt(contrib[k]),
                      regra=k in REGRA, **(_listas(b, k) if k in COM_LISTA else {})) for k in chaves]
        soma = sum(contrib[k] for k in chaves)
        itens += [_item_info(b, k) for k in ITENS_INFO.get(gid, [])]
        grupos.append(dict(id=gid, nome=T("g." + gid), cp=round(soma), lado=_lado_txt(soma), itens=itens))
    residuo = None if engine_cp is None else round(engine_cp - cp)
    return dict(cp=round(cp), idx=win_pct(cp), material_cp=round(mat), material_idx=win_pct(mat),
                estrutura_cp=round(cp - mat), estrutura_idx=win_pct(cp - mat),
                grupos=grupos, residuo=residuo, engine_cp=engine_cp)


_MAT_PT = {chess.PAWN: ("um peão", "peões", False), chess.KNIGHT: ("um cavalo", "cavalos", False), chess.BISHOP: ("um bispo", "bispos", False),
           chess.ROOK: ("uma torre", "torres", True), chess.QUEEN: ("uma dama", "damas", True)}
_VALOR_PECA = {chess.QUEEN: 9, chess.ROOK: 5, chess.BISHOP: 3, chess.KNIGHT: 3, chess.PAWN: 1}


def _pecas_por_extenso(contagem):
    out = []
    for t in _VALOR_PECA:
        n = contagem.get(t, 0)
        if not n: continue
        if lang() == "en":
            nome = _NOME_EN[t]
            out.append(f"a {nome}" if n == 1 else ({2: "two", 3: "three"}.get(n, str(n)) + f" {nome}s"))
        else:
            um, plural, fem = _MAT_PT[t]
            out.append(um if n == 1 else ({2: "duas" if fem else "dois", 3: "três"}.get(n, str(n)) + f" {plural}"))
    e = " and " if lang() == "en" else " e "
    return out[0] if len(out) == 1 else ", ".join(out[:-1]) + e + out[-1]


def desc_material(b):
    """A diferença de material pelas PEÇAS do tabuleiro (sem os pesos do índice posicional).
    -> (quem está na frente: True = brancas, "um cavalo a mais" | "uma torre contra um bispo e um peão") ou None se empata."""
    dif = {t: len(b.pieces(t, True)) - len(b.pieces(t, False)) for t in _VALOR_PECA}
    # um cavalo de um lado contra um bispo do outro não é material a mais para ninguém: os dois saem da conta
    if dif[chess.KNIGHT] * dif[chess.BISHOP] < 0:
        pares = min(abs(dif[chess.KNIGHT]), abs(dif[chess.BISHOP]))
        for t in (chess.KNIGHT, chess.BISHOP): dif[t] -= pares if dif[t] > 0 else -pares
    saldo = sum(_VALOR_PECA[t] * n for t, n in dif.items())
    if not saldo: return None
    lider = saldo > 0
    sinal = 1 if lider else -1
    meus = {t: sinal * n for t, n in dif.items() if sinal * n > 0}
    outros = {t: -sinal * n for t, n in dif.items() if sinal * n < 0}
    if not meus: return None
    return lider, (T("m.contra", a=_pecas_por_extenso(meus), b=_pecas_por_extenso(outros)) if outros else T("m.a_mais", a=_pecas_por_extenso(meus)))


def indice_posicao(b: chess.Board, engine_cp=None):
    """Índice de Posição 0-100 (50 = equilibrado; >50 favorece as brancas), texto curto e contribuições.
    A estimativa estática tem erro típico de ~1,7 peão contra o Stockfish, então 'clara' só vale para valores realmente altos."""
    cp, contrib = avalia(b)
    idx = win_pct(cp)
    maiores = sorted(((k, v) for k, v in contrib.items() if k != "material"), key=lambda kv: -abs(kv[1]))[:3]
    mat = contrib["material"]
    real = desc_material(b)
    pre = T("p.mat", l=T("w.brancas") if real[0] else T("w.pretas"), d=real[1]) if real else ""
    din = abs(cp - mat)
    if din < 40:
        txt = pre + T("p.eq")
    else:
        lado_b = cp - mat > 0
        grau = T("g.leve") if din < 100 else (T("g.moderada") if din < 200 else (T("g.clara") if din < 350 else T("g.grande")))
        engine_eq = engine_cp is not None and abs(engine_cp) < 40 and din >= 100
        lado = T("w.brancas") if lado_b else T("w.pretas")
        txt = pre + (T("p.trunfos", l=lado) if engine_eq else T("p.vant", g=grau, l=lado) + ".")
        fav = {True: [], False: []}
        for k, v in maiores:
            if abs(v) >= 8: fav[v > 0].append(mc(T("pf." + k), None, None, item=k))
        for lado, itens in ((lado_b, fav[lado_b]), (not lado_b, fav[not lado_b])):
            if itens: txt += " " + T("p.favor", l=T("w.brancas") if lado else T("w.pretas"), i=itens[0] if len(itens) == 1 else ", ".join(itens[:-1]) + T("db.e") + itens[-1])
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
            if chave == "pecas_desprotegidas":
                for sq in pecas_desprotegidas(b, c):
                    casas.append([nm(sq), "D", "anel"])           # "D" = vermelho (desprotegido)
                    ats = list(b.attackers(opp, sq))
                    if ats and desprotegida(b, sq, c):           # atacada e mal defendida: mostra um atacante
                        a = min(ats, key=lambda a: VAL.get(b.piece_type_at(a), 10_000))
                        if len(setas) < 14: setas.append([nm(a), nm(sq), "D"])
            elif chave == "casas_desprotegidas":
                for sq in casas_desprotegidas(b, c): casas.append([nm(sq), "D", "tinta"])   # só a casa pintada, sem borda
            elif chave == "peoes":                       # grupo Estrutura de peões: todos os peões
                for sq in peoes: casa(sq, c)
            elif chave == "peoes_dobrados":
                for sq in peoes:
                    if cols[chess.square_file(sq)] > 1: casa(sq, c)
            elif chave == "peoes_isolados":
                for sq in peoes_isolados(b, c): casa(sq, c)
            elif chave == "peoes_passados":
                for sq in peoes_passados(b, c): casa(sq, c)
            elif chave == "ilhas_peoes":
                for sq in peoes: casa(sq, c)
            elif chave == "mobilidade_cavalos":     # os cavalos e as casas úteis de cada um
                for sq, uteis in cavalos(b, c):
                    casa(sq, c)
                    for a in uteis: casa(a, c, "tinta")
            elif chave == "bispos_maus":            # o bispo e os peões que o atrapalham
                for sq, meus in bispos_maus(b, c):
                    casa(sq, c)
                    for a in meus: casa(a, c, "tinta")
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
            elif chave == "seguranca_rei":      # escudo de peões
                k = b.king(c)
                if k is not None:
                    kf, kr = chess.square_file(k), r(k)
                    casa(k, c)
                    for sq in peoes:
                        if abs(chess.square_file(sq) - kf) <= 1 and 0 < r(sq) - kr <= 2: casa(sq, c)
            elif chave == "rei_zona":           # casas ao redor do rei sob ataque, com as setas dos atacantes
                k = b.king(c)
                if k is not None:
                    zona = chess.SquareSet(chess.BB_KING_ATTACKS[k]) | chess.SquareSet.from_square(k)
                    for sq in zona:
                        ats = list(b.attackers(opp, sq))
                        if ats:
                            casa(sq, c, "tinta")
                            seta(max(ats, key=lambda a: _PESO_ATQ[b.piece_type_at(a)]), sq, opp)
            elif chave == "rei_raiox":          # linha do raio-x até o rei e a peça que está no meio
                k = b.king(c)
                if k is not None:
                    for sq, meio in _raiox(b, k, opp):
                        seta(sq, k, opp); casa(meio, c)
            elif chave == "rei_fuga":           # casas de fuga do rei
                k = b.king(c)
                if k is not None:
                    casa(k, c)
                    for sq in _fuga(b, k, c): casa(sq, c, "tinta")
            elif chave == "rei_final":
                k = b.king(c)
                if k is not None: casa(k, c)
            elif chave == "pecas_em_risco":
                for t in (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN):
                    for sq in b.pieces(t, c):
                        atq = list(b.attackers(opp, sq))
                        if not atq: continue
                        menor = min(VAL.get(b.piece_type_at(a), 10_000) for a in atq)
                        if not tem_defesa(b, sq, c) or menor < VAL[t]:
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


def texto_debilidades(b: chess.Board) -> str:
    """Quem tem mais debilidades (casas fracas e peças expostas) e se o adversário já as aproveita. Vazio quando não há diferença clara.
    Casas e peças saem em negrito e são marcadas no tabuleiro ao passar o mouse."""
    casas = destaques(b, "casas_fracas")["casas"]
    risco = destaques(b, "pecas_em_risco")["casas"]
    info = {}
    for c in (chess.WHITE, chess.BLACK):
        lado = "B" if c else "P"
        fracas = [chess.parse_square(x[0]) for x in casas if x[1] == lado and x[2] == "tinta"]
        expostas = [chess.parse_square(x[0]) for x in risco if x[1] == lado and c != b.turn]   # quem joga agora pode salvar a peça: não conta
        ocupa = [sq for sq in fracas if (p := b.piece_at(sq)) and p.color != c and p.piece_type in (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN)]
        controla = []
        for sq in fracas:
            ats = [a for a in b.attackers(not c, sq) if b.piece_type_at(a) in (chess.KNIGHT, chess.BISHOP)]
            if ats: controla.append((sq, ats[0]))
        info[c] = dict(fracas=fracas, expostas=expostas, ocupa=ocupa, controla=controla, nota=len(fracas) + 3 * len(expostas))
    fraco = chess.WHITE if info[chess.WHITE]["nota"] >= info[chess.BLACK]["nota"] else chess.BLACK
    d, o = info[fraco], info[not fraco]
    explorada = bool(d["ocupa"] or d["controla"] or d["expostas"])
    if d["nota"] - o["nota"] < (3 if explorada else 5): return ""
    lado = "B" if fraco == chess.WHITE else "P"
    partes = []
    if len(d["fracas"]) - len(o["fracas"]) >= 3:
        prio = [x for x in d["ocupa"]] + [x[0] for x in d["controla"]]
        ordem = list(dict.fromkeys(prio + d["fracas"]))   # sem repetir casas
        nomes = [chess.square_name(x) for x in ordem[:4]]
        partes.append(T("db.casas_em", s=mc(_lista_casas(nomes), nomes, lado)))
    if d["expostas"]:
        partes.append(T("db.pecas_em", p=T("db.e").join(pc(b, x) for x in d["expostas"][:2])))
    if not partes: return ""
    quem = T("w.brancas") if fraco == chess.WHITE else T("w.pretas")
    base = T("db.mais", l=quem, o=T("db.e").join(partes))
    como = []
    if d["expostas"]: como.append(T("db.ja_atacadas"))
    if d["ocupa"] and T("db.casas_em", s="") and len(d["fracas"]) - len(o["fracas"]) >= 3:
        como.append(T("db.ocupa", p=pc(b, d["ocupa"][0])))
    elif d["controla"] and len(d["fracas"]) - len(o["fracas"]) >= 3:
        sq, at = d["controla"][0]
        como.append(T("db.controla", p=pc(b, at), s=mc(chess.square_name(sq), [chess.square_name(sq)], lado)))
    return base + " " + (T("db.aproveita", c=T("db.e").join(como)) if como else T("db.nao"))


def texto_postos(b: chess.Board) -> str:
    """Comentário breve dos postos avançados. Ex.: 'Posto avançado: o bispo preto em f5.' (em negrito, marcado ao passar o mouse)."""
    itens = []
    for sq, lado, _ in destaques(b, "postos_avancados")["casas"]:
        s_ = chess.parse_square(sq)
        if b.piece_at(s_) is not None: itens.append(pc(b, s_))
    if not itens: return ""
    itens = itens[:3]
    return T("po.um" if len(itens) == 1 else "po.varios", l=T("db.e").join(itens) if len(itens) <= 2 else ", ".join(itens[:-1]) + T("db.e") + itens[-1])


def texto_pecas(b: chess.Board) -> str:
    """Cavalos mal colocados, bispos ruins e peões passados avançados, em frases curtas (peças e casas em negrito, marcadas no tabuleiro)."""
    frases = []
    junta = lambda itens: itens[0] if len(itens) == 1 else ", ".join(itens[:-1]) + T("db.e") + itens[-1]
    maus = [pc(b, s, extra=uteis) for c in (True, False) for s, uteis in cavalos(b, c) if cavalo_mal(s, uteis)][:2]
    if maus: frases.append(T("po.cavalo" if len(maus) == 1 else "po.cavalos", l=junta(maus)))
    ruins = [pc(b, s, extra=meus) for c in (True, False) for s, meus in bispos_maus(b, c)][:2]
    if ruins: frases.append(T("po.bispo" if len(ruins) == 1 else "po.bispos", l=junta(ruins)))
    passados = [s for c in (True, False) for s in peoes_passados(b, c) if (chess.square_rank(s) if c else 7 - chess.square_rank(s)) >= 4]
    passados = [pc(b, s) for s in passados][:3]
    if passados: frases.append(T("po.passado" if len(passados) == 1 else "po.passados", l=junta(passados)))
    return " ".join(frases)


def texto_rei(b: chess.Board) -> str:
    """Quando um dos reis está sob pressão (xeque com poucas respostas, poucas casas de fuga, casas ao redor atacadas, raio-x), diz isso
    numa frase. O rei sai em negrito e, ao passar o mouse, a tela marca ele e as casas ao redor que estão atacadas."""
    melhor = None
    for c in (chess.WHITE, chess.BLACK):
        k = b.king(c)
        if k is None: continue
        zona = list(chess.SquareSet(chess.BB_KING_ATTACKS[k]))
        atacadas_sq = [s for s in zona if b.is_attacked_by(not c, s)]
        fuga = len(_fuga(b, k, c))
        raiox = len(_raiox(b, k, not c))
        em_xeque = b.turn == c and b.is_check()
        respostas = b.legal_moves.count() if (b.turn == c) else None
        nota = (3 if em_xeque else 0) + (4 - min(fuga, 4)) + len(atacadas_sq) + 2 * raiox
        if melhor is None or nota > melhor[0]: melhor = (nota, c, k, atacadas_sq, fuga, raiox, em_xeque, respostas)
    if melhor is None: return ""
    nota, c, k, atacadas_sq, fuga, raiox, em_xeque, respostas = melhor
    partes = []
    if em_xeque and respostas is not None and respostas <= 3:
        partes.append(T("rk.xeque", n=respostas, v=P(respostas, "rk.resp")))
    if fuga <= 1: partes.append(T("rk.fuga"))
    if len(atacadas_sq) >= 2: partes.append(T("rk.zona"))
    if raiox: partes.append(T("rk.raiox"))
    if nota < 6 or len(partes) < 2: return ""
    return T("rk.base", k=pc(b, k, extra=atacadas_sq, cap=True), m=", ".join(partes))
