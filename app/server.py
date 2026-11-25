"""Servidor local do Chesslyst (http://127.0.0.1:8765): serve a interface web/ e faz a análise.

Fontes de jogo: PGN colado/aberto, partida do Lichess (ID), ou jogo de uma transmissão (rodada),
ao vivo ou não. Só FENs e consultas ao Lichess saem da máquina; o PGN colado não é enviado a ninguém.
"""
import io, json, os, re, sys, threading, time, urllib.parse, urllib.request, uuid
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
import chess, chess.engine, chess.pgn

from indice import pipeline, fontes
from indice.gerente import Gerente
from indice.i18n import set_lang, T
from indice import baixador, relogio
from indice.aberturas import nomes as nomes_abertura
from indice.explica import explicar_subida, texto_repeticao
from indice.posicional import destaques as destaques_posicao
from indice.core import analyse
from indice import inicial

from indice.caminhos import RECURSOS, DADOS
ROOT = RECURSOS                      # interface, exemplos e calibrações (somente leitura)
WEB = ROOT / "web"
PORT = int(sys.argv[sys.argv.index("--porta") + 1]) if "--porta" in sys.argv else 8765   # --porta N: outra porta (desenvolvimento)
UA = {"User-Agent": "indice-xadrez-pesquisa"}
LOCK = threading.Lock()          # uma análise de posição por vez (engines compartilhadas)
JOBS = {}
GER = Gerente()
def _codigo():
    """Carimbo do código em uso (data da última alteração dos .py): o launcher reinicia um servidor mais antigo que os arquivos."""
    try: return max(f.stat().st_mtime for f in [Path(__file__).resolve(), *(Path(__file__).resolve().parent / "indice").glob("*"), *(Path(__file__).resolve().parent / "calibracao").glob("*")] if f.suffix in (".py", ".json"))
    except OSError: return 0.0


CODIGO = _codigo()
MANTER = "--manter" in sys.argv        # não encerrar por ociosidade (desenvolvimento / terminal visível)
PING = {"ultimo": time.time(), "recebeu": False}


def sair():
    try: GER.fecha_tudo()
    finally: os._exit(0)


def vigia():
    """Sem página aberta, o servidor se encerra sozinho (90 s depois do último sinal; 180 s se nunca houve página)."""
    while True:
        time.sleep(5)
        if MANTER: continue
        ocioso = time.time() - PING["ultimo"]
        if (PING["recebeu"] and ocioso > 90) or (not PING["recebeu"] and ocioso > 180): sair()


def http_get(url, texto=True, timeout=30):
    d = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout).read()
    return d.decode("utf-8", "replace") if texto else d


def parse_jogos(pgn_texto):
    jogos, fh = [], io.StringIO(pgn_texto)
    while (g := chess.pgn.read_game(fh)): jogos.append(g)
    return jogos


# ---------------------------------------------------------------- jobs
def obtem_pgn(job):
    f = job["fonte"]
    if f["tipo"] == "pgn":
        return f["pgn"]
    if f["tipo"] == "lichess":
        gid = re.sub(r".*lichess\.org/(?:game/export/)?([A-Za-z0-9]{8}).*", r"\1", f["id"].strip())
        return http_get(f"https://lichess.org/game/export/{gid}?clocks=false&evals=false&opening=false")
    if f["tipo"] == "rodada":
        return http_get(f"https://lichess.org/api/broadcast/round/{f['round']}.pgn")
    raise ValueError("tipo de fonte desconhecido")


def escolhe_jogo(job, pgn_texto):
    jogos = parse_jogos(pgn_texto)
    if not jogos: return None
    f = job["fonte"]
    i = int(f.get("jogo", 0))
    return jogos[i] if 0 <= i < len(jogos) else None


# ---------- memória das análises: pausar e continuar (ou reabrir o programa) não recomeça do zero ----------
CACHE_ARQ = DADOS / "cache_analises.json"
CACHE_MAX = 10                       # partidas guardadas (as mais recentes)
try: ANALISES = json.loads(CACHE_ARQ.read_text(encoding="utf-8"))
except (OSError, ValueError): ANALISES = {}


