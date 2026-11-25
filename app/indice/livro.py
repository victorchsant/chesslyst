"""O relatório em formato de livro (o PDF): poucos diagramas, cada um ao lado de uma explicação.

Cada "linha" é um diagrama com texto, e cabem cerca de três por página:
 - "abertura": a posição a que a abertura levou;
 - "trecho": vários lances da partida resumidos, com as ideias do jogo (o que mudou, o que se trocou, os planos);
 - "momento": a posição em que a partida se decide, com o lance indicado e a linha da engine;
 - "variante": a posição a que a linha decisiva da engine chegaria.

As ideias saem de regras sobre a própria análise (nada de palpite): um lance só é citado como ideia quando a engine
o considera bom.
"""
from __future__ import annotations
import re
import chess
from .critico import estado
from .focos import fases, fase_de, focos
from .explica import _mlance, _notacao, _fmt_av, _ideias, _minusc, _lista, _material
from .posicional import mc, peoes_passados, peoes_isolados, peoes_dobrados, bispos_maus
from .i18n import T, lang

MAX_PASSOS_ATE = 10     # quantos lances o passador de um momento mostra antes da posição
MIN_TRECHO = 6          # meios-lances: menos que isso entra junto do momento seguinte
MAX_TRECHO = 24         # um trecho maior é dividido
MAX_VARIANTES = 3       # diagramas de variante (os momentos que mais custaram)
FORTES = ["garfo", "cravada", "dobra", "setima", "posto", "passado", "aberta", "semi", "fianchetto", "quebra"]
BOAS = ("brilhante", "melhor", "excelente")
FRACAS = ("imprecisao", "erro", "grave")
SINAIS = {"brilhante": "!!", "excelente": "!", "imprecisao": "?!", "erro": "?", "grave": "??"}


def _numero(b):
    return f"{b.fullmove_number}." if b.turn else f"{b.fullmove_number}…"


def _lado(c):
    return T("w.brancas") if c else T("w.pretas")


def _junta(itens):
    return itens[0] if len(itens) == 1 else ", ".join(itens[:-1]) + T("db.e") + itens[-1]


def _aval(r):
    if r.get("engine_cp") is None and r.get("engine_mate") is None: return ""
    return _fmt_av(r["engine_cp"], r["engine_mate"])


def _fim_de(rows, fens, b):
    """Posição depois do lance b-1 (a do começo do lance b)."""
    if b < len(fens): return chess.Board(fens[b])
    t = chess.Board(fens[b - 1]); t.push(chess.Move.from_uci(rows[b - 1]["uci"]))
    return t


def _lance_txt(rows, fens, i):
    t = chess.Board(fens[i])
    return _numero(t) + _mlance(t, chess.Move.from_uci(rows[i]["uci"]), rows[i]["move"]) + SINAIS.get(rows[i].get("jogada_classe_id"), "")


def _notacao_jogo(rows, fens, a, b):
    out = []
    for i in range(a, b):
        if not rows[i].get("move"): continue
        t = chess.Board(fens[i])
        x = _lance_txt(rows, fens, i)
        out.append(x if (t.turn or i == a) else x.split("…", 1)[1])
    return " ".join(out)


# ---------------------------------------------------------------- sequências do passador
def _sequencia(rotulo, fen0, ucis, cor="#2563eb"):
    """Posições de uma sequência de lances: a inicial e a de depois de cada lance."""
    b = chess.Board(fen0); passos = [dict(fen=b.fen(), uci="", rotulo="")]
    for u in ucis:
        m = chess.Move.from_uci(u)
        if m not in b.legal_moves: break
        x = _numero(b) + b.san(m)
        b.push(m); passos.append(dict(fen=b.fen(), uci=u, rotulo=x))
    return dict(rotulo=rotulo, cor=cor, passos=passos) if len(passos) > 1 else None


def _paragrafos_focos(lista):
    return [dict(rotulo=f["nome"], html=f["html"], foco=f["id"]) for f in lista]


