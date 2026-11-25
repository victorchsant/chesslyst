"""Relatório da partida: transforma a análise já feita num roteiro de slides e num texto no estilo de livro de xadrez.

Não consulta a engine: usa as linhas já calculadas (`job["rows"]`) e os dados brutos (`job["raws"]`).
Cada "momento" traz o diagrama marcado, a explicação, as variantes (com a posição depois de cada lance) e o roteiro
falado, já sem a notação abreviada ("Cf3" vira "cavalo f 3") para a voz do navegador ler bem.
"""
from __future__ import annotations
import html, re
import chess
from .explica import _notacao, _mlance, _fmt_av, _SAN
from .precisao import numeros as _numeros
from .relogio import fmt as fmt_tempo
from .livro import reflexoes
from .livro import montar_livro, fio_da_partida
from .focos import fases, perfil
from .i18n import T, P, num, lang

SINAIS = {"brilhante": "!!", "imprecisao": "?!", "erro": "?", "grave": "??"}   # "excelente" não leva "!": é um pouco abaixo do melhor
MAX_PRINCIPAIS, MAX_COMPLETO = 8, 40
COR_MELHOR, COR_JOGADO = "#1e9e5a", "#e0383e"


# ---------------------------------------------------------------- texto falado
_PECA_PT = {"K": "rei", "Q": "dama", "R": "torre", "B": "bispo", "N": "cavalo"}
_PECA_EN = {"K": "king", "Q": "queen", "R": "rook", "B": "bishop", "N": "knight"}
_LANCE = re.compile(r"^([KQRBN])?([a-h])?([1-8])?(x)?([a-h])([1-8])(?:=([QRBN]))?([+#])?$")


def falado(san: str) -> str:
    """'Bxc3+' -> 'bispo toma c 3, xeque'."""
    en = lang() == "en"
    fim = {"+": (", check" if en else ", xeque"), "#": (", checkmate" if en else ", xeque-mate")}
    if san.startswith("O-O"):
        longo = san.startswith("O-O-O")
        base = ("long castle" if longo else "short castle") if en else ("roque grande" if longo else "roque pequeno")
        return base + fim.get(san[-1], "")
    m = _LANCE.match(san)
    if not m: return san
    peca, col, fil, toma, c, f, promo, sufixo = m.groups()
    nomes = _PECA_EN if en else _PECA_PT
    out = []
    if peca: out.append(nomes[peca])
    elif toma: out.append("pawn" if en else "peão")
    if col: out.append(col)
    if fil: out.append(fil)
    if toma: out.append("takes" if en else "toma")
    out.append(f"{c} {f}")
    if promo: out.append((("promotes to " if en else "promove a ") + nomes[promo]))
    return " ".join(out) + fim.get(sufixo, "")


def para_voz(trecho: str) -> str:
    """Texto da interpretação (com negritos e notação) -> frases que a voz lê bem."""
    if not trecho: return ""
    s = re.sub(r"</b>([!?]*)\s+(?=(?:\d+\s*(?:\.|…)\s*)?<b[^>]*data-s=)", r"</b>, ", trecho)   # lances em sequência: a voz faz uma pausa entre eles
    s = re.sub(r"\d+\s*(?:\.|…)\s*(?=<b)", "", s)                             # numeração antes dos lances
    s = re.sub(r"<br>\s*•?\s*", ". ", s)

    def negrito(m):
        dentro = re.sub(r"<[^>]+>", "", m.group(2))
        return falado(dentro) if "data-s=" in m.group(1) else dentro
    s = re.sub(r"<b\b([^>]*)>(.*?)</b>", negrito, s, flags=re.S)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    s = re.sub(r"(?<=\d)[!?]+|(?<=xeque)[!?]+|(?<=check)[!?]+|(?<=mate)[!?]+|(?<=pequeno)[!?]+|(?<=grande)[!?]+|(?<=castle)[!?]+", "", s)
    en = lang() == "en"
    s = re.sub(r"\(\s*\+(\d+[.,]\d+)\s*\)", lambda m: (f", evaluation plus {m.group(1)}," if en else f", avaliação mais {m.group(1)},"), s)
    s = re.sub(r"\(\s*[−-](\d+[.,]\d+)\s*\)", lambda m: (f", evaluation minus {m.group(1)}," if en else f", avaliação menos {m.group(1)},"), s)
    s = re.sub(r"(?<![\w])\+(?=\d)", "plus " if en else "mais ", s)
    s = re.sub(r"[−](?=\d|M)", "minus " if en else "menos ", s)
    s = s.replace("→", " to " if en else " para ").replace("…", " ").replace("•", " ").replace("·", ",")
    s = re.sub(r"\s+([,.;:])", r"\1", re.sub(r"\s+", " ", s))
    s = re.sub(r"([.:,;])(?:\s*[.,;])+", r"\1", s)
    return s.strip()


