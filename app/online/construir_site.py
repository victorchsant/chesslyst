"""Monta a versão online (site estático para o GitHub Pages) em app/online/site/.

Uso:  python app/online/construir_site.py
Baixa (uma vez, para app/online/vendor/) os arquivos do Stockfish em WebAssembly (GPL-3.0, pacote npm 'stockfish') e junta:
interface (app/web), shim.js, webserver.py, o pacote indice, as calibrações e o python-chess num app.zip que roda no navegador.
"""
import shutil, sys, urllib.request, zipfile
from pathlib import Path

AQUI = Path(__file__).resolve().parent
APP = AQUI.parent
RAIZ = APP.parent
SITE = AQUI / "site"
VENDOR = AQUI / "vendor"
SF = "https://unpkg.com/stockfish@19.0.1/bin/"
ARQS_SF = ["stockfish-19-lite-single.js", "stockfish-19-lite-single.wasm"]
COPYING = "https://unpkg.com/stockfish@19.0.1/Copying.txt"


def baixa(url, destino):
    if destino.exists() and destino.stat().st_size > 0: return
    destino.parent.mkdir(parents=True, exist_ok=True)
    print("baixando", url)
    req = urllib.request.Request(url, headers={"User-Agent": "chesslyst-build"})
    with urllib.request.urlopen(req, timeout=120) as r, open(destino, "wb") as f: shutil.copyfileobj(r, f)


if SITE.exists():                      # esvazia sem apagar a própria pasta (um servidor de teste pode estar aberto nela)
    for f in SITE.iterdir(): shutil.rmtree(f) if f.is_dir() else f.unlink()
(SITE / "motor").mkdir(parents=True, exist_ok=True)
for a in ARQS_SF: baixa(SF + a, VENDOR / a); shutil.copy(VENDOR / a, SITE / "motor" / a)
baixa(COPYING, VENDOR / "Copying.txt"); shutil.copy(VENDOR / "Copying.txt", SITE / "motor" / "Copying.txt")

# interface: a mesma da versão local, com o shim carregado antes de tudo
html = (APP / "web" / "index.html").read_text(encoding="utf-8")
assert "<head>" in html
html = html.replace("<head>", '<head>\n<script src="shim.js"></script>', 1)
(SITE / "index.html").write_text(html, encoding="utf-8")
shutil.copy(APP / "web" / "idiomas.js", SITE / "idiomas.js")
shutil.copy(AQUI / "shim.js", SITE / "shim.js")
shutil.copy(APP / "exemplos" / "teste.pgn", SITE / "teste.pgn")
shutil.copy(RAIZ / "LICENSE", SITE / "LICENSE")
(SITE / ".nojekyll").write_text("", encoding="utf-8")

# app.zip: o que roda dentro do Pyodide (inclui o python-chess, que é Python puro)
import chess
with zipfile.ZipFile(SITE / "app.zip", "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    for f in sorted((APP / "indice").glob("*.py")): z.write(f, f"indice/{f.name}")
    z.write(APP / "indice" / "aberturas.json", "indice/aberturas.json")
    for nome in ("calibracao.json", "calibracao_tempo.json", "posicional.json"): z.write(APP / "calibracao" / nome, f"calibracao/{nome}")
    z.write(AQUI / "webserver.py", "webserver.py")
    pasta = Path(chess.__file__).resolve().parent
    for f in sorted(pasta.rglob("*.py")): z.write(f, "chess/" + f.relative_to(pasta).as_posix())
    z.write(pasta / "py.typed", "chess/py.typed") if (pasta / "py.typed").exists() else None
print("site pronto em", SITE, "|", round((SITE / "app.zip").stat().st_size / 1024), "KB de app.zip")
