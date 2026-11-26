"""Versão online do Chesslyst: o "servidor" roda dentro do navegador (Pyodide), sem servidor nenhum.

shim.js intercepta as chamadas /api/... da interface e as entrega à função `handle` daqui. O Stockfish roda em WebAssembly
(worker do navegador) e é consultado pelas funções JS `sfAnalisa` e `sfJogado`; as consultas ao Lichess (teoria, finais,
transmissões) saem direto do navegador. Reaproveita o pacote `indice` (fórmulas, explicações, posição, aberturas) sem mudanças.

Diferença para a versão local: não há o modelo Maia (rede neural), então a probabilidade de um jogador do nível escolher
cada lance é ESTIMADA a partir das avaliações da engine (`politica`).
"""
import asyncio, io, json, math, re, time, urllib.parse, uuid

import chess, chess.pgn
import js
from pyodide.http import pyfetch

from indice import inicial, pipeline, relogio, relatorio, precisao
from indice.aberturas import nomes as nomes_abertura
from indice.core import analyse, win_pct
from indice.explica import explicar_subida, texto_repeticao
from indice.i18n import set_lang, T
from indice.posicional import destaques as destaques_posicao

JOBS = {}
_CACHE = {}
NOME_MOTOR = "Stockfish (navegador)"


# ----------------------------------------------------------------- rede (Lichess) e engine
async def http_get(url, texto=True):
    r = await pyfetch(url)
    if not r.ok: raise RuntimeError(f"HTTP {r.status}")
    return await r.string()


async def get_json(url):
    if url in _CACHE: return _CACHE[url]
    try: d = json.loads(await http_get(url))
    except Exception: return None
    _CACHE[url] = d
    return d


async def masters(fen):
    """-> (total de partidas, {san: partidas}) ou (None, {})"""
    d = await get_json("https://explorer.lichess.ovh/masters?" + urllib.parse.urlencode({"fen": fen, "moves": 12}))
    if not d: return None, {}
    tot = d["white"] + d["draws"] + d["black"]
    return tot, {m["san"]: m["white"] + m["draws"] + m["black"] for m in d["moves"]}


async def tablebase(fen):
    d = await get_json("https://tablebase.lichess.ovh/standard?" + urllib.parse.urlencode({"fen": fen}))
    if not d or d.get("category") in (None, "unknown"): return None
    res = {"win": "win", "cursed-win": "draw", "draw": "draw", "blessed-loss": "draw", "loss": "loss"}.get(d["category"])
    if res is None: return None
    mv = d["moves"]
    return dict(result=res, legal=len(mv), win_moves=sum(1 for m in mv if m["category"] == "loss"),
                hold_moves=sum(1 for m in mv if m["category"] in ("draw", "cursed-win", "blessed-loss")))


async def motor(fen, n, depth):
    return json.loads(await js.sfAnalisa(fen, n, depth))


async def motor_jogado(fen, uci, depth):
    return json.loads(await js.sfJogado(fen, uci, depth))


def politica(cands, rating):
    """Sem o modelo Maia: probabilidade estimada de um jogador do nível escolher cada candidato (quanto melhor o jogador,
    mais ele se concentra nos melhores lances)."""
    if not cands: return {}
    w0 = [win_pct(c[1], c[2]) for c in cands]
    melhor = max(w0)
    tau = max(2.5, 14.0 - ((rating or 1800) - 1000) / 150.0)        # em pontos de chance de vitória
    pesos = [math.exp(-(melhor - w) / tau) for w in w0]
    tot = sum(pesos) or 1.0
    return {c[0]: p / tot for c, p in zip(cands, pesos)}


def _linha_de(board, info):
    sans, b2 = [], board.copy()
    for u in info["pv"][:8]:
        m = chess.Move.from_uci(u); sans.append(b2.san(m)); b2.push(m)
    return sans


