"""Gerenciador de engines: lista de engines UCI do usuário, referência do índice, modelo de jogadores.

Configuração em engines.json. Só executa os programas cadastrados aqui (pelo usuário, localmente).
"""
from __future__ import annotations
import json, shlex, threading
from pathlib import Path
import chess.engine
from . import pipeline
from .i18n import T

from .caminhos import DADOS as ROOT       # engines e engines.json ficam na pasta de dados do usuário
ARQ = ROOT / "engines.json"


def _rel(p: Path) -> str:
    try: return str(p.resolve().relative_to(ROOT)).replace("\\", "/")
    except ValueError: return str(p)


def padrao():
    return {
        "engines": ([{"id": "stockfish", "nome": "Stockfish", "caminho": _rel(pipeline.SF), "argumentos": "",
                      "opcoes": {"Threads": "2", "Hash": "128"}, "ativa": True, "tempo": 4}] if pipeline.SF else []),
        "referencia": "stockfish" if pipeline.SF else "",
        "humano": {"modo": "maia", "lc0": _rel(pipeline.LC0), "pesos": "", "argumentos": ""},
        "divergencia_peso": 0.0,   # 0 = divergência só aparece na leitura; >0 reduz o índice nessa fração
    }


def resolve(c: str) -> Path:
    p = Path(c)
    return p if p.is_absolute() else ROOT / p


def args_abs(texto: str):
    """Divide os argumentos e torna absolutos os valores que são arquivos relativos à pasta do projeto."""
    if not texto: return []
    out = []
    for tok in shlex.split(texto, posix=False):
        chave, sep, val = tok.partition("=")
        cand = (val if sep else tok).strip('"')
        if cand and not Path(cand).is_absolute() and (ROOT / cand).exists():
            cand = str(ROOT / cand)
            tok = chave + sep + cand if sep else cand
        out.append(tok)
    return out