# ---------------------------------------------------------------- o que mudou entre duas posições
def _trocas(ini: chess.Board, fim: chess.Board):
    """-> (frase das peças que saíram, frase do saldo de material)."""
    nomes = {chess.QUEEN: "p.dama", chess.ROOK: "p.torre", chess.BISHOP: "p.bispo", chess.KNIGHT: "p.cavalo"}
    sairam = {}
    for c in (True, False):
        sairam[c] = [t for t in nomes for _ in range(max(0, len(ini.pieces(t, c)) - len(fim.pieces(t, c))))]
    pares = list(zip(sairam[True], sairam[False]))
    frases = []
    if pares:
        grupos = {}
        for par in pares: grupos[par] = grupos.get(par, 0) + 1
        itens = []
        for (w, p), n in grupos.items():
            x = T("lv.contra", a=T(f"lv.{nomes[w]}"), b=T(f"lv.{nomes[p]}"))
            itens.append(x + (f" (×{n})" if n > 1 else ""))
        frases.append(T("lv.trocas", l=_junta(itens)))
    saldo = round((_material(fim) - _material(ini)) / 100)
    mat = ""
    if abs(saldo) >= 1: mat = T("lv.saldo", l=_lado(saldo > 0), n=abs(saldo), p=T("lv.ponto1" if abs(saldo) == 1 else "lv.pontos"))
    return " ".join(frases), mat


def _estrutura(ini: chess.Board, fim: chess.Board):
    """Peões passados, isolados, dobrados e bispos ruins que surgiram. -> (frase, casas para marcar no diagrama)."""
    frases, casas = [], []
    for c in (True, False):
        itens = []
        for chave, funcao in (("lv.passado", peoes_passados), ("lv.isolado", peoes_isolados), ("lv.dobrado", peoes_dobrados)):
            antes, depois = funcao(ini, c), funcao(fim, c)
            if len(depois) <= len(antes): continue
            colunas = {chess.square_file(s) for s in antes}
            novos = [s for s in depois if chess.square_file(s) not in colunas] or list(depois)
            nomes = [chess.square_name(s) for s in novos[:3]]
            itens.append(T(chave if len(nomes) == 1 else chave + "s", s=mc(_junta(nomes), nomes, "B" if c else "P")))
            casas += [[n, "B" if c else "P", "anel"] for n in nomes]
        if len(bispos_maus(fim, c)) > len(bispos_maus(ini, c)):
            s, meus = bispos_maus(fim, c)[0]
            itens.append(T("lv.bispo_ruim", s=mc(chess.square_name(s), [chess.square_name(x) for x in [s] + meus], "B" if c else "P")))
            casas.append([chess.square_name(s), "B" if c else "P", "anel"])
        if itens: frases.append(T("lv.passou_a_ter", l=_lado(c), i=_junta(itens)))
    return " ".join(frases), casas[:6]


def _a_favor(r):
    """O que a análise de posição aponta a favor de cada lado (grupos com peso, fora o material)."""
    por = {True: [], False: []}
    for g in sorted(r.get("posicao_grupos") or [], key=lambda g: -abs(g["cp"])):
        if g["id"] != "material" and abs(g["cp"]) >= 30: por[g["cp"] > 0].append(T("gv." + g["id"]))
    frases = [T("lv.favor", l=_lado(c), i=_junta(por[c][:2])) for c in (True, False) if por[c]]
    return " ".join(frases)


def _ideias_jogo(rows, fens, a, b, limite=3):
    """Os lances do trecho com uma ideia clara, que a engine aprova. -> lista de frases (na ordem da partida)."""
    achadas = []
    for i in range(a, b):
        r = rows[i]
        if not r.get("uci") or r.get("jogada_classe_id") not in BOAS: continue
        t = chess.Board(fens[i])
        y = _ideias(t, chess.Move.from_uci(r["uci"]))
        if y and y[0][0] in FORTES: achadas.append((FORTES.index(y[0][0]), i, y[0][0], y[0][1]))
    escolhidas, tipos = [], set()
    for _, i, tipo, frase in sorted(achadas):
        if tipo in tipos: continue
        tipos.add(tipo); escolhidas.append((i, frase))
        if len(escolhidas) == limite: break
    return [T("lv.ideia", m=_lance_txt(rows, fens, i), l=_lado(rows[i]["side"] == "B"), f=_minusc(f)) for i, f in sorted(escolhidas)]


def _avaliacao_trecho(rows, a, b):
    seg = [r for r in rows[a:min(b + 1, len(rows))] if _aval(r)]
    if not seg: return ""
    estados = [estado(r["engine_brancas"]) for r in seg]
    menor, maior = min(seg, key=lambda r: r["engine_brancas"]), max(seg, key=lambda r: r["engine_brancas"])
    if len(set(estados)) == 1:
        if _aval(menor) == _aval(maior): return T("lv.av_igual1", e=T(f"mc.e{estados[0]}"), a=_aval(menor))
        return T("lv.av_igual", e=T(f"mc.e{estados[0]}"), a=_aval(menor), b=_aval(maior))
    if estados[0] == estados[-1]:
        return T("lv.av_voltou", e=T(f"mc.e{estados[0]}"), a=_aval(menor), b=_aval(maior))
    return T("lv.av_mudou", de=T(f"mc.e{estados[0]}"), para=T(f"mc.e{estados[-1]}"), a=_aval(seg[0]), b=_aval(seg[-1]))