async def colher(board, move, rating, depth, multipv, em_livro, tempo):
    """Equivalente web de pipeline.colher: dados brutos de uma posição (antes de `move`)."""
    pcs = len(board.piece_map())
    tb = await tablebase(board.fen()) if pcs <= pipeline.ENDGAME_PIECES else None
    n = board.legal_moves.count() if (pcs <= pipeline.ENDGAME_PIECES and not tb) else multipv
    n = min(n, board.legal_moves.count())
    r = await motor(board.fen(), n, depth)
    cands, pvs = [], []
    for i in r["linhas"]:
        cands.append((board.san(chess.Move.from_uci(i["pv"][0])), i["cp"], i["mate"]))
        pvs.append(dict(uci=i["pv"][0], pv=_linha_de(board, i), pv_uci=i["pv"][:pipeline.PV_GUARDADA]))
    stable, alvo = None, r["linhas"][0]["pv"][0]
    for d in sorted((int(k) for k in r["bestAt"]), reverse=True):
        if r["bestAt"][str(d)] != alvo: break
        stable = d
    pol = politica(cands, rating)
    book, book_moves = (await masters(board.fen())) if em_livro else (None, {})
    san = jogado = fen_depois = uci = pv_jogado = None
    if move is not None:
        san, uci = board.san(move), move.uci()
        hit = next((j for j, (s_, c_, m_) in enumerate(cands) if s_ == san), None)
        if hit is not None: jogado, pv_jogado = [cands[hit][1], cands[hit][2]], pvs[hit]["pv_uci"]
        else:
            x = await motor_jogado(board.fen(), uci, depth); jogado, pv_jogado = [x["cp"], x["mate"]], x["pv"][:pipeline.PV_GUARDADA]
        b2 = board.copy(); b2.push(move); fen_depois = b2.fen()
    linhas = pipeline.montar_linhas(board, cands, pvs, pol)
    return dict(fen=board.fen(), fen_depois=fen_depois, ply=board.ply() + 1, side="B" if board.turn else "P", move=san, uci=uci,
                rating=rating, cands=cands, pol=pol, linhas=linhas, depth_stable=stable, book_games=book, book_moves=book_moves,
                piece_count=pcs, tb=tb, jogado=jogado, pv_jogado=pv_jogado, outras=[], tempo=tempo, game_over=board.is_game_over())


# ----------------------------------------------------------------- partidas
def parse_jogos(pgn_texto):
    jogos, fh = [], io.StringIO(pgn_texto)
    while (g := chess.pgn.read_game(fh)): jogos.append(g)
    return jogos


async def obtem_pgn(f):
    if f["tipo"] == "pgn": return f["pgn"]
    if f["tipo"] == "lichess":
        gid = re.sub(r".*lichess\.org/(?:game/export/)?([A-Za-z0-9]{8}).*", r"\1", f["id"].strip())
        return await http_get(f"https://lichess.org/game/export/{gid}?clocks=false&evals=false&opening=false")
    if f["tipo"] == "rodada": return await http_get(f"https://lichess.org/api/broadcast/round/{f['round']}.pgn")
    raise ValueError("tipo de fonte desconhecido")


def escolhe_jogo(f, pgn_texto):
    jogos = parse_jogos(pgn_texto)
    if not jogos: return None
    i = int(f.get("jogo", 0))
    return jogos[i] if 0 <= i < len(jogos) else None


async def partida(fonte):
    game = escolhe_jogo(fonte, await obtem_pgn(fonte))
    if game is None: raise ValueError(T("s.jogo"))
    h = game.headers; b = game.board(); fens, lances, ucis = [b.fen()], [], []
    for m in game.mainline_moves():
        lances.append(b.san(m)); ucis.append(m.uci()); b.push(m); fens.append(b.fen())
    info = {k: h.get(k, "") for k in ("White", "Black", "WhiteElo", "BlackElo", "Event", "Result", "Date", "Round", "BroadcastName", "BroadcastURL")}
    return dict(info=info, lances=lances, fens=fens, ucis=ucis, aberturas=nomes_abertura(fens))


# ----------------------------------------------------------------- linhas e jobs (porte de server.py)
def _ant(r, extra=""):
    if r is None or r["jogada_indice"] is None: return None
    return dict(lance=r["move"], uci=r.get("uci"), lado=r.get("side"), indice=r["jogada_indice"], classe=r["jogada_classe"], classe_id=r["jogada_classe_id"],
                texto=(r["jogada_texto"] or "") + ((" " + extra) if extra else ""), tempo=r.get("tempo_texto", ""), critico=r.get("critico"))


