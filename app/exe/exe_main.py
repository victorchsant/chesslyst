"""Ponto de entrada do Chesslyst.exe (Windows): sobe o servidor local e abre o navegador, sem janela de console.

O programa se encerra sozinho cerca de 90 s depois de fechar a página. O registro fica em
%LOCALAPPDATA%/Chesslyst/servidor.log; engines, caches e configurações ficam nessa mesma pasta.
"""
import os, subprocess, sys, threading, time, urllib.request, webbrowser
from pathlib import Path

if os.name == "nt":      # nenhum programa filho (as engines) abre janela de console
    _init = subprocess.Popen.__init__

    def _sem_janela(self, *a, **k):
        k["creationflags"] = k.get("creationflags", 0) | 0x08000000      # CREATE_NO_WINDOW
        _init(self, *a, **k)
    subprocess.Popen.__init__ = _sem_janela

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))      # modo desenvolvimento: app/ com server.py e indice/
from indice.caminhos import DADOS

try: sys.stdout = sys.stderr = open(DADOS / "servidor.log", "w", encoding="utf-8", buffering=1)
except OSError: pass


def aviso(texto):
    try:
        import tkinter, tkinter.messagebox as mb
        r = tkinter.Tk(); r.withdraw(); mb.showerror("Chesslyst", texto); r.destroy()
    except Exception:
        print(texto)


def ativo(url):
    try:
        urllib.request.urlopen(url + "ping.js", timeout=1.5)
        return True
    except Exception:
        return False


def main():
    import server
    url = f"http://127.0.0.1:{server.PORT}/"
    abrir = "--sem-navegador" not in sys.argv
    if ativo(url):                       # já está rodando: só abre a página
        if abrir: webbrowser.open(url)
        return

    def abre_quando_pronto():
        for _ in range(80):
            if ativo(url):
                if abrir: webbrowser.open(url)
                return
            time.sleep(0.25)
    threading.Thread(target=abre_quando_pronto, daemon=True).start()
    try:
        server.servir()
    except OSError as e:
        aviso(f"Não consegui iniciar o servidor (a porta {server.PORT} pode estar em uso por outro programa).\n\n{e}")


if __name__ == "__main__":
    main()
