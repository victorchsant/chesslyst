"""Relógios do PGN ([%clk]): tempo restante antes de jogar e tempo gasto em cada lance."""
from __future__ import annotations
import json
import re


def incremento(headers) -> int:
    tc = headers.get("TimeControl", "") or ""
    m = re.search(r"\+\s*(\d+)\s*$", tc) or re.search(r"increment of (\d+)", tc) or re.search(r"(\d+) seconds? incr", tc)
    return int(m.group(1)) if m else 0


def tempo_inicial(headers):
    """Tempo inicial em segundos (None se não der para saber)."""
    tc = headers.get("TimeControl", "") or ""
    m = re.match(r"^\s*\d+/(\d+)", tc) or re.match(r"^\s*(\d+)\s*(?:\+|$)", tc)
    if not m: return None
    v = int(m.group(1))
    return v * 60 if v <= 300 and "/" not in tc else v    # "90+30" = minutos; "3600+30" = segundos


def tempos_do_jogo(game):
    """Para cada posição i (antes do lance i): dict(restante, gasto). `gasto` é None se o lance ainda não foi jogado
    ou o relógio não existe; `restante` = tempo de quem joga antes de mover."""
    h = game.headers
    inc, ini = incremento(h), tempo_inicial(h)
    clks = [n.clock() for n in game.mainline()]
    out = []
    for i in range(len(clks) + 1):
        anterior = clks[i - 2] if i >= 2 else ini
        gasto = None
        if i < len(clks) and clks[i] is not None and anterior is not None:
            gasto = max(0.0, anterior + inc - clks[i])
        out.append(dict(restante=anterior, gasto=gasto))
    return out


def url_ao_vivo(rodada):
    """Endereço dos dados atuais de uma rodada de transmissão do Lichess ("" se o código não for válido)."""
    return f"https://lichess.org/api/broadcast/-/-/{rodada}" if re.fullmatch(r"[A-Za-z0-9]{8}", rodada or "") else ""


def ao_vivo(texto, brancas, pretas) -> dict:
    """Relógios atuais da partida, a partir dos dados da rodada. -> {} se não houver, ou dict(fen, vez, B, P, corre):
    B e P = segundos no relógio de cada lado após o seu último lance; `corre` = há quantos segundos saiu o último lance,
    tempo que ainda não foi descontado de quem tem a vez (None se o relógio não está correndo ou não se sabe)."""
    for g in json.loads(texto).get("games") or []:
        js = g.get("players") or []
        if [j.get("name") for j in js] != [brancas, pretas]: continue
        campos = (g.get("fen") or "").split()
        if len(campos) < 2 or any(j.get("clock") is None for j in js): return {}
        corre = g.get("thinkTime") if g.get("status") == "*" else None
        return dict(fen=" ".join(campos[:2]), vez="B" if campos[1] == "w" else "P",
                    B=js[0]["clock"] / 100, P=js[1]["clock"] / 100, corre=corre)    # o Lichess dá em centésimos
    return {}


def fmt(seg):
    if seg is None: return "?"
    seg = int(round(seg))
    h, r = divmod(seg, 3600); m, s = divmod(r, 60)
    return f"{h}h{m:02d}min" if h else (f"{m}min{s:02d}s" if m else f"{s}s")