def chave_analise(depth, fen0):
    """Mesma partida, mesma profundidade e mesmas engines = mesma análise (idioma não conta: o texto é refeito ao mostrar)."""
    import hashlib
    with LOCK: c = GER.cfg
    assin = json.dumps({k: c.get(k) for k in ("engines", "referencia", "humano", "divergencia_peso")}, sort_keys=True, default=str)
    return f"{depth}|{hashlib.md5(assin.encode()).hexdigest()}|{fen0}"


def reaproveita(job, raws, boards, moves, chave):
    """Carrega o que já foi analisado desta partida (a parte que ainda confere com a partida) e devolve o estado de 'em teoria'."""
    antigas = ANALISES.get(chave) or []
    for i, r in enumerate(antigas):
        if i >= len(boards) or r.get("fen") != boards[i].fen(): break
        if r.get("move") is not None and (i >= len(moves) or r.get("uci") != moves[i].uci()): break
        raws.append(r)
    em = True
    for i, r in enumerate(raws):
        if em: em = bool(r.get("book_games") and r["book_games"] >= 20)
        push_row(job, r, i)
    ANALISES.pop(chave, None); ANALISES[chave] = raws          # a lista viva do job é a memória: cresce junto com a análise
    while len(ANALISES) > CACHE_MAX: ANALISES.pop(next(iter(ANALISES)))
    return em


