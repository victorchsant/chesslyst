"""Relógios do PGN ([%clk]): tempo restante antes de jogar e tempo gasto em cada lance."""
from __future__ import annotations
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


def fmt(seg):
    if seg is None: return "?"
    seg = int(round(seg))
    h, r = divmod(seg, 3600); m, s = divmod(r, 60)
    return f"{h}h{m:02d}min" if h else (f"{m}min{s:02d}s" if m else f"{s}s")
