"""Download de engines direto das páginas oficiais (GitHub Releases), iniciado pelo usuário.

O projeto NÃO distribui Stockfish, Lc0 nem as redes Maia: cada pessoa baixa a sua cópia da fonte
oficial, sob a licença original (GPL-3.0). Só são aceitos os repositórios da lista abaixo.
"""
from __future__ import annotations
import hashlib, json, platform, tarfile, threading, urllib.request, zipfile
from pathlib import Path
from .i18n import T, set_lang, lang

from .caminhos import DADOS as ROOT       # as engines baixadas vão para a pasta de dados do usuário
UA = {"User-Agent": "indice-xadrez-pesquisa", "Accept": "application/vnd.github+json"}
WIN = platform.system() == "Windows"
EXT = ".exe" if WIN else ""

CATALOGO = {
    "stockfish": dict(
        nome="Stockfish", repo="official-stockfish/Stockfish", tag=None, destino="engines/stockfish",
        licenca="GPL-3.0", site="https://stockfishchess.org",
        licenca_url="https://github.com/official-stockfish/Stockfish/blob/master/Copying.txt",
        desc="A engine mais forte e usada como referência do índice."),
    "lc0": dict(
        nome="Lc0 (Leela Chess Zero, CPU)", repo="LeelaChessZero/lc0", tag=None, destino="engines/lc0",
        licenca="GPL-3.0", site="https://lczero.org",
        licenca_url="https://github.com/LeelaChessZero/lc0/blob/master/COPYING",
        desc="Necessário para executar as redes Maia (modelo de jogadores)."),
    "maia": dict(
        nome="Redes Maia 1100–1900", repo="CSSLab/maia-chess", tag="v1.0", destino="engines/maia",
        licenca="GPL-3.0", site="https://maiachess.com",
        licenca_url="https://github.com/CSSLab/maia-chess/blob/master/LICENSE",
        desc="Pesos que imitam jogadores de cada faixa de rating."),
}
ESTADOS = {}   # id -> dict(estado, pct, msg)


def _json(url):
    return json.load(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30))


def _escolhe(item_id, assets):
    """Devolve a lista de assets a baixar para esta plataforma (ou [] se indisponível)."""
    sis, mq = platform.system(), platform.machine().lower()
    arm = "arm" in mq or "aarch" in mq
    nomes = {a["name"]: a for a in assets}
    if item_id == "stockfish":
        alvo = {"Windows": "stockfish-windows-arm64-universal.zip" if arm else "stockfish-windows-x86-64-universal.zip",
                "Linux": "stockfish-linux-arm64-universal.tar.gz" if arm else "stockfish-linux-x86-64-universal.tar.gz",
                "Darwin": "stockfish-macos-universal.tar.gz"}.get(sis)
        return [nomes[alvo]] if alvo in nomes else []
    if item_id == "lc0":
        if sis != "Windows": return []   # sem binário oficial pré-compilado para CPU fora do Windows
        return [a for a in assets if a["name"].endswith("windows-cpu-dnnl.zip")][:1]
    if item_id == "maia":
        return sorted((a for a in assets if a["name"].startswith("maia-") and a["name"].endswith(".pb.gz")), key=lambda a: a["name"])
    return []


def instalado(item_id):
    d = ROOT / CATALOGO[item_id]["destino"]
    if not d.exists(): return None
    if item_id == "maia": return str(d) if any(d.glob("maia-*.pb.gz")) else None
    return achar_exe(item_id)


def achar_exe(item_id):
    d = ROOT / CATALOGO[item_id]["destino"]
    nome = "stockfish" if item_id == "stockfish" else "lc0"
    for p in sorted(d.rglob(nome + "*")):
        if p.is_file() and p.name.lower().startswith(nome) and p.suffix.lower() in (EXT, "") and p.stat().st_size > 500_000:
            return str(p)
    return None


def info(item_id):
    """Descrição do que será baixado (consulta a API do GitHub): arquivos, tamanho."""
    c = CATALOGO[item_id]
    rel = _json(f"https://api.github.com/repos/{c['repo']}/releases/" + (f"tags/{c['tag']}" if c["tag"] else "latest"))
    assets = _escolhe(item_id, rel["assets"])
    return dict(id=item_id, versao=rel["tag_name"], arquivos=[a["name"] for a in assets],
                mb=round(sum(a["size"] for a in assets) / 1e6, 1), disponivel=bool(assets),
                url=rel["html_url"], _assets=assets)


def catalogo():
    out = []
    for i, c in CATALOGO.items():
        try: inf = info(i); inf.pop("_assets")
        except Exception as e: inf = dict(id=i, disponivel=False, erro=str(e)[:100], arquivos=[], mb=0, versao="", url="")
        out.append(dict(c, **inf, nome=T(f"dl.{i}.n"), desc=T(f"dl.{i}.d"), instalado=bool(instalado(i)), estado=ESTADOS.get(i, {})))
    return out


def _seguro(destino: Path, nome: str) -> Path:
    alvo = (destino / nome).resolve()
    if destino.resolve() not in alvo.parents and alvo != destino.resolve():
        raise ValueError("arquivo suspeito no pacote: " + nome)
    return alvo


def _extrai(arq: Path, destino: Path):
    if arq.name.endswith(".zip"):
        with zipfile.ZipFile(arq) as z:
            for m in z.namelist(): _seguro(destino, m)
            z.extractall(destino)
    elif arq.name.endswith((".tar.gz", ".tgz")):
        with tarfile.open(arq) as t:
            for m in t.getmembers(): _seguro(destino, m.name)
            t.extractall(destino)
    # .pb.gz (Maia) fica como está


def _baixa(item_id, idioma="pt"):
    set_lang(idioma)
    est = ESTADOS[item_id]
    try:
        c = CATALOGO[item_id]
        inf = info(item_id)
        if not inf["disponivel"]: raise RuntimeError(T("d.sempacote"))
        destino = ROOT / c["destino"]; destino.mkdir(parents=True, exist_ok=True)
        total = sum(a["size"] for a in inf["_assets"]); feito = 0
        for a in inf["_assets"]:
            est.update(msg=T("d.baixando", a=a["name"]))
            arq = destino / a["name"]
            h = hashlib.sha256()
            req = urllib.request.Request(a["browser_download_url"], headers={"User-Agent": UA["User-Agent"]})
            with urllib.request.urlopen(req, timeout=60) as r, open(arq, "wb") as f:
                while (blk := r.read(1 << 16)):
                    f.write(blk); h.update(blk); feito += len(blk)
                    est["pct"] = round(100 * feito / total)
            dig = (a.get("digest") or "").removeprefix("sha256:")
            if dig and dig != h.hexdigest():
                arq.unlink(); raise RuntimeError(T("d.hash", a=a["name"]))
            if item_id != "maia":
                est.update(msg=T("d.extraindo")); _extrai(arq, destino); arq.unlink()
        if item_id in ("stockfish", "lc0"):
            exe = achar_exe(item_id)
            if not exe: raise RuntimeError(T("d.semexe"))
            if not WIN: Path(exe).chmod(0o755)
        est.update(estado="ok", pct=100, msg=T("d.ok", v=inf["versao"]))
    except Exception as e:
        est.update(estado="erro", msg=str(e)[:200])


def baixar(item_id):
    if item_id not in CATALOGO: raise KeyError(item_id)
    if ESTADOS.get(item_id, {}).get("estado") == "baixando": return
    ESTADOS[item_id] = dict(estado="baixando", pct=0, msg=T("d.iniciando"))
    threading.Thread(target=_baixa, args=(item_id, lang()), daemon=True).start()