def _linha_trecho(rows, fens, a, b, titulo, fase, tipo="trecho", extra=""):
    ini, fim = chess.Board(fens[a]), _fim_de(rows, fens, b)
    pecas, saldo = _trocas(ini, fim)
    estrutura, casas = _estrutura(ini, fim)
    ideias = _ideias_jogo(rows, fens, a, b, 2 if tipo == "abertura" else 3)
    deslizes = [i for i in range(a, b) if rows[i].get("jogada_classe_id") in FRACAS]
    lista = focos(rows, fens, fase, a, b)
    par = []
    if extra: par.append(dict(rotulo="", html=extra))
    par.append(dict(rotulo=T("lv.r_lances"), html=_notacao_jogo(rows, fens, a, b), lances=True))
    corpo = " ".join(x for x in (_avaliacao_trecho(rows, a, b) if tipo != "abertura" else "", pecas, saldo) if x)
    if fim.is_checkmate(): corpo = " ".join(x for x in (pecas, T("lv.fim_mate")) if x)
    if corpo: par.append(dict(rotulo=T("lv.r_correu"), html=corpo))
    if ideias: par.append(dict(rotulo=T("lv.r_ideias"), html=" ".join(ideias)))
    if deslizes:
        itens = []
        for i in sorted(sorted(deslizes, key=lambda i: -(rows[i].get("jogado_perda") or 0))[:3]):
            r = rows[i]; t = chess.Board(fens[i])
            melhor = r["linhas"][0] if r.get("linhas") else None
            x = _lance_txt(rows, fens, i)
            if melhor and melhor["uci"] != r["uci"]: x += " " + T("lv.preferia", m=_mlance(t, chess.Move.from_uci(melhor["uci"]), melhor["san"]))
            itens.append(x)
        par.append(dict(rotulo=T("lv.r_deslizes"), html="; ".join(itens) + "."))
    if estrutura and not any(f["id"] in ("peoes", "debilidades") for f in lista): par.append(dict(rotulo=T("lv.r_mudou"), html=estrutura))
    par += _paragrafos_focos(lista)
    marcas = [x for f in lista for x in f["casas"]] or casas
    vistos = {}
    for x in marcas: vistos.setdefault(x[0], x)
    ult = rows[b - 1]["uci"]
    seq = _sequencia(T("lv.seq_trecho"), fens[a], [rows[i]["uci"] for i in range(a, b)])
    return dict(tipo=tipo, fase=fase, selo=T("fc.f_" + fase), titulo=titulo, fen=fim.fen(), setas=[], casas=list(vistos.values())[:6],
                ult=[ult[:2], ult[2:4]], legenda=[], figura=T("lv.fig_apos", x=_numero(chess.Board(fens[b - 1])) + rows[b - 1]["move"]),
                paragrafos=par, seqs=[seq] if seq else [], inicial=-1)


def _frases_curtas(texto, limite):
    """As primeiras frases de um texto com marcações, sem cortar no meio, até cerca de `limite` caracteres visíveis."""
    out, n = [], 0
    for f in re.split(r"(?<=\.)\s+(?=[A-ZÀ-Ú<])", texto or ""):
        visivel = len(re.sub(r"<[^>]+>", "", f))
        if out and n + visivel > limite: break
        out.append(f); n += visivel
    return " ".join(out)


