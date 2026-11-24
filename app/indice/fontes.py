"""Fontes externas (Lichess): explorador de mestres (teoria) e tablebase Syzygy (até 7 peças).
Só a posição (FEN) é enviada. Respostas ficam em cache local (cache_fontes.json)."""
import json, time, urllib.parse, urllib.request
from pathlib import Path

from .caminhos import DADOS
CACHE = DADOS / "cache_fontes.json"
_cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
_last = 0.0
PERSIST = True  # processos paralelos desligam, para não corromper o arquivo
HDR = {"User-Agent": "indice-xadrez-pesquisa"}


def _get(url):
    global _last
    if url in _cache: return _cache[url]
    time.sleep(max(0, 0.6 - (time.time() - _last)))  # educado com a API
    try:
        req = urllib.request.Request(url, headers=HDR)
        data = json.load(urllib.request.urlopen(req, timeout=20))
    except Exception:
        return None
    _last = time.time()
    _cache[url] = data
    if PERSIST: CACHE.write_text(json.dumps(_cache), encoding="utf-8")
    return data


def masters(fen):
    """-> (total de partidas na posição, {san: partidas}) ou (None, {})"""
    d = _get("https://explorer.lichess.ovh/masters?" + urllib.parse.urlencode({"fen": fen, "moves": 12}))
    if not d: return None, {}
    tot = d["white"] + d["draws"] + d["black"]
    return tot, {m["san"]: m["white"] + m["draws"] + m["black"] for m in d["moves"]}


def tablebase(fen):
    """-> dict(result, legal, win_moves, hold_moves) do ponto de vista de quem joga, ou None."""
    d = _get("https://tablebase.lichess.ovh/standard?" + urllib.parse.urlencode({"fen": fen}))
    if not d or d.get("category") in (None, "unknown"): return None
    cat = d["category"]
    res = {"win": "win", "cursed-win": "draw", "draw": "draw", "blessed-loss": "draw", "loss": "loss"}.get(cat)
    if res is None: return None
    mv = d["moves"]  # categoria de cada lance vem do ponto de vista do adversário
    return dict(result=res, legal=len(mv),
                win_moves=sum(1 for m in mv if m["category"] == "loss"),
                hold_moves=sum(1 for m in mv if m["category"] in ("draw", "cursed-win", "blessed-loss")))