def _frases(texto: str):
    """Divide em frases curtas (a voz de alguns navegadores para no meio de textos longos)."""
    return [x.strip() for x in re.split(r"(?<=[.!?])\s+(?=[^a-z\d])", texto) if x.strip()]


# ---------------------------------------------------------------- notação
def _numero(board: chess.Board) -> str:
    return f"{board.fullmove_number}." if board.turn else f"{board.fullmove_number}…"


def _trecho(rows, fens, ini, fim):
    """Os lances de ini até fim-1 escritos em sequência, com os sinais (!, ?, ??)."""
    out = []
    for i in range(ini, min(fim, len(rows))):
        r = rows[i]
        if not r.get("move"): continue
        b = chess.Board(fens[i])
        prefixo = _numero(b) if (b.turn or i == ini) else ""
        mv = chess.Move.from_uci(r["uci"])
        out.append(prefixo + _mlance(b, mv, r["move"]) + SINAIS.get(r.get("jogada_classe_id"), ""))
    return " ".join(out)


def _marcas(*textos, limite=10):
    """Casas das peças citadas nos textos (as que não são lances), para o diagrama."""
    out, vistos = [], set()
    for t in textos:
        for atrib in re.findall(r"<b\b([^>]*)>", t or ""):
            if "data-s=" in atrib or 'data-t="tinta"' in atrib: continue
            c = re.search(r'data-c="([^"]+)"', atrib)
            if not c: continue
            lado = re.search(r'data-l="([^"]+)"', atrib)
            sq = c.group(1).split(",")[0]                     # a primeira casa é a da peça citada
            if sq not in vistos: vistos.add(sq); out.append([sq, lado.group(1) if lado else "B", "anel"])
    return out[:limite]


def _variante(fen, ucis, titulo, cor, passos_max=5):
    """Avança a variante: posição depois de cada lance e a notação escrita."""
    b = chess.Board(fen); passos = []
    for u in (ucis or [])[:passos_max]:
        m = chess.Move.from_uci(u)
        if m not in b.legal_moves: break
        san, rotulo = b.san(m), _numero(b) + b.san(m)
        b.push(m)
        passos.append(dict(fen=b.fen(), uci=u, san=san, rotulo=rotulo, voz=falado(san)))
    if not passos: return None
    return dict(titulo=titulo, cor=cor, notacao=_notacao(chess.Board(fen), [p["uci"] for p in passos], passos_max), passos=passos)


# ---------------------------------------------------------------- momentos
def _escolhe(rows, completo):
    classes = ("grave", "erro", "brilhante") + (("imprecisao",) if completo else ())
    cand = []
    for i, r in enumerate(rows):
        crit, cid = r.get("critico"), r.get("jogada_classe_id")
        if crit: cand.append((crit["peso"] + 20, i))
        elif cid in classes: cand.append((40 if cid == "brilhante" else (r.get("jogado_perda") or 0) + 10, i))
    cand.sort(key=lambda x: -x[0])
    return sorted(i for _, i in cand[:MAX_COMPLETO if completo else MAX_PRINCIPAIS])


