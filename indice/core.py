"""Núcleo do Índice de Chance de Acerto (xadrez padrão) + interpretação.

Python puro, sem dependências: recebe, para uma posição, os lances candidatos
da engine (multi-PV) e a distribuição do modelo humano, e devolve o índice
e uma leitura em português explicando o que ele significa.
"""
from __future__ import annotations
import json, math
from pathlib import Path
from .relogio import fmt as _fmt_t
from .i18n import T, P, pontos, num
from dataclasses import dataclass, field
from typing import List, Optional

EPSILON_WIN = 3.0  # lance "bom" = perde no máximo 3 pontos de win% para o melhor


def _sigmoid(x): return 1 / (1 + math.exp(-x))


def features(idx_bruto, rating, flags):
    """Variáveis da calibração (logística): índice bruto, rating e interações."""
    l = math.log(max(.01, min(.99, idx_bruto / 100)) / (1 - max(.01, min(.99, idx_bruto / 100))))
    z = ((rating or 2200) - 2200) / 400
    return [1.0, l, z, l * z]


def _carrega_cal():
    f = Path(__file__).resolve().parent.parent / "calibracao.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None


CAL = _carrega_cal()


def _carrega_cal_tempo():
    f = Path(__file__).resolve().parent.parent / "calibracao_tempo.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None


CAL_T = _carrega_cal_tempo()   # calibração com tempo do jogador (só retrospectiva)


def win_pct(cp: Optional[float], mate: Optional[int] = None) -> float:
    """Centipeões (ponto de vista de quem joga) -> chance de vitória 0-100."""
    if mate is not None:
        return 100.0 if mate > 0 else 0.0
    return 50 + 50 * (2 / (1 + math.exp(-0.00368208 * cp)) - 1)


@dataclass
class Candidate:
    san: str
    cp: Optional[float] = None      # avaliação após o lance (de quem joga)
    mate: Optional[int] = None      # mate em N (+ a favor de quem joga)
    p_human: float = 0.0            # probabilidade do modelo humano


@dataclass
class Position:
    candidates: List[Candidate]               # ordenados do melhor ao pior
    depth_stable: Optional[int] = None        # profundidade em que o melhor lance estabilizou
    book_games: Optional[int] = None          # nº de partidas de mestres que chegaram a esta posição
    tb_hold_moves: Optional[int] = None       # lances que seguram o empate (tablebase, posição empatada)
    piece_count: int = 32
    tempo_gasto: Optional[float] = None       # segundos gastos no lance (só depois de jogado)
    tempo_restante: Optional[float] = None    # segundos no relógio de quem joga antes de mover
    rating: Optional[int] = None              # rating de quem joga (escolhe a rede Maia e entra na calibração)
    tb_win_moves: Optional[int] = None        # lances que mantêm a vitória (tablebase)
    tb_legal: Optional[int] = None            # total de lances legais
    tb_result: Optional[str] = None           # 'win' | 'draw' | 'loss' (de quem joga)
    endgame_kind: Optional[str] = None        # ex.: 'torre contra torre'
    outras: Optional[list] = None             # melhor lance de cada engine adicional [{nome, san}]
    div_peso: float = 0.0                     # fração que a divergência entre engines reduz o índice


@dataclass
class Reading:
    index: float                  # 0-100
    band: str                     # faixa
    headline: str                 # frase principal
    reasons: List[str] = field(default_factory=list)
    flags: List[str] = field(default_factory=list)
    eval_pct: float = 50.0
    practical: float = 50.0       # pontuação prática esperada 0-100
    index_bruto: float = 0.0      # antes da calibração por rating
    index_tempo: Optional[float] = None   # chance de acerto considerando o tempo gasto (retrospectivo)
    tempo_texto: str = ""


BANDS = [(90, "b1"), (75, "b2"), (50, "b3"), (25, "b4"), (0, "b5")]   # (limite inferior, chave do texto)


def band_of(idx: float):
    for lo, k in BANDS:
        if idx >= lo:
            return T(k + ".n"), T(k + ".d")
    return T("b5.n"), T("b5.d")