class Gerente:
    def __init__(self):
        self.lock = threading.RLock()
        self.vivas = {}      # id -> (assinatura, SimpleEngine)
        self.maia_obj = None; self.maia_sig = None
        self.cfg = json.loads(ARQ.read_text(encoding="utf-8")) if ARQ.exists() else padrao()
        base = padrao()
        for k, v in base.items(): self.cfg.setdefault(k, v)

    # ---------- configuração
    def salvar(self, cfg):
        ids = set()
        eng = []
        for e in cfg.get("engines", []):
            i = "".join(c for c in (e.get("id") or e.get("nome", "")).lower() if c.isalnum() or c in "-_") or "engine"
            while i in ids: i += "x"
            ids.add(i)
            eng.append({"id": i, "nome": (e.get("nome") or i)[:60], "caminho": e.get("caminho", "").strip().strip('"'),
                        "argumentos": e.get("argumentos", "").strip(),
                        "opcoes": {str(k): str(v) for k, v in (e.get("opcoes") or {}).items()},
                        "ativa": bool(e.get("ativa", True)),
                        "tempo": max(0.5, min(60.0, float(e.get("tempo") or 4)))})
        ref = cfg.get("referencia")
        if ref not in ids: ref = next((e["id"] for e in eng if e["ativa"]), eng[0]["id"] if eng else "")
        for e in eng:
            if e["id"] == ref: e["ativa"] = True
        h = cfg.get("humano") or {}
        novo = {"engines": eng, "referencia": ref,
                "humano": {"modo": "custom" if h.get("modo") == "custom" else "maia", "lc0": (h.get("lc0") or _rel(pipeline.LC0)).strip().strip('"'),
                           "pesos": (h.get("pesos") or "").strip().strip('"'), "argumentos": (h.get("argumentos") or "").strip()},
                "divergencia_peso": max(0.0, min(0.5, float(cfg.get("divergencia_peso") or 0)))}
        with self.lock:
            self.cfg = novo
            ARQ.write_text(json.dumps(novo, ensure_ascii=False, indent=1), encoding="utf-8")
            self.fecha_engines()
        return novo

    # ---------- registro após download
    def registra_baixada(self, item_id, exe):
        """Depois de baixar uma engine, inclui-a na configuração."""
        with self.lock:
            c = json.loads(json.dumps(self.cfg))
            if item_id == "stockfish" and not any(e["id"] == "stockfish" for e in c["engines"]):
                c["engines"].insert(0, {"id": "stockfish", "nome": "Stockfish", "caminho": _rel(Path(exe)), "argumentos": "",
                                         "opcoes": {"Threads": "2", "Hash": "128"}, "ativa": True, "tempo": 4})
            if item_id == "stockfish" and not c.get("referencia"): c["referencia"] = "stockfish"
            if item_id == "lc0": c["humano"]["lc0"] = _rel(Path(exe))
            self.salvar(c)

    # ---------- processos
    def _abre(self, e):
        exe = resolve(e["caminho"])
        if not exe.is_file(): raise FileNotFoundError(f"executável não encontrado: {exe}")
        cmd = [str(exe)] + args_abs(e["argumentos"])
        eng = chess.engine.SimpleEngine.popen_uci(cmd, cwd=str(exe.parent), timeout=60)
        cfg = {}
        for k, v in e["opcoes"].items():
            o = eng.options.get(k)
            if o is None: continue
            if o.type == "spin": cfg[k] = int(float(v))
            elif o.type == "check": cfg[k] = str(v).lower() in ("1", "true", "sim", "on")
            elif o.type != "button": cfg[k] = v
        if cfg: eng.configure(cfg)
        return eng

    def engine(self, e):
        sig = json.dumps(e, sort_keys=True)
        with self.lock:
            viva = self.vivas.get(e["id"])
            if viva and viva[0] == sig: return viva[1]
            if viva:
                try: viva[1].quit()
                except Exception: pass
            eng = self._abre(e)
            self.vivas[e["id"]] = (sig, eng)
            return eng

    def referencia(self):
        e = next((e for e in self.cfg["engines"] if e["id"] == self.cfg["referencia"]), None)
        if e is None:
            raise RuntimeError(T("e.nenhuma"))
        return e, self.engine(e)

    def outras(self):
        """Engines ativas que não são a referência: lista de (dict, engine). Falhas viram (dict, None, erro)."""
        res = []
        for e in self.cfg["engines"]:
            if e["ativa"] and e["id"] != self.cfg["referencia"]:
                try: res.append((e, self.engine(e), None))
                except Exception as ex: res.append((e, None, str(ex)[:120]))
        return res

    def maia(self):
        h = self.cfg["humano"]
        sig = json.dumps(h, sort_keys=True)
        with self.lock:
            if self.maia_obj and self.maia_sig == sig: return self.maia_obj
            if self.maia_obj: self.maia_obj.close()
            if h["modo"] == "custom" and h["pesos"]:
                self.maia_obj = pipeline.Maia(lc0=resolve(h["lc0"]), pesos=resolve(h["pesos"]), args=h["argumentos"])
            else:
                self.maia_obj = pipeline.Maia()
            self.maia_sig = sig
            return self.maia_obj

    def fecha_engines(self):
        for _, eng in list(self.vivas.values()):
            try: eng.quit()
            except Exception: pass
        self.vivas.clear()

    def fecha_tudo(self):
        self.fecha_engines()
        if self.maia_obj: self.maia_obj.close()

    # ---------- teste de uma engine candidata
    @staticmethod
    def testar(caminho, argumentos="", opcoes=None):
        exe = resolve(caminho.strip().strip('"'))
        if not exe.is_file(): return {"ok": False, "erro": T("e.naoachou", p=exe)}
        cmd = [str(exe)] + args_abs(argumentos)
        try:
            eng = chess.engine.SimpleEngine.popen_uci(cmd, cwd=str(exe.parent), timeout=30)
        except Exception as ex:
            return {"ok": False, "erro": T("e.naouci", e=str(ex)[:150])}
        try:
            ops = eng.options
            try:
                eng.timeout = 15
                eng.analyse(chess.Board(), chess.engine.Limit(time=1))
            except Exception as ex:
                return {"ok": False, "erro": T("e.falhou", e=str(ex) or type(ex).__name__)}
            return {"ok": True, "nome": eng.id.get("name", ""), "autor": eng.id.get("author", ""),
                    "multipv": "MultiPV" in ops, "opcoes": sorted(ops.keys())[:60]}
        finally:
            try: eng.quit()
            except Exception: pass