def _momento(rows, raws, fens, i, ini_trecho):
    r, raw = rows[i], raws[i]
    b = chess.Board(fens[i])
    brancas = r["side"] == "B"
    lado = T("w.brancas") if brancas else T("w.pretas")
    crit, cid = r.get("critico"), r.get("jogada_classe_id")
    jogado = r.get("move")
    nome_lance = (_numero(b) + jogado + SINAIS.get(cid, "")) if jogado else T("rel.vez", n=b.fullmove_number, l=lado)
    selo = crit["titulo"] if crit else (r.get("jogada_classe") or "")
    linhas = raw.get("linhas") or []
    melhor = linhas[0] if linhas else None

    blocos = []
    if crit: blocos.append(dict(rotulo=T("mc.rotulo"), html=crit["texto"], principal=True))
    if jogado and r.get("jogada_texto"):
        blocos.append(dict(rotulo=T("rel.lance", c=r["jogada_classe"]), html=r["jogada_texto"], principal=not crit))
    if r.get("avaliacao_texto"): blocos.append(dict(rotulo=T("rel.avaliacao"), html=r["avaliacao_texto"], principal=True))
    motivos = [m for m in (r.get("motivos") or "").split(" | ") if m]
    if motivos: blocos.append(dict(rotulo=T("rel.porque"), html="<ul>" + "".join(f"<li>{m}</li>" for m in motivos) + "</ul>", principal=False))
    if r.get("posicao_texto"): blocos.append(dict(rotulo=T("rel.posicao"), html=r["posicao_texto"], principal=False))

    setas = []
    if jogado and (not melhor or r["uci"] != melhor["uci"]): setas.append([r["uci"][:2], r["uci"][2:4], COR_JOGADO])
    if melhor: setas.append([melhor["uci"][:2], melhor["uci"][2:4], COR_MELHOR])
    legenda = []
    if melhor: legenda.append([COR_MELHOR, T("rel.leg_melhor", m=melhor["san"])])
    if len(setas) > 1: legenda.append([COR_JOGADO, T("rel.leg_jogado", m=jogado)])

    variantes = []
    if melhor:
        v = _variante(fens[i], melhor.get("pv_uci"), T("rel.var_melhor", a=_fmt_av(melhor["cp"], melhor["mate"])), COR_MELHOR)
        if v: variantes.append(v)
    if jogado and melhor and r["uci"] != melhor["uci"] and (r.get("jogado_perda") or 0) >= 5:
        v = _variante(fens[i], raw.get("pv_jogado"), T("rel.var_jogado", m=jogado), COR_JOGADO)
        if v: variantes.append(v)

    # roteiro falado: v = variante mostrada (-1 = diagrama principal), k = quantos lances dela já foram feitos
    abertura = T("rel.voz_momento", s=selo, n=b.fullmove_number, l=lado) if selo else ""
    if jogado: abertura += " " + T("rel.voz_jogado", x=falado(jogado))
    falas = [dict(texto=abertura.strip(), v=-1, k=0)]
    for bl in blocos:
        if bl["principal"]:
            falas += [dict(texto=f, v=-1, k=0) for f in _frases(para_voz(bl["html"]))]
    for n, v in enumerate(variantes):
        falas.append(dict(texto=T("rel.voz_var_melhor") if v["cor"] == COR_MELHOR else T("rel.voz_var_jogado"), v=n, k=0))
        falas += [dict(texto=p["voz"] + ".", v=n, k=k + 1) for k, p in enumerate(v["passos"])]

    return dict(tipo="critico" if crit else "lance", i=i, titulo=nome_lance, selo=selo, classe=cid or "",
                antes=_trecho(rows, fens, ini_trecho, i), antes_comentarios=_comentarios(rows, fens, ini_trecho, i),
                fen=fens[i], setas=setas, casas=_marcas(*(bl["html"] for bl in blocos if bl["principal"])), legenda=legenda,
                aval=_fmt_av(r["engine_cp"], r["engine_mate"]) if (r.get("engine_cp") is not None or r.get("engine_mate") is not None) else "",
                acerto=round(r["indice"]), faixa=r["faixa"], blocos=blocos, variantes=variantes, falas=[f for f in falas if f["texto"]])


def _comentarios(rows, fens, ini, fim, so_fracos=True):
    """Comentários curtos dos lances do trecho que não viraram momento (usados no relatório completo)."""
    out = []
    for i in range(ini, min(fim, len(rows))):
        r = rows[i]
        if not r.get("move") or not r.get("jogada_texto"): continue
        if so_fracos and r.get("jogada_classe_id") not in ("imprecisao", "erro", "grave", "brilhante", "bom"): continue
        b = chess.Board(fens[i])
        out.append(dict(lance=_numero(b) + r["move"] + SINAIS.get(r.get("jogada_classe_id"), ""), classe=r["jogada_classe"], html=r["jogada_texto"]))
    return out