def guarda_analises():
    try: CACHE_ARQ.write_text(json.dumps(ANALISES, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    except (OSError, TypeError, ValueError): pass


def rodar_job(job):
    set_lang(job["lang"])
    depth = int(job["depth"])
    em_livro, raws, rt = True, [], None
    job["raws"] = raws
    try:
        while not job["parar"]:
            try:
                game = escolhe_jogo(job, obtem_pgn(job))
            except Exception as e:
                job["estado"] = "esperando"; job["aviso"] = T("s.fonte", e=e)
                if job["fonte"]["tipo"] == "pgn": raise
                time.sleep(5); continue
            if game is None: raise ValueError(T("s.jogo"))
            h = game.headers
            job["info"] = {k: h.get(k, "") for k in ("White", "Black", "WhiteElo", "BlackElo", "Event", "Result", "Date", "Round", "BroadcastName", "BroadcastURL")}
            rt = pipeline.ratings(game)
            moves = list(game.mainline_moves())
            tempos = relogio.tempos_do_jogo(game)
            board = game.board()
            # confere se o que já foi analisado ainda é um prefixo da partida
            boards = []
            for m in moves: boards.append(board.copy()); board.push(m)
            boards.append(board.copy())  # posição final / atual
            b0, lances = game.board(), []
            for m in moves: lances.append(b0.san(m)); b0.push(m)
            job["lances"], job["esperado"] = lances, len(boards)   # a interface mostra tudo desde já e o progresso
            job["fens"], job["ucis"] = [bb.fen() for bb in boards], [m.uci() for m in moves]
            job["aberturas"] = nomes_abertura(job["fens"])
            if not job.get("_memoria"):                      # primeira volta: aproveita a análise guardada desta partida
                job["_memoria"] = True; job["_chave"] = chave_analise(depth, boards[0].fen())
                if not raws: em_livro = reaproveita(job, raws, boards, moves, job["_chave"])
            if any(i < len(boards) - 1 and raws[i]["fen"] != boards[i].fen() for i in range(min(len(raws), len(boards)))):
                raws.clear(); job["rows"].clear(); em_livro = True
            for i in range(len(raws), len(boards)):
                if job["parar"]: break
                b = boards[i]
                set_lang(job["lang"])   # o idioma pode mudar durante a análise
                job["atual"], job["atual_ini"] = i, time.time()
                lance = moves[i] if i < len(moves) else None
                side = "B" if b.turn else "P"
                if lance is None and b.is_game_over():   # fim de partida: não há o que calcular
                    raw = dict(fen=b.fen(), move=None, terminal=True, rating=rt[side], tempo=tempos[i])
                    raws.append(raw); push_row(job, raw, i); job["atual"] = None
                    continue
                with LOCK:
                    (e_ref, sf), maia, outras = GER.referencia(), GER.maia(), [(e["nome"], eng, er, e.get("tempo", 4)) for e, eng, er in GER.outras()]
                    job["engines"] = dict(referencia=e_ref["nome"], outras=[o[0] for o in outras])
                    raw = pipeline.colher(b, lance, sf, maia, rt[side], depth, 5, em_livro, outras=outras, tempo=tempos[i])
                if em_livro: em_livro = bool(raw["book_games"] and raw["book_games"] >= 20)
                raws.append(raw)
                push_row(job, raw, i)
                job["atual"] = None
                # a posição anterior agora tem lance conhecido? (ao vivo: posição "atual" ganha seu lance)
            # posição atual anterior sem lance que agora tem lance
            for i in range(len(moves)):
                if i < len(raws) and raws[i]["move"] is None:
                    with LOCK:
                        (_, sf) = GER.referencia()
                        b, m = boards[i], moves[i]
                        san = b.san(m)
                        j = next((k for k, (s_, c_, m_) in enumerate(raws[i]["cands"]) if s_ == san), None)
                        if j is not None: jog, pvj = [raws[i]["cands"][j][1], raws[i]["cands"][j][2]], raws[i]["linhas"][j].get("pv_uci")
                        else:
                            r3 = pipeline.avalia_jogado(sf, b, m, depth); jog, pvj = [r3[0], r3[1]], r3[2]
                        raws[i]["tempo"] = tempos[i]
                        raws[i].update(move=san, uci=m.uci(), jogado=jog, pv_jogado=pvj)
                        b2 = b.copy(); b2.push(m); raws[i]["fen_depois"] = b2.fen()
                    push_row(job, raws[i], i)
            if job["parar"]: break   # parado no meio: não marcar como "ao vivo"
            resultado = h.get("Result", "*")
            completo = len(raws) == len(boards) and all(r["move"] is not None for r in raws[:len(moves)])
            ao_vivo = job["fonte"].get("ao_vivo") and job["fonte"]["tipo"] != "pgn"
            if not ao_vivo and completo: break
            if ao_vivo and completo and (resultado != "*" or board.is_game_over()): break
            job["estado"] = "ao vivo"; time.sleep(4)
        job["estado"] = "parado" if job["parar"] else "fim"
    except Exception as e:
        job["estado"] = "erro"; job["aviso"] = repr(e)
    finally:
        guarda_analises()


def _ant(r, extra=""):
    """Resumo do lance jogado em uma linha (mostrado na linha seguinte como 'último lance'); `extra` = a avaliação sobe depois dele."""
    if r is None or r["jogada_indice"] is None: return None
    return dict(lance=r["move"], indice=r["jogada_indice"], classe=r["jogada_classe"], classe_id=r["jogada_classe_id"],
                texto=(r["jogada_texto"] or "") + ((" " + extra) if extra else ""), tempo=r.get("tempo_texto", ""))


def _subida(job, i):
    """Texto de 'a avaliação sobe muito' para o lance que levou à posição i (usa a análise das posições i-1 e i)."""
    raws = job.get("raws") or []
    return explicar_subida(raws[i - 1], raws[i]) if 0 < i < len(raws) else None


def push_row(job, raw, i):
    with job["lk"]:
        set_lang(job["lang"])   # o texto sai sempre no idioma atual do job, mesmo que ele tenha mudado durante o cálculo
        if raw.get("terminal"):
            row = pipeline.linha_final(chess.Board(raw["fen"]), raw.get("rating"), raw.get("tempo"))
        else:
            pos = pipeline.para_posicao(raw, GER.cfg.get("divergencia_peso", 0.0))
            row = pipeline.linha(raw, pos, analyse(pos))
        row["idx"] = i
        row["repeticao_texto"] = texto_repeticao(job.get("fens") or [], job.get("lances") or [], i)   # repetição de lances / xeque perpétuo
        row["ant"] = _ant(job["rows"][i - 1], _subida(job, i) or "") if i > 0 and i - 1 < len(job["rows"]) else None
        if i < len(job["rows"]): job["rows"][i] = row
        else: job["rows"].append(row)
        job["versao"] += 1
        row["_v"] = job["versao"]            # versão em que esta linha mudou: o cliente pede as que mudaram depois do que ele já viu
        if i + 1 < len(job["rows"]):   # a linha seguinte deve mostrar a jogada anterior atualizada
            job["rows"][i + 1]["ant"] = _ant(row, _subida(job, i + 1) or "")
            job["rows"][i + 1]["_v"] = job["versao"]


def traduz_job(job, lang):
    """Troca o idioma de um job: refaz os textos de todas as linhas a partir dos dados brutos (sem consultar a engine)."""
    set_lang(lang)
    job["lang"] = lang
    with job["lk"]:
        for i, raw in enumerate(list(job["raws"])):
            push_row(job, raw, i)


def partida(fonte):
    """Abre uma partida SEM analisar: cabeçalhos, lances (SAN/UCI) e posições (FEN). Rápido, não usa engine."""
    job = {"fonte": fonte}
    game = escolhe_jogo(job, obtem_pgn(job))
    if game is None: raise ValueError(T("s.jogo"))
    h = game.headers; b = game.board(); fens, lances, ucis = [b.fen()], [], []
    for m in game.mainline_moves():
        lances.append(b.san(m)); ucis.append(m.uci()); b.push(m); fens.append(b.fen())
    info = {k: h.get(k, "") for k in ("White", "Black", "WhiteElo", "BlackElo", "Event", "Result", "Date", "Round", "BroadcastName", "BroadcastURL")}
    return dict(info=info, lances=lances, fens=fens, ucis=ucis, aberturas=nomes_abertura(fens))


EXEMPLO = {"pgn": None, "titulo": ""}
EXEMPLO_OK = threading.Event()


INICIAL = {"quando": 0.0, "dados": {}}


def partida_inicial():
    """A partida ao vivo (ou a mais recente) dos torneios mais importantes; guardada por 60 s."""
    if time.time() - INICIAL["quando"] < 60 and INICIAL["dados"]: return INICIAL["dados"]
    import asyncio

    async def get(url): return http_get(url)
    INICIAL.update(quando=time.time(), dados=asyncio.run(inicial.escolhe(get)))
    return INICIAL["dados"]


def acha_exemplo():
    """Procura, no Lichess, uma partida recente e terminada de uma transmissão (roda em segundo plano ao iniciar)."""
    try:
        top = json.loads(http_get("https://lichess.org/api/broadcast/top?page=1"))
        passadas = top.get("past", [])
        if isinstance(passadas, dict): passadas = passadas.get("currentPageResults", [])
        for it in passadas[:8]:
            nome = it["tour"]["name"]
            rodadas = json.loads(http_get(f"https://lichess.org/api/broadcast/{it['tour']['id']}"))["rounds"]
            for r in reversed(rodadas[-3:]):
                for g in parse_jogos(http_get(f"https://lichess.org/api/broadcast/round/{r['id']}.pgn")):
                    h = g.headers
                    if h.get("Result", "*") == "*" or not h.get("WhiteElo", "").isdigit(): continue
                    if sum(1 for _ in g.mainline_moves()) < 30: continue
                    EXEMPLO.update(pgn=str(g), titulo=f"{nome} · {r['name']}")
                    return
    except Exception:
        pass
    finally:
        EXEMPLO_OK.set()


def novo_job(fonte, depth, lang="pt"):
    jid = uuid.uuid4().hex[:8]
    job = dict(id=jid, fonte=fonte, depth=depth, rows=[], estado="analisando", aviso="", info={}, parar=False, versao=0, engines={}, lances=[], esperado=0, atual=None, atual_ini=0.0, fens=[], ucis=[],
               lang=lang, lk=threading.RLock(), raws=[])
    JOBS[jid] = job
    threading.Thread(target=rodar_job, args=(job,), daemon=True).start()
    return job


# ---------------------------------------------------------------- HTTP
MIME = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
        ".json": "application/json", ".svg": "image/svg+xml", ".png": "image/png"}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def json(self, obj, code=200):
        d = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code); self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(d))); self.send_header("Cache-Control", "no-store"); self.end_headers()
        self.wfile.write(d)

    def local(self):
        """Recusa pedidos de outros sites (DNS rebinding / CSRF): o servidor executa engines cadastradas."""
        ok = {f"127.0.0.1:{PORT}", f"localhost:{PORT}"}
        o = self.headers.get("Origin")
        if self.headers.get("Host") not in ok or (o and o.split("://", 1)[-1] not in ok):
            self.json({"erro": "origem não permitida"}, 403); return False
        return True

    def do_GET(self):
        if not self.local(): return
        set_lang(self.headers.get("X-Lang"))
        u = urllib.parse.urlparse(self.path); q = {k: v[0] for k, v in urllib.parse.parse_qs(u.query).items()}
        try:
            if u.path == "/api/transmissoes":
                d = json.loads(http_get("https://lichess.org/api/broadcast/top?page=1"))
                if q.get("q"): d = {"active": json.loads(http_get("https://lichess.org/api/broadcast/search?q=" + urllib.parse.quote(q["q"])))["currentPageResults"], "past": []}
                else: d = {"active": d["active"], "past": d["past"][:12] if isinstance(d["past"], list) else d["past"].get("currentPageResults", [])[:12]}
                lst = lambda L: [dict(id=x["tour"]["id"], nome=x["tour"]["name"], tier=x["tour"].get("tier")) for x in L]
                return self.json({"ao_vivo": lst(d["active"]), "recentes": lst(d["past"])})
            if u.path == "/api/transmissao":
                d = json.loads(http_get(f"https://lichess.org/api/broadcast/{q['id']}"))
                return self.json([dict(id=r["id"], nome=r["name"], ao_vivo=bool(r.get("ongoing")), finalizada=bool(r.get("finished")), inicio=r.get("startsAt"))
                                  for r in d["rounds"]])
            if u.path == "/api/rodada":
                gs = parse_jogos(http_get(f"https://lichess.org/api/broadcast/round/{q['id']}.pgn"))
                return self.json([dict(i=i, brancas=g.headers.get("White"), pretas=g.headers.get("Black"), res=g.headers.get("Result"),
                                       elo_b=g.headers.get("WhiteElo"), elo_p=g.headers.get("BlackElo"),
                                       lances=sum(1 for _ in g.mainline_moves())) for i, g in enumerate(gs)])
            if u.path == "/api/variante":
                try:
                    b = chess.Board(q["fen"]); fens, ucis = [b.fen()], []
                    for san in [s for s in q.get("pv", "").split(",") if s]:
                        m = b.parse_san(san); ucis.append(m.uci()); b.push(m); fens.append(b.fen())
                    return self.json({"fens": fens, "ucis": ucis})
                except Exception as e:
                    return self.json({"erro": str(e)}, 400)
            if u.path == "/api/inicial":
                return self.json(partida_inicial())
            if u.path == "/api/exemplo":
                EXEMPLO_OK.wait(10)
                if EXEMPLO["pgn"]: return self.json(EXEMPLO)
                f = ROOT / "exemplos" / "teste.pgn"   # sem internet: partida de demonstração incluída
                return self.json({"pgn": f.read_text(encoding="utf-8") if f.exists() else "", "titulo": "demonstração"})
            if u.path == "/api/destaque":      # casas/setas a marcar no tabuleiro para um item do Índice de Posição
                try: return self.json(destaques_posicao(chess.Board(q["fen"]), q.get("item", "")))
                except Exception as e: return self.json({"erro": str(e)}, 400)
            if u.path == "/api/codigo":
                return self.json({"codigo": CODIGO})
            if u.path == "/api/ping":
                PING["ultimo"], PING["recebeu"] = time.time(), True
                return self.json({"ok": True})
            if u.path == "/api/engines":
                return self.json(GER.cfg)
            if u.path == "/api/baixaveis":
                return self.json(baixador.catalogo())
            if u.path == "/api/baixar/estado":
                est = {k: dict(v) for k, v in baixador.ESTADOS.items()}
                for k, v in est.items():
                    if v.get("estado") == "ok" and not v.get("registrado"):
                        v["registrado"] = baixador.ESTADOS[k]["registrado"] = True
                        exe = baixador.instalado(k)
                        if exe and k in ("stockfish", "lc0"): GER.registra_baixada(k, exe)
                return self.json(est)
            if u.path == "/api/job":
                job = JOBS.get(q.get("id"))
                if not job: return self.json({"erro": "job inexistente"}, 404)
                desde = max(0, int(q.get("desde", 0)) - 1)
                v = int(q.get("v", -1))
                mudadas = [r for r in job["rows"][:desde] if r.get("_v", 0) > v] if v >= 0 else []   # linhas já enviadas que mudaram (ex.: lance ao vivo que acabou de ser analisado)
                return self.json(dict(estado=job["estado"], aviso=job["aviso"], info=job["info"], engines=job["engines"], total=len(job["rows"]),
                                      versao=job["versao"], desde=desde, rows=job["rows"][desde:], mudadas=mudadas, lances=job["lances"], esperado=job["esperado"], fens=job["fens"], ucis=job["ucis"], aberturas=job.get("aberturas") or [],
                                      atual=job["atual"], decorrido=(None if job["atual"] is None else round(time.time() - job["atual_ini"], 1))))
            # estáticos
            p = "index.html" if u.path in ("/", "") else u.path.lstrip("/")
            f = (WEB / p).resolve()
            if WEB.resolve() not in f.parents or not f.is_file(): return self.json({"erro": "não encontrado"}, 404)
            d = f.read_bytes()
            self.send_response(200); self.send_header("Content-Type", MIME.get(f.suffix, "application/octet-stream"))
            self.send_header("Content-Length", str(len(d))); self.send_header("Cache-Control", "no-store"); self.end_headers()
            self.wfile.write(d)
        except Exception as e:
            self.json({"erro": repr(e)}, 500)

    def do_POST(self):
        if not self.local(): return
        set_lang(self.headers.get("X-Lang"))
        n = int(self.headers.get("Content-Length", 0)); body = json.loads(self.rfile.read(n) or b"{}")
        u = urllib.parse.urlparse(self.path)
        if u.path == "/api/job":
            for j in JOBS.values():  # um job ativo por vez: encerra os anteriores
                j["parar"] = True
            job = novo_job(body["fonte"], int(body.get("depth", 14)), body.get("lang", "pt"))
            return self.json({"id": job["id"]})
        if u.path == "/api/partida":
            try: return self.json(partida(body["fonte"]))
            except Exception as e: return self.json({"erro": str(e)})
        if u.path == "/api/encerrar":
            threading.Timer(0.5, sair).start()
            return self.json({"ok": True})
        if u.path == "/api/engines":
            try:
                with LOCK: return self.json(GER.salvar(body))
            except Exception as e: return self.json({"erro": str(e)}, 400)
        if u.path == "/api/baixar":
            try: baixador.baixar(body.get("id", "")); return self.json({"ok": True})
            except KeyError: return self.json({"erro": "item desconhecido"}, 400)
        if u.path == "/api/engines/testar":
            return self.json(GER.testar(body.get("caminho", ""), body.get("argumentos", "")))
        if u.path == "/api/idioma":
            j = JOBS.get(body.get("id"))
            if j: traduz_job(j, body.get("lang", "pt"))
            return self.json({"ok": True})
        if u.path == "/api/parar":
            if body.get("id") in JOBS: JOBS[body["id"]]["parar"] = True
            return self.json({"ok": True})
        self.json({"erro": "não encontrado"}, 404)


def servir():
    """Sobe o servidor e fica atendendo (usado por `python server.py` e pelo Chesslyst.exe)."""
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), H)
    print(f"Chesslyst em http://127.0.0.1:{PORT}", flush=True)
    threading.Thread(target=vigia, daemon=True).start()
    threading.Thread(target=acha_exemplo, daemon=True).start()
    try: srv.serve_forever()
    finally: GER.fecha_tudo()


if __name__ == "__main__":
    servir()