def _linha_momento(rows, fens, m, antes, tem_variante, fase):
    i = m["i"]; r = rows[i]
    crit = r.get("critico")
    par = []
    if antes: par.append(dict(rotulo=T("lv.r_ate"), html=antes, lances=True))
    principal = []
    if crit: principal.append(crit["texto"])
    if r.get("jogada_texto") and (not crit or (crit["tipo"] == "unico" and not crit.get("achou"))): principal.append(r["jogada_texto"])
    if not crit and r.get("avaliacao_texto"): principal.append(r["avaliacao_texto"])
    if principal: par.append(dict(rotulo="", html=" ".join(principal)))
    # por que era difícil (motivos curtos da chance de acerto; as linhas da engine já aparecem abaixo)
    curtos = [x for x in (r.get("motivos") or "").split(" | ") if x and "<br>" not in x and "data-s=" not in x]
    if curtos: par.append(dict(rotulo=T("lv.r_dificuldade"), html=" ".join(curtos[:2])))
    lista = focos(rows, fens, fase, max(0, i - 4), i, 3)
    # um foco além do texto do momento: o mais relevante para esta posição (os golpes já estão no texto do momento)
    par += _paragrafos_focos([f for f in lista if f["id"] != "taticas"][:1 if tem_variante or crit else 2])
    for v in ([] if tem_variante else m["variantes"]):      # com diagrama de variante logo abaixo, as linhas ficam nele
        par.append(dict(rotulo=v["titulo"], html=v["notacao"], lances=True, cor=v["cor"]))
    meta = f"{T('lv.aval')}: {m['aval']} · {T('lv.acerto')}: {m['acerto']}% ({m['faixa']})"
    a = max(0, i - MAX_PASSOS_ATE)
    seqs = [_sequencia(T("lv.seq_ate"), fens[a], [rows[k]["uci"] for k in range(a, i)])]
    seqs += [_sequencia(v["titulo"], m["fen"], [p["uci"] for p in v["passos"]], v["cor"]) for v in m["variantes"]]
    seqs = [x for x in seqs if x]
    return dict(tipo="momento", fase=fase, selo=T("fc.f_" + fase) + " · " + m["selo"], titulo=m["titulo"], meta=meta, fen=m["fen"], setas=m["setas"], casas=m["casas"], ult=[],
                legenda=m["legenda"], figura=T("lv.fig_antes", x=m["titulo"]), paragrafos=par, seqs=seqs,
                inicial=len(seqs[0]["passos"]) - 1 if seqs and i > a else -1)


def _linha_variante(rows, raws, fens, m):
    """A posição ao fim da linha que a engine indicava, com as ideias de cada passo."""
    i = m["i"]; r = rows[i]
    v = m["variantes"][0]
    ini = chess.Board(fens[i])
    melhor = raws[i]["linhas"][0]
    t = ini.copy(); ideias = []
    for p in v["passos"]:
        mv = chess.Move.from_uci(p["uci"])
        y = _ideias(t, mv)
        if y and len(ideias) < 3 and y[0][0] not in ("salva",):
            ideias.append(T("lv.ideia", m=_numero(t) + _mlance(t, mv), l=_lado(t.turn), f=_minusc(y[0][1])))
        t.push(mv)
    pecas, saldo = _trocas(ini, t)
    estrutura, casas = _estrutura(ini, t)
    par = [dict(rotulo=T("lv.r_linha"), html=v["notacao"], lances=True, cor=v["cor"])]
    if ideias: par.append(dict(rotulo=T("lv.r_ideias"), html=" ".join(ideias)))
    for outra in m["variantes"][1:]:
        par.append(dict(rotulo=outra["titulo"], html=outra["notacao"], lances=True, cor=outra["cor"]))
    corpo = " ".join(x for x in (pecas, saldo, estrutura) if x)
    if corpo: par.append(dict(rotulo=T("lv.r_muda"), html=corpo))
    fecho = T("lv.var_aval", a=_fmt_av(melhor["cp"], melhor["mate"]))
    if r.get("jogado_perda") and r["jogado_perda"] >= 5 and i + 1 < len(rows) and _aval(rows[i + 1]):
        fecho += " " + T("lv.var_jogado", m=r["move"], a=_aval(rows[i + 1]))
    par.append(dict(rotulo=T("rel.avaliacao"), html=fecho))
    p = v["passos"][-1]
    seqs = [x for x in (_sequencia(o["titulo"], m["fen"], [q["uci"] for q in o["passos"]], o["cor"]) for o in m["variantes"]) if x]
    return dict(tipo="variante", seqs=seqs, inicial=-1, selo=T("lv.s_variante"), titulo=T("lv.t_variante", m=melhor["san"]), fen=p["fen"], setas=[], casas=casas,
                ult=[p["uci"][:2], p["uci"][2:4]], legenda=[], figura=T("lv.fig_apos", x=p["rotulo"]), paragrafos=par)


def _sem_repeticao(linhas):
    """Tira o foco que repete o que um dos dois blocos anteriores já disse (mesmo tema, quase o mesmo texto)."""
    recentes = []
    for l in linhas:
        meus, ficam = [], []
        for p in l["paragrafos"]:
            if not p.get("foco"): ficam.append(p); continue
            palavras = set(re.sub(r"<[^>]+>|\d+", " ", p["html"]).split())
            repetido = any(f == p["foco"] and len(palavras & w) >= 0.8 * max(len(palavras), len(w)) for bloco in recentes[-2:] for f, w in bloco)
            meus.append((p["foco"], palavras))
            if not repetido: ficam.append(p)
        recentes.append(meus); l["paragrafos"] = ficam
    return linhas


