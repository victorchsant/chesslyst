"""Momento crítico: a posição em que a partida se decide (ou poderia ter se decidido).

Dois casos, ambos tirados só dos números da engine:
- "unico": só um lance resolve a posição (o segundo melhor cede muito) e ele não é óbvio para um jogador do nível;
- "virada": o lance jogado muda o rumo da partida (por exemplo, de vantagem para equilíbrio, ou de equilíbrio para perdido).

Ficam de fora a teoria de abertura, o lance forçado e a posição que já estava decidida.
"""
from __future__ import annotations
import chess
from .core import win_pct
from .explica import _mlance, _notacao, _justifica, _fmt_av
from .i18n import T, num

MIN_GAP = 15      # pontos de chance de vitória entre o melhor lance e o segundo
MIN_PERDA = 15    # pontos que o lance jogado precisa custar para ser uma virada
MAX_ACERTO = 80   # acima disso o lance único é óbvio demais para ser "crítico"


def estado(w_brancas: float) -> int:
    """2 = ganho das brancas, 1 = vantagem, 0 = equilíbrio, -1 e -2 = o mesmo para as pretas."""
    if w_brancas >= 80: return 2
    if w_brancas >= 62: return 1
    if w_brancas > 38: return 0
    return -1 if w_brancas > 20 else -2


def momento_critico(raw: dict, acerto: float):
    """-> dict(tipo, titulo, texto, peso, achou) ou None."""
    linhas = raw.get("linhas") or []
    cands = raw.get("cands") or []
    if raw.get("terminal") or len(linhas) < 1 or not cands: return None
    brancas = raw["side"] == "B"
    w_melhor = win_pct(cands[0][1], cands[0][2])                        # de quem joga
    w_segundo = win_pct(cands[1][1], cands[1][2]) if len(cands) > 1 else None
    gap = (w_melhor - w_segundo) if w_segundo is not None else 0.0
    em_teoria = bool(raw.get("book_games") and raw["book_games"] >= 20)
    unico = (not em_teoria and w_segundo is not None and gap >= MIN_GAP and acerto < MAX_ACERTO
             and w_melhor > 10 and w_segundo < 85)

    jogado, depois, perda = raw.get("jogado"), None, 0.0
    if jogado is not None and raw.get("uci"):
        depois = win_pct(jogado[0], jogado[1])
        perda = max(0.0, w_melhor - depois)
    branco = lambda w: w if brancas else 100 - w
    e_antes = estado(branco(w_melhor))
    e_depois = estado(branco(depois)) if depois is not None else e_antes
    virada = depois is not None and perda >= MIN_PERDA and e_depois != e_antes
    if not (unico or virada): return None

    tab = chess.Board(raw["fen"])
    melhor = linhas[0]
    mv = chess.Move.from_uci(melhor["uci"])
    m_txt = _mlance(tab, mv, melhor["san"])
    a_txt = _fmt_av(melhor["cp"], melhor["mate"])
    just = _justifica(tab, melhor)
    lado = T("w.brancas") if brancas else T("w.pretas")
    achou = None if depois is None else perda <= 3

    jog_txt = av_jog = None
    if depois is not None:
        jm = chess.Move.from_uci(raw["uci"])
        jog_txt = _mlance(tab, jm, raw["move"])
        sinal = 1 if brancas else -1
        cp, mate = jogado
        av_jog = _fmt_av(None if cp is None else cp * sinal, None if mate is None else mate * sinal) if (cp is not None or mate) else None

    frases = []
    if virada:
        frases.append(T("mc.virada", x=jog_txt, de=T(f"mc.e{e_antes}"), para=T(f"mc.e{e_depois}"), a=a_txt, b=av_jog or T("mc.mate_dado")))
        frases.append(T("mc.indicado", m=m_txt, j=(": " + just) if just else ""))
        pv = raw.get("pv_jogado") or []
        if len(pv) >= 2:
            b2 = tab.copy(); b2.push(chess.Move.from_uci(raw["uci"]))
            frases.append(T("pq.resposta", l=_notacao(b2, pv[1:4], 3)))
    else:
        s = linhas[1] if len(linhas) > 1 else None
        if s:
            frases.append(T("mc.unico", m=m_txt, a=a_txt, s=_mlance(tab, chess.Move.from_uci(s["uci"]), s["san"]),
                            sa=_fmt_av(s["cp"], s["mate"]), d=num(gap, 0)))
        if just: frases.append(T("mc.porque", j=just))
        resto = (melhor.get("pv_uci") or [])[1:5]
        if resto:
            b2 = tab.copy(); b2.push(mv)
            frases.append(T("pq.cont", l=_notacao(b2, resto)) + ".")
        if achou: frases.append(T("mc.achou", l=lado))
        elif jog_txt: frases.append(T("mc.jogou", l=lado, x=jog_txt, p=num(perda, 0)))
    peso = 60 + perda if virada else gap * (1 - acerto / 120) + (8 if achou else 0)
    return dict(tipo="virada" if virada else "unico", titulo=T("mc.t_virada" if virada else "mc.t_unico"),
                texto=" ".join(frases), peso=round(peso, 1), achou=achou)