def chance_of_hit(pos: Position, eps: float = EPSILON_WIN) -> tuple:
    """Índice base = soma de p_humano dos lances que perdem <= eps de win%."""
    best = pos.candidates[0]
    best_w = win_pct(best.cp, best.mate)
    total_p = sum(c.p_human for c in pos.candidates) or 1.0
    good = [c for c in pos.candidates if best_w - win_pct(c.cp, c.mate) <= eps]
    return 100 * sum(c.p_human for c in good) / total_p, good


def analyse(pos: Position, calibrar: bool = True) -> Reading:
    best = pos.candidates[0]
    best_w = win_pct(best.cp, best.mate)
    base, good = chance_of_hit(pos)
    idx = base
    cap_final = 100.0  # teto por regra para finais técnicos (aplicado após a calibração)
    reasons, flags = [], []
    total_p = sum(c.p_human for c in pos.candidates) or 1.0

    # Teoria de abertura
    if pos.book_games is not None and pos.book_games >= 20:
        idx = max(idx, 85 + 15 * min(1, pos.book_games / 500))
        flags.append("teoria")
        reasons.append(T("r.teoria"))

    # Lance único
    if len(pos.candidates) > 1:
        gap = best_w - win_pct(pos.candidates[1].cp, pos.candidates[1].mate)
        if gap > 15:
            flags.append("lance_unico")
            reasons.append(T("r.unico", san=pos.candidates[1].san))
        elif len(good) == 1 and base < 60:
            reasons.append(T("r.so_um"))

    # Tática curta
    if best.mate is not None and best.mate > 0 and best.mate <= 4:
        flags.append("tatica_curta")
        idx = max(idx, 90)
        reasons.append(T("r.mate", m=best.mate))

    # Profundidade tardia
    if pos.depth_stable is not None and pos.depth_stable >= 30:
        flags.append("contraintuitivo")
        idx *= 0.8
        reasons.append(T("r.contra"))

    # Final técnico / tablebase
    kind = f" ({pos.endgame_kind})" if pos.endgame_kind else ""
    if pos.tb_result == "win" and pos.tb_win_moves is not None and pos.tb_legal:
        frac = pos.tb_win_moves / pos.tb_legal
        if frac <= 0.2:
            flags.append("final_tecnico")
            cap_final = min(cap_final, 100 * frac * 2 + base * 0.3)
            reasons.append(T("r.ft_win", kind=kind, w=pos.tb_win_moves, l=pos.tb_legal, v=P(pos.tb_win_moves, "v.mantem")))
        else:
            reasons.append(T("r.ft_win_n", kind=kind, w=pos.tb_win_moves, l=pos.tb_legal))
    elif pos.tb_result == "draw" and pos.tb_hold_moves is not None and pos.tb_legal:
        frac = pos.tb_hold_moves / pos.tb_legal
        if frac <= 0.2:
            flags.append("final_tecnico")
            cap_final = min(cap_final, 100 * frac * 2 + base * 0.3)
            reasons.append(T("r.ft_draw", kind=kind, h=pos.tb_hold_moves, l=pos.tb_legal, v=P(pos.tb_hold_moves, "v.segura")))
        else:
            reasons.append(T("r.ft_draw_n", kind=kind, h=pos.tb_hold_moves, l=pos.tb_legal, v=P(pos.tb_hold_moves, "v.segura")))

    # Lance mais provável dos humanos é um erro
    top_h = max(pos.candidates, key=lambda c: c.p_human)
    loss_h = best_w - win_pct(top_h.cp, top_h.mate)
    if loss_h > 10 and top_h.p_human / total_p > 0.3:
        flags.append("armadilha")
        reasons.append(T("r.arm", san=top_h.san))

    idx = max(0.0, min(100.0, idx))
    bruto = idx
    if calibrar and CAL and "teoria" not in flags:
        idx = 100 * _sigmoid(sum(w * f for w, f in zip(CAL["w"], features(bruto, pos.rating, flags))))   # ajuste por rating: interno, sem texto na tela
    if "final_tecnico" in flags: idx = min(idx, cap_final)
    # divergência entre engines: a engine de referência diz que o lance da outra é pior
    if pos.outras:
        bons = {c.san for c in good}
        div = [o for o in pos.outras if o["san"] not in bons]
        if div:
            flags.append("divergencia")
            lista = "; ".join(T("r.div_item", nome=o["nome"], san=o["san"]) for o in div[:3])
            reasons.append(T("r.div", lista=lista, san=best.san))
            if pos.div_peso > 0: idx *= (1 - pos.div_peso)
        else:
            reasons.append(T("r.conc2") if len(pos.outras) == 1 else T("r.conc", n=len(pos.outras) + 1))
    # leitura retrospectiva com o tempo do jogador (não altera o índice acima nem a avaliação da engine)
    index_tempo, tempo_texto = None, ""
    if pos.tempo_restante is not None:
        tempo_texto = T("r.clock", t=_fmt_t(pos.tempo_restante)) + (T("r.pouco") if pos.tempo_restante < 300 else "")
        if calibrar and CAL_T and pos.tempo_gasto is not None and "teoria" not in flags:
            b4 = features(bruto, pos.rating, flags)
            x = b4 + [math.log1p(pos.tempo_gasto) / 8, math.log1p(pos.tempo_restante) / 8, float(pos.tempo_restante < 300)]
            it = 100 * _sigmoid(sum(w * f for w, f in zip(CAL_T["w"], x)))
            if "final_tecnico" in flags: it = min(it, cap_final)
            if "divergencia" in flags and pos.div_peso > 0: it *= (1 - pos.div_peso)
            index_tempo = it
            tempo_texto = T("r.gasto", g=_fmt_t(pos.tempo_gasto), r=_fmt_t(pos.tempo_restante), it=f"{it:.0f}", i=f"{idx:.0f}")
    band, desc = band_of(idx)
    practical = 50 + (best_w - 50) * (idx / 100)  # puxa a vantagem para 50% quando é difícil converter

    # Frase principal: cruza avaliação x dificuldade
    d = desc[:1].lower() + desc[1:]
    if best_w >= 75 and idx < 50: head = T("h.vant_dif", d=d)
    elif best_w >= 75: head = T("h.vant", d=d)
    elif best_w <= 25: head = T("h.ruim", d=d)
    elif best_w >= 60: head = T("h.melhor", d=d)
    elif best_w <= 40: head = T("h.pior", d=d)
    else: head = T("h.eq", d=d)
    reasons.insert(0, f"{band}: {desc}.")
    return Reading(idx, band, head, reasons, flags, best_w, practical, bruto, index_tempo, tempo_texto)