def _subida(job, i):
    raws = job.get("raws") or []
    return explicar_subida(raws[i - 1], raws[i]) if 0 < i < len(raws) else None


def push_row(job, raw, i):
    set_lang(job["lang"])
    if raw.get("terminal"):
        row = pipeline.linha_final(chess.Board(raw["fen"]), raw.get("rating"), raw.get("tempo"))
    else:
        pos = pipeline.para_posicao(raw, 0.0)
        row = pipeline.linha(raw, pos, analyse(pos), job["raws"][i - 1] if 0 < i <= len(job.get("raws") or []) else None)
        res = (job.get("info") or {}).get("Result")
        if raw.get("move") is None and res in ("1-0", "0-1", "1/2-1/2"):      # partida encerrada: não há lance a escolher
            row["motivos"] = T("f.encerrada", r=res)
    row["idx"] = i
    row["repeticao_texto"] = texto_repeticao(job.get("fens") or [], job.get("lances") or [], i)
    row["ant"] = _ant(job["rows"][i - 1], _subida(job, i) or "") if i > 0 and i - 1 < len(job["rows"]) else None
    if i < len(job["rows"]): job["rows"][i] = row
    else: job["rows"].append(row)
    job["versao"] += 1
    row["_v"] = job["versao"]
    if i + 1 < len(job["rows"]):
        job["rows"][i + 1]["ant"] = _ant(row, _subida(job, i + 1) or "")
        job["rows"][i + 1]["_v"] = job["versao"]


def traduz_job(job, lang):
    set_lang(lang); job["lang"] = lang
    for i, raw in enumerate(list(job["raws"])): push_row(job, raw, i)


async def rodar_job(job):
    set_lang(job["lang"])
    depth = int(job["depth"]); em_livro, raws = True, []
    job["raws"] = raws
    job["engines"] = dict(referencia=NOME_MOTOR, outras=[])
    try:
        while not job["parar"]:
            try:
                game = escolhe_jogo(job["fonte"], await obtem_pgn(job["fonte"]))
            except Exception as e:
                job["estado"] = "esperando"; job["aviso"] = T("s.fonte", e=e)
                if job["fonte"]["tipo"] == "pgn": raise
                await asyncio.sleep(5); continue
            if game is None: raise ValueError(T("s.jogo"))
            h = game.headers
            job["info"] = {k: h.get(k, "") for k in ("White", "Black", "WhiteElo", "BlackElo", "Event", "Result", "Date", "Round", "BroadcastName", "BroadcastURL")}
            rt = pipeline.ratings(game)
            moves = list(game.mainline_moves()); tempos = relogio.tempos_do_jogo(game)
            board = game.board(); boards = []
            for m in moves: boards.append(board.copy()); board.push(m)
            boards.append(board.copy())
            b0, lances = game.board(), []
            for m in moves: lances.append(b0.san(m)); b0.push(m)
            job["lances"], job["esperado"] = lances, len(boards)
            job["fens"], job["ucis"] = [bb.fen() for bb in boards], [m.uci() for m in moves]
            job["aberturas"] = nomes_abertura(job["fens"])
            if any(i < len(boards) - 1 and raws[i]["fen"] != boards[i].fen() for i in range(min(len(raws), len(boards)))):
                raws.clear(); job["rows"].clear(); em_livro = True
            for i in range(len(raws), len(boards)):
                if job["parar"]: break
                b = boards[i]; set_lang(job["lang"])
                job["atual"], job["atual_ini"] = i, time.time()
                lance = moves[i] if i < len(moves) else None
                side = "B" if b.turn else "P"
                if lance is None and b.is_game_over():
                    raw = dict(fen=b.fen(), move=None, terminal=True, rating=rt[side], tempo=tempos[i])
                    raws.append(raw); push_row(job, raw, i); job["atual"] = None
                    continue
                raw = await colher(b, lance, rt[side], depth, 5, em_livro, tempos[i])
                if em_livro: em_livro = bool(raw["book_games"] and raw["book_games"] >= 20)
                raws.append(raw); push_row(job, raw, i); job["atual"] = None
                await asyncio.sleep(0)
            for i in range(len(moves)):
                if job["parar"]: break
                if i < len(raws) and raws[i]["move"] is None:
                    b, m = boards[i], moves[i]
                    san = b.san(m)
                    j = next((k for k, (s_, c_, m_) in enumerate(raws[i]["cands"]) if s_ == san), None)
                    if j is not None: jog, pvj = [raws[i]["cands"][j][1], raws[i]["cands"][j][2]], raws[i]["linhas"][j].get("pv_uci")
                    else:
                        x = await motor_jogado(b.fen(), m.uci(), depth); jog, pvj = [x["cp"], x["mate"]], x["pv"][:pipeline.PV_GUARDADA]
                    raws[i]["tempo"] = tempos[i]
                    raws[i].update(move=san, uci=m.uci(), jogado=jog, pv_jogado=pvj)
                    b2 = b.copy(); b2.push(m); raws[i]["fen_depois"] = b2.fen()
                    push_row(job, raws[i], i)
            if job["parar"]: break
            resultado = h.get("Result", "*")
            completo = len(raws) == len(boards) and all(r["move"] is not None for r in raws[:len(moves)])
            ao_vivo = job["fonte"].get("ao_vivo") and job["fonte"]["tipo"] != "pgn"
            if not ao_vivo and completo: break
            if ao_vivo and completo and (resultado != "*" or board.is_game_over()): break
            job["estado"] = "ao vivo"; await asyncio.sleep(4)
        job["estado"] = "parado" if job["parar"] else "fim"
    except Exception as e:
        job["estado"] = "erro"; job["aviso"] = repr(e)
    job["atual"] = None


