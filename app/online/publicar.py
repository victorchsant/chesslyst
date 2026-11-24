"""Publica a versão online no GitHub Pages (ramo gh-pages do próprio repositório).

Uso:  python app/online/publicar.py
Monta o site (construir_site.py), cria um commit novo só com o site num repositório temporário e o envia, à força, para o
ramo gh-pages. O ramo main não é tocado. Requer o git configurado com acesso de escrita ao repositório (remote 'origin').
No GitHub: Settings → Pages → Source = "Deploy from a branch", branch gh-pages, pasta / (raiz).
"""
import shutil, subprocess, sys, tempfile
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent.parent


def git(*args, cwd):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


subprocess.run([sys.executable, str(AQUI / "construir_site.py")], check=True)
url = git("config", "--get", "remote.origin.url", cwd=RAIZ)
msg = "Chesslyst online: " + git("log", "-1", "--format=%h %s", cwd=RAIZ)
tmp = Path(tempfile.mkdtemp(prefix="chesslyst-pages-"))
try:
    shutil.copytree(AQUI / "site", tmp / "site")
    d = tmp / "site"
    git("init", "-q", "-b", "gh-pages", cwd=d)
    git("add", "-A", cwd=d)
    git("-c", "user.name=Chesslyst", "-c", "user.email=noreply@users.noreply.github.com", "commit", "-q", "-m", msg, cwd=d)
    git("remote", "add", "origin", url, cwd=d)
    print(git("push", "-f", "origin", "gh-pages", cwd=d) or "gh-pages enviado")
finally:
    shutil.rmtree(tmp, ignore_errors=True)