def line_index(indices: List[float]) -> float:
    """Chance de achar todos os lances do lado forte numa linha (produto)."""
    p = 1.0
    for i in indices:
        p *= i / 100
    return 100 * p


JOGADA_CLASSES = [  # (perda máxima em win%, id da classe)
    (0.5, "melhor"), (2, "excelente"), (5, "bom"), (10, "imprecisao"), (20, "erro"), (101, "grave"),
]


def nome_classe(cid: str) -> str:
    return T("c." + cid)


def indice_jogada(perda: float, acerto: float, eval_antes: float, eval_depois: float):
    """Índice de Jogada 0-100: qualidade do lance realmente jogado.
    perda = win% que o lance jogou fora em relação ao melhor; acerto = índice de chance de acerto
    da posição onde foi jogado; eval_* = win% de quem jogou antes/depois do lance.
    Devolve (nota, id da classe, texto)."""
    perda = max(0.0, perda)
    nota = max(0.0, min(100.0, 103.1668 * math.exp(-0.04354 * perda) - 3.1669))
    cid = next(n for lim, n in JOGADA_CLASSES if perda <= lim)
    if perda <= 1 and acerto <= 30:
        cid = "brilhante"
        nota = max(nota, 95)
        txt = T("j.brilhante", a=f"{acerto:.0f}")
    elif perda <= 0.5:
        txt = T("j.melhor")
    elif perda <= 5:
        txt = T("j.pouca", c=nome_classe(cid), p=num(perda, 1), u=pontos(perda))
    else:
        txt = T("j.muita", c=nome_classe(cid), p=f"{perda:.0f}")
        if eval_antes >= 90 and eval_depois < 60: txt += T("j.escapar")
        elif eval_antes >= 40 and eval_depois < 15: txt += T("j.perdida")
        txt += "."
        if acerto >= 75: txt += T("j.facil")
    return nota, cid, txt
