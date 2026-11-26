"""Gera o Chesslyst.exe (Windows, um único arquivo) com o PyInstaller, num ambiente isolado (app/exe/.venv-build).

Uso:  python app/exe/construir.py        ->  app/exe/dist/Chesslyst.exe
Os recursos (interface, calibrações, exemplos, lista de aberturas) vão dentro do .exe; as engines NÃO são incluídas
(o usuário as baixa pelo próprio app, cada uma com a sua licença).
"""
import subprocess, sys, venv
from pathlib import Path

AQUI = Path(__file__).resolve().parent
APP = AQUI.parent
VB = AQUI / ".venv-build"
PY = VB / "Scripts" / "python.exe"

if not PY.exists():
    print("Criando o ambiente de construção (só na primeira vez)…")
    venv.EnvBuilder(with_pip=True).create(VB)
subprocess.run([str(PY), "-m", "pip", "install", "--quiet", "--upgrade", "pyinstaller", "-r", str(APP / "requirements.txt")], check=True)

dados = [(APP / "web", "web"), (APP / "calibracao", "calibracao"), (APP / "exemplos", "exemplos"), (APP / "indice" / "aberturas.json", "indice"), (APP.parent / "LICENSE", ".")]
cmd = [str(PY), "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile", "--noconsole", "--name", "Chesslyst",
       "--distpath", str(AQUI / "dist"), "--workpath", str(AQUI / "build"), "--specpath", str(AQUI / "build"),
       "--paths", str(APP)]
for origem, destino in dados:
    cmd += ["--add-data", f"{origem};{destino}"]
cmd.append(str(AQUI / "exe_main.py"))
subprocess.run(cmd, check=True)
print("\nPronto:", AQUI / "dist" / "Chesslyst.exe")
