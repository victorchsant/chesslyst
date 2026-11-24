#!/usr/bin/env python3
"""Inicia o Chesslyst (Windows, Linux e Mac): prepara o ambiente na primeira vez, sobe o servidor e abre o navegador.

Uso:  python iniciar.py            terminal visível (mostra o que o servidor imprime; Ctrl+C encerra)
      iniciar.pyw                  Windows, dois cliques, SEM janela de terminal (servidor oculto)
      python iniciar.py --sem-navegador
Requer Python 3.10+. Na primeira execução cria a pasta .venv e instala o python-chess (precisa de internet).
No modo sem janela o servidor se encerra sozinho ~90 s depois de fechar a página (ou pelo botão ⏻ da interface).
"""
import os, subprocess, sys, time, urllib.request, venv, webbrowser
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
PORTA = 8765
URL = f"http://127.0.0.1:{PORTA}/"
VENV = RAIZ / ".venv"
PY = VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
SILENCIOSO = "--silencioso" in sys.argv or Path(sys.executable).name.lower().startswith("pythonw")
SEM_JANELA = 0x08000000 | 0x00000200      # CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP (só Windows)


def mensagem(titulo, texto, erro=False):
    """Mostra uma caixa de diálogo (sem terminal) ou imprime."""
    print(("ERRO: " if erro else "") + texto)
    if not SILENCIOSO: return
    try:
        import tkinter, tkinter.messagebox as mb
        r = tkinter.Tk(); r.withdraw()
        (mb.showerror if erro else mb.showinfo)(titulo, texto)
        r.destroy()
    except Exception:
        pass


def pausa_erro(msg):
    if SILENCIOSO:
        mensagem("Chesslyst", msg, erro=True)
    else:
        print("\nERRO:", msg)
        if os.name == "nt" and sys.stdin and sys.stdin.isatty():
            input("Pressione Enter para fechar…")
    sys.exit(1)


def servidor_ativo():
    try:
        urllib.request.urlopen(URL + "ping.js", timeout=1.5)
        return True
    except Exception:
        return False


def rodar_oculto(cmd, **kw):
    """Roda um comando sem abrir janela (Windows) e devolve o resultado."""
    if os.name == "nt": kw["creationflags"] = SEM_JANELA
    return subprocess.run(cmd, **kw)


def prepara_ambiente():
    if sys.version_info < (3, 10):
        pausa_erro(f"é preciso Python 3.10 ou mais novo (você tem {sys.version.split()[0]}).")
    splash = None
    precisa = not PY.exists() or rodar_oculto([str(PY), "-c", "import chess"], capture_output=True).returncode != 0
    if precisa and SILENCIOSO:   # primeira vez: avisa numa janelinha enquanto instala
        try:
            import tkinter
            splash = tkinter.Tk(); splash.title("Chesslyst"); splash.geometry("340x70"); splash.resizable(False, False)
            tkinter.Label(splash, text="Preparando o Chesslyst pela primeira vez…\nIsso leva cerca de um minuto.", pady=14).pack()
            splash.update()
        except Exception:
            splash = None
    try:
        if not PY.exists():
            print("Primeira execução: criando o ambiente (.venv)…")
            venv.EnvBuilder(with_pip=True).create(VENV)
        if rodar_oculto([str(PY), "-c", "import chess"], capture_output=True).returncode != 0:
            print("Instalando o python-chess (só na primeira vez)…")
            r = rodar_oculto([str(PY), "-m", "pip", "install", "--quiet", "-r", str(RAIZ / "requirements.txt")], capture_output=True)
            if r.returncode != 0:
                pausa_erro("não consegui instalar o python-chess (confira a internet) e tente de novo.")
    finally:
        if splash:
            try: splash.destroy()
            except Exception: pass


def main():
    abrir = "--sem-navegador" not in sys.argv
    if servidor_ativo():
        print("O Chesslyst já está rodando. Abrindo o navegador…")
        if abrir: webbrowser.open(URL)
        return
    prepara_ambiente()
    if SILENCIOSO:
        log = open(RAIZ / "servidor.log", "w", encoding="utf-8")
        kw = dict(cwd=str(RAIZ), stdout=log, stderr=log, stdin=subprocess.DEVNULL)
        if os.name == "nt": kw["creationflags"] = SEM_JANELA
        else: kw["start_new_session"] = True
        proc = subprocess.Popen([str(PY), str(RAIZ / "server.py")], **kw)
    else:
        print("Iniciando o servidor… (feche esta janela ou use Ctrl+C para encerrar)")
        proc = subprocess.Popen([str(PY), str(RAIZ / "server.py"), "--manter"], cwd=str(RAIZ))
    try:
        for _ in range(60):
            if proc.poll() is not None:
                pausa_erro("o servidor encerrou ao iniciar (a porta 8765 pode estar em uso por outro programa). Veja servidor.log.")
            if servidor_ativo(): break
            time.sleep(0.5)
        else:
            pausa_erro("o servidor não respondeu a tempo.")
        print(f"Pronto: {URL}")
        if abrir: webbrowser.open(URL)
        if SILENCIOSO:
            return                      # o servidor segue oculto e se encerra sozinho
        proc.wait()
    except KeyboardInterrupt:
        pass
    finally:
        if not SILENCIOSO and proc.poll() is None:
            proc.terminate()
            try: proc.wait(5)
            except subprocess.TimeoutExpired: proc.kill()


if __name__ == "__main__":
    main()