def montar_livro(rows, raws, fens, momentos, fim_teoria, abertura):
    """-> lista de linhas (diagrama + texto), na ordem da partida, com os trechos cortados nas mudanças de fase."""
    jogados = sum(1 for r in rows if r.get("move"))
    lista = fases(rows, fens, fim_teoria)
    linhas = []
    ini = 0
    if lista and jogados:
        k = min(lista[0][2], momentos[0]["i"] if momentos else jogados)
        if k >= 4:
            titulo = abertura["titulo"] if abertura else T("fc.f_abertura")
            linhas.append(_linha_trecho(rows, fens, 0, k, titulo, "abertura", "abertura", abertura["texto"] if abertura else ""))
            ini = k
    com_variante = [m for m in momentos if m["variantes"] and (rows[m["i"]].get("jogado_perda") or 0) >= 10]
    com_variante = {m["i"] for m in sorted(com_variante, key=lambda m: -rows[m["i"]]["jogado_perda"])[:MAX_VARIANTES]}

    def blocos(a, b):
        """Divide [a, b) nas fronteiras das fases; pedaços curtos juntam-se ao vizinho."""
        pedacos = [[fase, max(a, x), min(b, y)] for fase, x, y in lista if min(b, y) > max(a, x)]
        k = 0
        while len(pedacos) > 1 and k < len(pedacos):
            if pedacos[k][2] - pedacos[k][1] < MIN_TRECHO:
                viz = k - 1 if k else 1
                pedacos[viz][1] = min(pedacos[viz][1], pedacos[k][1]); pedacos[viz][2] = max(pedacos[viz][2], pedacos[k][2])
                pedacos.pop(k); k = 0
            else: k += 1
        return pedacos

    def trechos(a, b, ultimo=False):
        pedacos = blocos(a, b)
        for n_p, (fase, x0, y0) in enumerate(pedacos):
            partes = max(1, -(-(y0 - x0) // MAX_TRECHO))
            cortes = [x0 + round((y0 - x0) * k / partes) for k in range(partes + 1)]
            for k in range(partes):
                x, y = cortes[k], cortes[k + 1]
                n1, n2 = chess.Board(fens[x]).fullmove_number, chess.Board(fens[y - 1]).fullmove_number
                titulo = T("lv.t_lances", a=n1, b=n2) if n1 != n2 else T("lv.t_lance", a=n1)
                if ultimo and k == partes - 1 and n_p == len(pedacos) - 1: titulo = T("lv.t_desfecho", t=titulo)
                linhas.append(_linha_trecho(rows, fens, x, y, titulo, fase))

    for m in momentos:
        i = m["i"]; antes = ""
        if i - ini >= MIN_TRECHO: trechos(ini, i)
        elif i > ini: antes = _notacao_jogo(rows, fens, ini, i)
        linhas.append(_linha_momento(rows, fens, m, antes, i in com_variante, fase_de(lista, i)))
        if i in com_variante:
            v = _linha_variante(rows, raws, fens, m); v["fase"] = fase_de(lista, i); linhas.append(v)
        ini = max(ini, i + 1 if rows[i].get("move") else i)
    if jogados > ini: trechos(ini, jogados, ultimo=True)
    return _sem_repeticao(linhas)


def fio_da_partida(rows, fens, momentos, abertura):
    """A partida em poucas linhas: a abertura e cada momento decisivo."""
    out = []
    if abertura: out.append(T("lv.fio_abertura", a=abertura["titulo"]))
    for m in momentos:
        i = m["i"]; r = rows[i]; crit = r.get("critico")
        quem = _lado(r["side"] == "B")
        x = _lance_txt(rows, fens, i) if r.get("move") else m["titulo"]
        if crit and crit["tipo"] == "virada" and i + 1 < len(rows):
            out.append(T("lv.fio_virada", x=x, de=T(f"mc.e{estado(r['engine_brancas'])}"), para=T(f"mc.e{estado(rows[i + 1]['engine_brancas'])}")))
        elif crit:
            out.append(T("lv.fio_achou" if crit.get("achou") else "lv.fio_unico", x=x, l=quem))
        elif r.get("jogada_classe"):
            out.append(T("lv.fio_outro", x=x, l=quem, c=r["jogada_classe"].lower()))
    return out
