"""Memória das análises: o que já foi calculado de cada partida é salvo posição a posição e reaproveitado ao reabrir.

- Partidas comuns: um arquivo só (cache_analises.json) com as mais recentes.
- Campeonato Mundial: cada partida tem o seu arquivo na pasta analises_mundial/, que nunca é descartado.

A análise é identificada pela PARTIDA (endereço dela no Lichess ou, sem isso, jogadores, evento, data e rodada),
pela profundidade e pelas engines usadas. A posição inicial sozinha não serve: é igual em quase todas as partidas.
"""
import hashlib, json, os, re, threading

CACHE_MAX = 10                       # análises de partidas comuns guardadas (as mais recentes)
MUNDIAL = re.compile(r"\bworld (chess )?championship\b", re.I)


def _md5(txt):
    return hashlib.md5(txt.encode("utf-8")).hexdigest()


def _val(headers, nome):
    v = (headers.get(nome) or "").strip()
    return "" if re.fullmatch(r"[?.\-*]*", v) else v


def id_partida(headers, ucis):
    """Identificação estável da partida: não muda enquanto ela está em andamento."""
    url = _val(headers, "GameURL")
    if url: return url
    site = _val(headers, "Site")
    if "lichess.org/" in site: return site
    dados = [_val(headers, k) for k in ("White", "Black", "Event", "Date", "Round")]
    if any(dados): return "|".join(dados)
    return "lances:" + " ".join(ucis)        # PGN sem cabeçalho nenhum


def chave(depth, config_engines, headers, fen0, ucis):
    assin = json.dumps(config_engines, sort_keys=True, default=str)
    return f"{depth}|{_md5(assin)}|{_md5(id_partida(headers, ucis) + '|' + fen0)}"


def eh_mundial(headers):
    return bool(MUNDIAL.search(_val(headers, "BroadcastName") or _val(headers, "Event")))


def nome_arquivo(headers):
    rodada = _val(headers, "Round")
    partes = [_val(headers, "BroadcastName") or _val(headers, "Event"), f"R{rodada}" if rodada else "",
              f"{_val(headers, 'White')} x {_val(headers, 'Black')}"]
    nome = " - ".join(p for p in partes if p)
    return re.sub(r'[\\/:*?"<>|\x00-\x1f]+', "-", nome)[:140].strip(" .-") + ".json"


def _grava(arq, obj):
    """Escreve num arquivo temporário e troca de uma vez: fechar o programa no meio não estraga o que já estava salvo."""
    tmp = arq.with_name(arq.name + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    os.replace(tmp, arq)


def _le(arq):
    try:
        d = json.loads(arq.read_text(encoding="utf-8"))
        if isinstance(d, dict): return d
    except OSError:
        return {}
    except ValueError:
        pass
    try: os.replace(arq, arq.with_name(arq.name + ".corrompido"))   # não escreve por cima de um arquivo ilegível
    except OSError: pass
    return {}


def _mais_completa(salva, nova):
    """A análise a manter: a salva, se a nova for só um começo dela (transmissão que voltou lances, análise interrompida)."""
    if salva and len(nova) < len(salva) and all(a.get("fen") == b.get("fen") for a, b in zip(nova, salva)): return salva
    return nova


class Memoria:
    def __init__(self, dados):
        self.arq = dados / "cache_analises.json"
        self.pasta = dados / "analises_mundial"
        self.lk = threading.RLock()
        self.comuns = _le(self.arq) if self.arq.exists() else {}

    def _mundial(self, headers):
        arq = self.pasta / nome_arquivo(headers)
        return arq, (_le(arq) if arq.exists() else {})

    def _todas(self, headers):
        return self._mundial(headers)[1].get("analises", {}) if eh_mundial(headers) else self.comuns

    def carrega(self, k, headers):
        with self.lk:
            return list(self._todas(headers).get(k) or [])

    def salva(self, k, headers, raws):
        """-> "mundial", "ok", "falhou" ou "" (nada a salvar)."""
        if not raws: return ""
        with self.lk:
            try:
                if eh_mundial(headers):
                    self.pasta.mkdir(parents=True, exist_ok=True)
                    arq, d = self._mundial(headers)
                    analises = d.get("analises", {})
                    analises[k] = _mais_completa(analises.get(k), list(raws))
                    info = {n: headers.get(n, "") for n in ("White", "Black", "WhiteElo", "BlackElo", "Event", "Result", "Date", "Round",
                                                          "BroadcastName", "BroadcastURL", "GameURL")}
                    _grava(arq, {"info": info, "analises": analises})
                    return "mundial"
                lista = _mais_completa(self.comuns.pop(k, None), list(raws))
                self.comuns[k] = lista                                  # vai para o fim: é a mais recente
                while len(self.comuns) > CACHE_MAX: self.comuns.pop(next(iter(self.comuns)))
                _grava(self.arq, self.comuns)
                return "ok"
            except (OSError, TypeError, ValueError):
                return "falhou"

    def resumo(self, config_engines, headers, fens, ucis):
        """Quantas posições desta partida já estão salvas, por profundidade (com as engines atuais)."""
        _, cfg, ident = chave(0, config_engines, headers, fens[0], ucis).split("|")
        out = {}
        with self.lk:
            for k, raws in self._todas(headers).items():
                partes = k.split("|")
                if len(partes) != 3 or partes[1:] != [cfg, ident]: continue
                n = 0
                for r, fen in zip(raws, fens):
                    if r.get("fen") != fen: break
                    n += 1
                if n: out[partes[0]] = n
        return out
