"""Escolhe a partida que o programa abre sozinho: a que está ao vivo, ou a mais recente, nos torneios mais importantes
das transmissões do Lichess.

A importância é a "tier" que o próprio Lichess dá a cada transmissão (5 = a mais alta). Do nível mais alto para o mais
baixo: primeiro uma rodada em andamento; se não houver, a rodada mais recente que já começou. Dentro da rodada, vale a
primeira mesa ainda em andamento (ou a primeira com lances).
Serve à versão local e à online: quem chama passa a função assíncrona `get(url) -> texto`.
"""
import io, json, time
import chess.pgn

BASE = "https://lichess.org/api/broadcast"


def escolhe_na_rodada(pgn_texto, em_andamento):
    """-> (índice do jogo, ao_vivo) ou None. Rodada em andamento: primeira partida sem resultado (mesmo ainda sem lances)."""
    fh, jogos = io.StringIO(pgn_texto), []
    while len(jogos) < 40 and (g := chess.pgn.read_game(fh)):
        jogos.append((g.headers.get("Result", "*"), next(iter(g.mainline_moves()), None) is not None))
    if em_andamento:
        abertas = [i for i, (res, _) in enumerate(jogos) if res == "*"]
        com_lances = [i for i in abertas if jogos[i][1]]
        if abertas: return (com_lances or abertas)[0], True
    for i, (res, tem) in enumerate(jogos):
        if tem: return i, res == "*"
    return None


async def escolhe(get, agora_ms=None, max_pedidos=10):
    """-> dict(fonte=..., titulo=..., ao_vivo=bool) ou {} se nada foi encontrado."""
    agora = agora_ms or time.time() * 1000
    pedidos = [0]

    async def pede(url):
        pedidos[0] += 1
        if pedidos[0] > max_pedidos: raise TimeoutError("muitos pedidos")
        return await get(url)

    async def tenta(tour, rodada, em_andamento):
        try:
            r = escolhe_na_rodada(await pede(f"{BASE}/round/{rodada['id']}.pgn"), em_andamento)
        except TimeoutError: raise
        except Exception: return None
        if r is None: return None
        i, vivo = r
        return dict(fonte=dict(tipo="rodada", round=rodada["id"], jogo=i, ao_vivo=vivo),
                    titulo=f"{tour.get('name', '')} · {rodada.get('name', '')}", ao_vivo=vivo)

    try:
        top = json.loads(await pede(f"{BASE}/top?page=1"))
        ativos = top.get("active") or []
        passados = top.get("past") or []
        if isinstance(passados, dict): passados = passados.get("currentPageResults") or []
        niveis = sorted({x["tour"].get("tier") or 0 for x in ativos + passados}, reverse=True)
        for nivel in niveis:
            do_nivel = [x for x in ativos if (x["tour"].get("tier") or 0) == nivel]
            # 1) ao vivo neste nível (na ordem de destaque do Lichess)
            for x in do_nivel:
                rd = x.get("round") or {}
                if rd.get("ongoing"):
                    r = await tenta(x["tour"], rd, True)
                    if r: return r
            # 2) a rodada mais recente que já começou neste nível
            candidatos = []
            for x in do_nivel + [y for y in passados if (y["tour"].get("tier") or 0) == nivel]:
                rd = x.get("round") or {}
                if rd.get("finished") or (rd.get("startsAt") or agora + 1) <= agora:
                    candidatos.append((rd.get("startsAt") or rd.get("finishedAt") or 0, x["tour"], rd))
                else:                      # a rodada indicada ainda não começou: pega a anterior que já aconteceu
                    try:
                        rodadas = json.loads(await pede(f"{BASE}/{x['tour']['id']}")).get("rounds") or []
                    except TimeoutError: raise
                    except Exception: continue
                    feitas = [q for q in rodadas if q.get("finished") or q.get("ongoing")]
                    if feitas:
                        q = max(feitas, key=lambda z: z.get("startsAt") or 0)
                        candidatos.append((q.get("startsAt") or 0, x["tour"], q))
            for _, tour, rd in sorted(candidatos, key=lambda c: -c[0])[:3]:
                r = await tenta(tour, rd, bool(rd.get("ongoing")))
                if r: return r
    except Exception:
        pass
    return {}
