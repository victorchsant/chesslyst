"""Precisão dos jogadores e os números fundamentais da partida.

Precisão (0-100), pelo método usado pelo Lichess:
 1. cada lance recebe uma nota conforme os pontos de chance de vitória que perdeu em relação ao melhor lance
    (perdeu nada = 100; a nota cai exponencialmente com a perda);
 2. a precisão é a média entre duas médias dessas notas: a ponderada pela oscilação da avaliação naquele trecho
    (lances em momentos agitados pesam mais) e a harmônica (os lances ruins pesam mais).
A engine e a profundidade são as daqui, então o número pode diferir um pouco do que o Lichess mostra.
"""
from __future__ import annotations
import math
import chess

LIMITE_CP = 1000          # perda em centipeões: avaliações (e mates) são limitadas a ±10 peões
CLASSES = ["brilhante", "melhor", "excelente", "bom", "imprecisao", "erro", "grave"]


def nota_lance(perda: float) -> float:
    if perda <= 0: return 100.0
    return max(0.0, min(100.0, 103.1668100711649 * math.exp(-0.04354415386753951 * perda) - 3.166924740191411 + 1))


def _pesos(win_brancas: list, n_lances: int) -> list:
    """Peso de cada lance = quanto a avaliação oscilava no trecho (desvio padrão, entre 0,5 e 12)."""
    if not n_lances: return []
    tam = max(2, min(8, n_lances // 10))
    janelas = [win_brancas[:tam]] * max(0, min(tam, len(win_brancas)) - 2)
    janelas += [win_brancas[k:k + tam] for k in range(max(0, len(win_brancas) - tam + 1))]
    out = []
    for j in janelas:
        if not j: out.append(0.5); continue
        m = sum(j) / len(j)
        out.append(max(0.5, min(12.0, math.sqrt(sum((x - m) ** 2 for x in j) / len(j)))))
    out = out or [0.5]
    return (out + [out[-1]] * n_lances)[:n_lances]


def precisao(notas_pesos: list):
    """[(nota, peso)] -> precisão 0-100 (ou None sem lances)."""
    if not notas_pesos: return None
    ponderada = sum(a * w for a, w in notas_pesos) / sum(w for _, w in notas_pesos)
    harmonica = len(notas_pesos) / sum(1 / max(a, 1.0) for a, _ in notas_pesos)
    return round((ponderada + harmonica) / 2, 1)


def _cp(cp, mate):
    if mate is not None: return LIMITE_CP if mate > 0 else -LIMITE_CP
    return max(-LIMITE_CP, min(LIMITE_CP, cp or 0))


def _rotulo(r):
    b = chess.Board(r["fen"])
    return f"{b.fullmove_number}{'.' if b.turn else '…'}{r['move']}"


def numeros(rows: list, raws: list, total_lances: int = 0):
    """-> dict(B=..., P=..., partida=...) com os números da análise feita até agora (ou None sem lance analisado)."""
    n = min(len(rows), len(raws or []))
    rows, raws = rows[:n], raws[:n]
    jogados = [i for i, r in enumerate(rows) if r.get("move") and r.get("jogado_perda") is not None]
    if not jogados: return None
    pesos = _pesos([r["engine_brancas"] for r in rows], max(jogados) + 1)
    out = {}
    for lado in ("B", "P"):
        meus = [i for i in jogados if rows[i]["side"] == lado]
        perdas_cp, melhores = [], 0
        for i in meus:
            raw = raws[i]
            if raw.get("cands") and raw.get("jogado"):
                perdas_cp.append(max(0, _cp(*raw["cands"][0][1:3]) - _cp(*raw["jogado"])))
                melhores += raw["cands"][0][0] == rows[i]["move"]
        crit = [r for r in rows if r["side"] == lado and r.get("critico")]
        pior = max(meus, key=lambda i: rows[i]["jogado_perda"], default=None)
        tempos = [rows[i]["tempo_gasto"] for i in meus if rows[i].get("tempo_gasto") is not None]
        out[lado] = dict(
            lances=len(meus),
            precisao=precisao([(nota_lance(rows[i]["jogado_perda"]), pesos[i]) for i in meus]),
            perda_cp=round(sum(perdas_cp) / len(perdas_cp)) if perdas_cp else None,
            melhor_pct=round(100 * melhores / len(perdas_cp)) if perdas_cp else None,
            acerto=round(sum(rows[i]["indice"] for i in meus) / len(meus)) if meus else None,
            contagem={c: sum(1 for i in meus if rows[i].get("jogada_classe_id") == c) for c in CLASSES},
            criticos=len(crit), achados=sum(1 for r in crit if r["critico"].get("achou")),
            pior=(dict(lance=_rotulo(rows[pior]), perda=round(rows[pior]["jogado_perda"])) if pior is not None and rows[pior]["jogado_perda"] >= 5 else None),
            tempo_medio=round(sum(tempos) / len(tempos)) if tempos else None)
    teoria = [r for r in rows if r.get("teoria_partidas") and r["teoria_partidas"] >= 20]
    out["partida"] = dict(
        analisados=len(jogados), total=total_lances or len(jogados),
        lances=chess.Board(rows[max(jogados)]["fen"]).fullmove_number,
        teoria_ate=chess.Board(teoria[-1]["fen"]).fullmove_number if teoria else None,
        viradas=sum(1 for r in rows if r.get("critico") and r["critico"]["tipo"] == "virada"),
        criticos=sum(1 for r in rows if r.get("critico")))
    return out