def _data(info):
    m = re.match(r"(\d{4})\.(\d\d)\.(\d\d)", info.get("Date") or "")
    if not m: return ""
    a, mes, d = m.groups()
    return f"{a}-{mes}-{d}" if lang() == "en" else f"{d}/{mes}/{a}"


def _falas_bloco(l):
    """O que a voz diz num bloco: cada fala aponta o comentário (p) e, nas variantes e lances, o passo no tabuleiro (s, k)."""
    titulo = _SAN.sub(lambda x: falado(x.group(0)), l["titulo"]).replace("?", "").replace("!", "")
    out = [dict(texto=f, p=-1) for f in _frases(para_voz(f"{l['selo']}. {titulo}."))]
    for n, p in enumerate(l["paragrafos"]):
        rotulo = _SAN.sub(lambda x: falado(x.group(0)), p.get("rotulo") or "")
        if p.get("cab"):
            out.append(dict(texto=rotulo + ".", p=-1)); continue
        seq = p.get("seq")
        if p.get("lances") and seq is not None and seq < len(l["seqs"]):
            out.append(dict(texto=rotulo + ".", p=n, s=seq, k=0))
            out += [dict(texto=falado(re.sub(r"^\d+(?:\.|…)|[!?]+$", "", x["rotulo"])) + ".", p=n, s=seq, k=k)
                    for k, x in enumerate(l["seqs"][seq]["passos"]) if k]
            continue
        texto = para_voz(p["html"])
        if rotulo: texto = f"{rotulo}. {texto}"
        out += [dict(texto=f, p=n) for f in _frases(texto)]
    return [x for x in out if x["texto"].strip(" .")]


def _fim_por_repeticao(rows, fens, resultado):
    """Quando a partida acaba em empate com a posição final repetida três vezes: a frase que conta como terminou."""
    if resultado != "1/2-1/2" or not rows: return ""
    posicoes = list(fens) + ([rows[-1]["fen_depois"]] if rows[-1].get("move") and rows[-1].get("fen_depois") else [])
    chave = lambda f: " ".join(f.split()[:4])
    vezes = [k for k, f in enumerate(posicoes) if chave(f) == chave(posicoes[-1])]
    if len(vezes) < 3: return ""
    texto = T("rel.repeticao", n=len(vezes), m=chess.Board(posicoes[vezes[0]]).fullmove_number)
    for lado, nome in (("B", T("w.brancas")), ("P", T("w.pretas"))):
        if sum(1 for r in rows[vezes[0]:] if r.get("side") == lado and (r.get("move") or "").endswith("+")) >= 2:
            texto += " " + T("rel.rep_xeques", l=nome)
    return texto