def novo_job(fonte, depth, lang):
    jid = uuid.uuid4().hex[:8]
    job = dict(id=jid, fonte=fonte, depth=depth, rows=[], estado="analisando", aviso="", info={}, parar=False, versao=0,
               engines={}, lances=[], esperado=0, atual=None, atual_ini=0.0, fens=[], ucis=[], lang=lang, raws=[])
    JOBS[jid] = job
    asyncio.ensure_future(rodar_job(job))
    return job


# ----------------------------------------------------------------- "API"
def _ok(obj, code=200): return json.dumps({"_status": code, "corpo": obj}, ensure_ascii=False)


async def handle(metodo, caminho, query_json, corpo_json, lang):
    """Entrega uma chamada /api/... da interface. Devolve um JSON {_status, corpo}."""
    q = json.loads(query_json or "{}"); body = json.loads(corpo_json) if corpo_json else {}
    set_lang(lang or "pt")
    try:
        if caminho == "/api/ping": return _ok({"ok": True})
        if caminho == "/api/engines":
            return _ok(dict(engines=[dict(id="stockfish", nome=NOME_MOTOR, caminho="WebAssembly", argumentos="", opcoes={}, ativa=True)],
                            referencia="stockfish", humano=dict(modo="maia", lc0="", pesos="", argumentos=""), divergencia_peso=0.0))
        if caminho == "/api/baixaveis": return _ok([])
        if caminho == "/api/baixar/estado": return _ok({})
        if caminho == "/api/engines/testar": return _ok({"erro": "indisponível na versão online"}, 400)
        if caminho == "/api/relogio":       # relógios atuais de uma partida de transmissão em andamento
            url = relogio.url_ao_vivo(q.get("round"))
            try: return _ok(relogio.ao_vivo(await http_get(url), q.get("brancas"), q.get("pretas")) if url else {})
            except Exception: return _ok({})
        if caminho == "/api/inicial":
            return _ok(await inicial.escolhe(http_get))
        if caminho == "/api/exemplo":
            try: pgn = await http_get(js.SITE_BASE + "teste.pgn")
            except Exception: pgn = ""
            return _ok({"pgn": pgn, "titulo": "demonstração"})
        if caminho == "/api/relatorio":
            job = JOBS.get(body.get("id"))
            if not job: return _ok({"erro": T("rel.sem")})
            set_lang(job["lang"])
            return _ok(relatorio.montar(job))
        if caminho == "/api/partida":
            try: return _ok(await partida(body["fonte"]))
            except Exception as e: return _ok({"erro": str(e)})
        if caminho == "/api/job" and metodo == "POST":
            for j in JOBS.values(): j["parar"] = True
            js.sfParar()
            job = novo_job(body["fonte"], int(body.get("depth", 14)), body.get("lang", lang or "pt"))
            return _ok({"id": job["id"]})
        if caminho == "/api/job":
            job = JOBS.get(q.get("id"))
            if not job: return _ok({"erro": "job inexistente"}, 404)
            desde = max(0, int(q.get("desde", 0)) - 1); v = int(q.get("v", -1))
            mudadas = [r for r in job["rows"][:desde] if r.get("_v", 0) > v] if v >= 0 else []
            return _ok(dict(estado=job["estado"], aviso=job["aviso"], info=job["info"], engines=job["engines"], total=len(job["rows"]),
                            versao=job["versao"], desde=desde, rows=job["rows"][desde:], mudadas=mudadas, lances=job["lances"],
                            esperado=job["esperado"], fens=job["fens"], ucis=job["ucis"], aberturas=job.get("aberturas") or [],
                            numeros=precisao.numeros(job["rows"], job.get("raws"), len(job["lances"])),
                            atual=job["atual"], decorrido=(None if job["atual"] is None else round(time.time() - job["atual_ini"], 1))))
        if caminho == "/api/parar":
            job = JOBS.get(body.get("id"))
            if job: job["parar"] = True
            js.sfParar()
            return _ok({"ok": True})
        if caminho == "/api/idioma":
            job = JOBS.get(body.get("id"))
            if job: traduz_job(job, body.get("lang", "pt"))
            return _ok({"ok": True})
        if caminho == "/api/variante":
            b = chess.Board(q["fen"]); fens, ucis = [b.fen()], []
            for san in [s for s in q.get("pv", "").split(",") if s]:
                m = b.parse_san(san); ucis.append(m.uci()); b.push(m); fens.append(b.fen())
            return _ok({"fens": fens, "ucis": ucis})
        if caminho == "/api/destaque":
            return _ok(destaques_posicao(chess.Board(q["fen"]), q.get("item", "")))
        if caminho == "/api/transmissoes":
            d = json.loads(await http_get("https://lichess.org/api/broadcast/top?page=1"))
            if q.get("q"):
                d = {"active": json.loads(await http_get("https://lichess.org/api/broadcast/search?q=" + urllib.parse.quote(q["q"])))["currentPageResults"], "past": []}
            else:
                d = {"active": d["active"], "past": d["past"][:12] if isinstance(d["past"], list) else d["past"].get("currentPageResults", [])[:12]}
            lst = lambda L: [dict(id=x["tour"]["id"], nome=x["tour"]["name"], tier=x["tour"].get("tier")) for x in L]
            return _ok({"ao_vivo": lst(d["active"]), "recentes": lst(d["past"])})
        if caminho == "/api/transmissao":
            d = json.loads(await http_get(f"https://lichess.org/api/broadcast/{q['id']}"))
            return _ok([dict(id=r["id"], nome=r["name"], ao_vivo=bool(r.get("ongoing")), finalizada=bool(r.get("finished")), inicio=r.get("startsAt")) for r in d["rounds"]])
        if caminho == "/api/rodada":
            gs = parse_jogos(await http_get(f"https://lichess.org/api/broadcast/round/{q['id']}.pgn"))
            return _ok([dict(i=i, brancas=g.headers.get("White"), pretas=g.headers.get("Black"), res=g.headers.get("Result"),
                             elo_b=g.headers.get("WhiteElo"), elo_p=g.headers.get("BlackElo"), lances=sum(1 for _ in g.mainline_moves())) for i, g in enumerate(gs)])
        return _ok({"erro": "não encontrado"}, 404)
    except Exception as e:
        return _ok({"erro": f"{type(e).__name__}: {e}"}, 500)