def montar(job: dict, modo: str = "completo") -> dict:
    """Relatório completo da análise feita até agora. modo: "principais" (momentos que decidem) ou "completo"."""
    rows = [r for r in job.get("rows") or [] if r]
    raws = (job.get("raws") or [])[:len(rows)]
    rows = rows[:len(raws)]
    if not rows: return dict(erro=T("rel.sem"))
    fens = [r["fen"] for r in rows]
    info = job.get("info") or {}
    completo = True                       # o relatório cobre sempre a partida inteira
    modo = "completo"
    jogados = sum(1 for r in rows if r.get("move"))
    total = len(job.get("lances") or [])
    nomes = {"B": info.get("White") or T("w.brancas"), "P": info.get("Black") or T("w.pretas")}
    numeros = _numeros(rows, raws, total)

    # abertura: até onde a partida seguiu a teoria
    abertura = None
    nomes_ab = job.get("aberturas") or []
    teoria = [i for i, r in enumerate(rows) if r.get("teoria_partidas") and r["teoria_partidas"] >= 20]
    ult_teoria = teoria[-1] if teoria else 0
    com_nome = [x for x in nomes_ab[:len(rows)] if x]
    if com_nome:
        eco = com_nome[-1]
        nome = eco[1] if lang() == "en" else eco[2]
        k = min(max(ult_teoria, 1), len(rows) - 1)
        texto = T("rel.ab_texto", e=eco[0], a=nome)
        if teoria:
            texto += " " + T("rel.ab_teoria", n=chess.Board(fens[ult_teoria]).fullmove_number)
            if ult_teoria < len(rows) - 1 and rows[ult_teoria].get("move"):      # o lance que levou a uma posição pouco vista
                b_ = chess.Board(fens[ult_teoria])
                texto += " " + T("rel.saiu_teoria", x=_numero(b_) + _mlance(b_, chess.Move.from_uci(rows[ult_teoria]["uci"]), rows[ult_teoria]["move"]))
        falas = [dict(texto=f, v=-1, k=0) for f in _frases(para_voz(texto))]
        abertura = dict(titulo=f"{eco[0]} · {nome}", texto=texto, fen=fens[k], lances=_trecho(rows, fens, 0, k), falas=falas)

    escolhidos = _escolhe(rows, completo)
    momentos, ini = [], (min(max(ult_teoria, 1), len(rows) - 1) if abertura else 0)
    for i in escolhidos:
        ini = min(ini, i)
        momentos.append(_momento(rows, raws, fens, i, ini))
        ini = i + 1 if rows[i].get("move") else i

    # conclusão
    ult = rows[-1]
    res = info.get("Result") or "*"
    frases = [T({"1-0": "rel.res_b", "0-1": "rel.res_p", "1/2-1/2": "rel.res_e"}.get(res, "rel.res_aberto"), b=nomes["B"], p=nomes["P"])]
    qb, qp = (numeros["B"]["precisao"], numeros["P"]["precisao"]) if numeros else (None, None)
    if qb is not None and qp is not None:
        frases.append(T("rel.precisao", b=num(qb), p=num(qp), nb=nomes["B"], np=nomes["P"]))
    viradas = [(i, r) for i, r in enumerate(rows) if r.get("critico") and r["critico"]["tipo"] == "virada"]
    if viradas:
        i, r = max(viradas, key=lambda x: x[1]["critico"]["peso"])
        frases.append(T("rel.maior_virada", n=len(viradas), v=P(len(viradas), "rel.virada"), x=_numero(chess.Board(fens[i])) + r["move"]))
    else:
        frases.append(T("rel.sem_virada"))
    ucis_ult = ult.get("uci")
    fen_final = ult.get("fen_depois") or ult["fen"]
    ini_fim = (momentos[-1]["i"] + (1 if rows[momentos[-1]["i"]].get("move") else 0)) if momentos else ini
    conclusao = dict(texto=" ".join(frases), fen=fen_final, ult=[ucis_ult[:2], ucis_ult[2:4]] if (ult.get("fen_depois") and ucis_ult) else [],
                     lances=_trecho(rows, fens, ini_fim, len(rows)),
                     comentarios=_comentarios(rows, fens, ini_fim, len(rows)),
                     falas=[dict(texto=f, v=-1, k=0) for f in _frases(para_voz(" ".join(frases)))])

    partes = [info.get("BroadcastName") or info.get("Event") or "", _data(info), res if res != "*" else T("rel.andamento")]
    capa = dict(brancas=nomes["B"], pretas=nomes["P"], elo_b=info.get("WhiteElo") or "", elo_p=info.get("BlackElo") or "",
                detalhe=" · ".join(p for p in partes if p and p != "?"), resultado=res,
                parcial=T("rel.parcial", n=jogados, t=total) if total and jogados < total else "")
    capa["falas"] = [dict(texto=T("rel.voz_capa", b=nomes["B"], p=nomes["P"]), v=-1, k=0)]

    def voz_resumo():
        out = []
        for lado in ("B", "P"):
            x = numeros[lado] if numeros else None
            if not x or x["precisao"] is None: continue
            out.append(dict(texto=T("rel.voz_resumo", n=nomes[lado], q=num(x["precisao"]), i=x["contagem"]["imprecisao"], e=x["contagem"]["erro"],
                                    g=x["contagem"]["grave"]), v=-1, k=0))
        return out

    tabela = []
    for i, r in enumerate(rows):
        if not r.get("move"): continue
        b_ = chess.Board(fens[i])
        depois = b_.copy(stack=False); depois.push(chess.Move.from_uci(r["uci"]))
        tabela.append(dict(fen=depois.fen(), uci=r["uci"], n=b_.fullmove_number, brancas=b_.turn, san=r["move"] + SINAIS.get(r.get("jogada_classe_id"), ""), lance=_numero(chess.Board(fens[i])) + r["move"] + SINAIS.get(r.get("jogada_classe_id"), ""),
                           aval=_fmt_av(r["engine_cp"], r["engine_mate"]) if (r.get("engine_cp") is not None or r.get("engine_mate") is not None) else "",
                           acerto=round(r["indice"]), jogada=None if r.get("jogada_indice") is None else round(r["jogada_indice"]),
                           classe=r.get("jogada_classe") or "", critico=bool(r.get("critico"))))

    extremos = {}
    com_aval = [(i, r) for i, r in enumerate(rows) if r.get("engine_cp") is not None or r.get("engine_mate") is not None]
    for lado, melhor in (("B", max), ("P", min)):
        if not com_aval: break
        i, r = melhor(com_aval, key=lambda x: (x[1]["engine_brancas"], (x[1].get("engine_cp") or 0)))
        if (r["engine_brancas"] > 55) if lado == "B" else (r["engine_brancas"] < 45):
            b_ = chess.Board(fens[i])
            extremos[lado] = f"{_fmt_av(r['engine_cp'], r['engine_mate'])} ({T('rel.no_lance', n=b_.fullmove_number)})"
    fim_teoria = (ult_teoria if teoria else 16) if abertura else 0          # sem dados de teoria: os primeiros 8 lances
    livro = montar_livro(rows, raws, fens, momentos, fim_teoria, abertura)
    fio = fio_da_partida(rows, fens, momentos, abertura)
    fases_txt, desfecho = perfil(rows, fens, fases(rows, fens, fim_teoria), res)
    # a partida em imagens: uma posição a cada poucos lances (usada para completar as páginas do PDF)
    imagens = []
    for i, r in enumerate(rows):
        if not r.get("uci") or not r.get("fen_depois"): continue
        b_ = chess.Board(fens[i])
        imagens.append(dict(i=i, fen=r["fen_depois"], uci=r["uci"], rotulo=_numero(b_) + r["move"] + SINAIS.get(r.get("jogada_classe_id"), "")))
    # o relógio e a forma como a partida acabou
    pensadas = reflexoes(rows, quantas=1)
    for i in pensadas:
        r = rows[i]; b_ = chess.Board(fens[i])
        fio.append(T("lv.fio_relogio", x=_numero(b_) + _mlance(b_, chess.Move.from_uci(r["uci"]), r["move"]) + SINAIS.get(r.get("jogada_classe_id"), ""),
                     l=T("w.brancas") if r["side"] == "B" else T("w.pretas"), t=fmt_tempo(r["tempo_gasto"])))
    fim = _fim_por_repeticao(rows, fens, res)
    if fim:
        desfecho = f"{desfecho} {fim}"
        conclusao["texto"] += " " + fim
        conclusao["falas"] += [dict(texto=f, v=-1, k=0) for f in _frases(para_voz(fim))]
        if livro: livro[-1]["paragrafos"].append(dict(rotulo=T("lv.r_terminou"), html=fim, marca=None))
    for l in livro: l["falas"] = _falas_bloco(l)
    falas_topo = capa["falas"] + voz_resumo() + [dict(texto=f, v=-1, k=0) for f in _frases(para_voz(" ".join([fases_txt, desfecho] + [x + "." if not x.endswith(".") else x for x in fio])))]
    falas_numeros = [dict(texto=T("rel.voz_numeros"), v=-1, k=0)] + voz_resumo()
    return dict(modo=modo, falas_topo=falas_topo, livro=livro, fio=fio, fases=fases_txt, desfecho=desfecho, imagens=imagens, capa=capa, numeros=numeros, extremos=extremos, falas_numeros=falas_numeros, falas_resumo=voz_resumo(), abertura=abertura, momentos=momentos, conclusao=conclusao,
                grafico=[r["engine_brancas"] for r in rows], marcos=[dict(i=m["i"], rotulo=m["titulo"], critico=m["tipo"] == "critico") for m in momentos],
                tabela=tabela)
