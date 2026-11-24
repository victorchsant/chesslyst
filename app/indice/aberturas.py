"""Nome e código ECO da abertura de cada posição de uma partida, em inglês e português.
Dados: lichess-org/chess-openings (CC0), convertidos em indice/aberturas.json (chave = EPD da posição).
O nome em português é montado por regras (substantivo + adjetivos com concordância); nomes próprios
(Najdorf, Morphy, Ruy Lopez…) ficam como estão, como nos livros em português."""
import json
from functools import lru_cache
from pathlib import Path
import chess

_ARQ = Path(__file__).with_name("aberturas.json")
try: _DB = json.loads(_ARQ.read_text(encoding="utf-8"))
except (OSError, ValueError): _DB = {}

# substantivo-núcleo: inglês -> (português, gênero)
_SUBST = {
    "Variation": ("Variante", "f"), "Variations": ("Variantes", "f"), "Line": ("Linha", "f"), "Gambit": ("Gambito", "m"),
    "Countergambit": ("Contragambito", "m"), "Attack": ("Ataque", "m"), "Counterattack": ("Contra-ataque", "m"),
    "Defense": ("Defesa", "f"), "System": ("Sistema", "m"), "Opening": ("Abertura", "f"), "Game": ("Jogo", "m"),
    "Formation": ("Formação", "f"), "Trap": ("Armadilha", "f"), "Endgame": ("Final", "m"), "Sacrifice": ("Sacrifício", "m"),
    "Retreat": ("Recuo", "m"), "Invitation": ("Convite", "m"), "Gambits": ("Gambitos", "m"),
}
# adjetivos com concordância: (masculino, feminino)
_ADJ = {
    "Classical": ("Clássico", "Clássica"), "Modern": ("Moderno", "Moderna"), "Closed": ("Fechado", "Fechada"),
    "Open": ("Aberto", "Aberta"), "Normal": ("Normal", "Normal"), "Main": ("Principal", "Principal"),
    "Symmetrical": ("Simétrico", "Simétrica"), "Orthodox": ("Ortodoxo", "Ortodoxa"), "Accelerated": ("Acelerado", "Acelerada"),
    "Reversed": ("Invertido", "Invertida"), "Delayed": ("Retardado", "Retardada"), "Deferred": ("Adiado", "Adiada"),
    "Quiet": ("Tranquilo", "Tranquila"), "Traditional": ("Tradicional", "Tradicional"), "Central": ("Central", "Central"),
    "Double": ("Duplo", "Dupla"), "Accepted": ("Aceito", "Aceita"), "Declined": ("Recusado", "Recusada"),
    "Old": ("Antigo", "Antiga"), "Positional": ("Posicional", "Posicional"), "Hybrid": ("Híbrido", "Híbrida"),
    "Global": ("Global", "Global"), "Eastern": ("Oriental", "Oriental"), "East": ("Oriental", "Oriental"), "Baltic": ("Báltico", "Báltica"),
    "Semi-Classical": ("Semiclássico", "Semiclássica"),
    "Austrian": ("Austríaco", "Austríaca"), "English": ("Inglês", "Inglesa"), "Spanish": ("Espanhol", "Espanhola"),
    "Scotch": ("Escocês", "Escocesa"), "Russian": ("Russo", "Russa"), "Italian": ("Italiano", "Italiana"), "French": ("Francês", "Francesa"),
    "Polish": ("Polonês", "Polonesa"), "Hungarian": ("Húngaro", "Húngara"), "Portuguese": ("Português", "Portuguesa"),
    "Czech": ("Tcheco", "Tcheca"), "Dutch": ("Holandês", "Holandesa"), "Sicilian": ("Siciliano", "Siciliana"),
    "Norwegian": ("Norueguês", "Norueguesa"), "Danish": ("Dinamarquês", "Dinamarquesa"), "Latvian": ("Letão", "Letã"),
    "Irish": ("Irlandês", "Irlandesa"), "Mexican": ("Mexicano", "Mexicana"), "Australian": ("Australiano", "Australiana"),
    "Basque": ("Basco", "Basca"), "Catalan": ("Catalão", "Catalã"), "Scandinavian": ("Escandinavo", "Escandinava"),
    "Slav": ("Eslavo", "Eslava"), "Semi-Slav": ("Semieslavo", "Semieslava"), "Indian": ("Índia", "Índia"),
    "Anglo-Indian": ("Anglo-Índia", "Anglo-Índia"), "Anglo-Slav": ("Anglo-Eslavo", "Anglo-Eslava"),
    "Exchange": ("de Troca", "de Troca"), "Poisoned": ("Envenenado", "Envenenada"),
    "Pianissimo": ("Pianíssimo", "Pianíssima"), "Advance": ("de Avanço", "de Avanço"),
    "Anti-Berlin": ("Anti-Berlim", "Anti-Berlim"), "Yugoslav": ("Iugoslavo", "Iugoslava"), "Pterodactyl": ("Pterodáctilo", "Pterodáctilo"),
    "Sacrifice": ("de Sacrifício", "de Sacrifício"), "Retreat": ("de Recuo", "de Recuo"), "Endgame": ("de Final", "de Final"), "Center": ("do Centro", "do Centro"),
}
# expressões e preposicionados (invariantes)
_FRASE = {
    "Main Line": "Linha Principal", "Bishop Sacrifice": "do Sacrifício do Bispo", "Knight Sacrifice": "do Sacrifício do Cavalo", "Queen Sacrifice": "do Sacrifício da Dama",
    "Two Pawns": "dos Dois Peões", "Three Pawns": "dos Três Peões", "Four Pawns": "dos Quatro Peões", "Three Pawn": "dos Três Peões", "King Walk": "da Caminhada do Rei", "King March": "da Marcha do Rei",
    "Queen's Gambit": "do Gambito da Dama", "King's Gambit": "do Gambito do Rei", "Two Knights": "dos Dois Cavalos", "Three Knights": "dos Três Cavalos", "Four Knights": "dos Quatro Cavalos",
    "Knights": "dos Cavalos", "Poisoned Pawn": "do Peão Envenenado", "Wing": "da Ala", "King's Pawn": "do Peão do Rei", "Queen's Pawn": "do Peão da Dama",
    "King's": "do Rei", "Queen's": "da Dama", "Bishop's": "do Bispo", "Knight's": "do Cavalo", "Bishop": "do Bispo", "Knight": "do Cavalo",
    "Queen": "da Dama", "Pawn": "do Peão", "Pawns": "dos Peões", "Vienna": "de Viena", "Paris": "de Paris", "Venice": "de Veneza",
    "Lion": "do Leão", "Rat": "do Rato", "Elephant": "do Elefante", "Hippopotamus": "do Hipopótamo", "Kangaroo": "do Canguru",
    "Vulture": "do Abutre", "Lemming": "do Lemingue", "Dragon": "Dragão", "Check": "de Xeque",
    "with": "com",
}
# famílias com ordem própria (nome completo)
_FAMILIAS = {
    "King's Indian Defense": "Defesa Índia do Rei", "King's Indian Attack": "Ataque Índia do Rei", "Queen's Indian Defense": "Defesa Índia da Dama",
    "Queen's Indian Accelerated": "Índia da Dama Acelerada", "Pseudo Queen's Indian Defense": "Pseudodefesa Índia da Dama",
    "Nimzo-Indian Defense": "Defesa Nimzo-Índia", "Bogo-Indian Defense": "Defesa Bogo-Índia", "Old Indian Defense": "Defesa Índia Antiga",
    "East Indian Defense": "Defesa Índia Oriental", "Indian Defense": "Defesa Índia", "Slav Indian": "Índia Eslava",
    "Queen's Pawn": "Peão da Dama", "King's Pawn": "Peão do Rei", "Queen's Pawn Game": "Jogo do Peão da Dama", "King's Pawn Game": "Jogo do Peão do Rei", "King's Pawn Opening": "Abertura do Peão do Rei",
    "King's Knight Opening": "Abertura do Cavalo do Rei", "Center Game": "Jogo do Centro", "Center Game Accepted": "Jogo do Centro Aceito",
    "English Orangutan": "Orangotango Inglês", "Petrov's Defense": "Defesa Petrov",
    "Vienna Game": "Jogo de Viena", "Vienna Gambit": "Gambito de Viena",
    "Four Knights Game": "Jogo dos Quatro Cavalos", "Three Knights Opening": "Abertura dos Três Cavalos",
    "Queen's Gambit": "Gambito da Dama", "Queen's Gambit Declined": "Gambito da Dama Recusado", "Queen's Gambit Accepted": "Gambito da Dama Aceito",
    "King's Gambit": "Gambito do Rei", "King's Gambit Accepted": "Gambito do Rei Aceito", "King's Gambit Declined": "Gambito do Rei Recusado",
    "Bishop's Opening": "Abertura do Bispo", "Formation": "Formação", "London System": "Sistema Londres",
}


def _tok(t, g):
    """Traduz uma palavra: adjetivo concordando com o gênero g, preposicionado, ou nome próprio (inalterado)."""
    if t in _FRASE: return _FRASE[t]
    if t in _ADJ: return _ADJ[t][0 if g == "m" else 1]
    if t.endswith("'s") and len(t) > 3: return t[:-2]          # Anderssen's -> Anderssen
    if t in _SUBST: return _SUBST[t][0]                          # substantivo usado como modificador
    if "-" in t:                                                 # compostos: Nimzo-Dutch -> Nimzo-Holandesa
        ps = t.split("-")
        if any(x in _ADJ for x in ps): return "-".join(_tok(x, g) for x in ps)
    return t


def _frases(t, g):
    saida, i = [], 0
    while i < len(t):
        for n in (3, 2):                                        # expressão mais longa primeiro
            f = " ".join(t[i:i + n])
            if len(t[i:i + n]) == n and f in _FRASE: saida.append(_FRASE[f]); i += n; break
        else:
            saida.append(_tok(t[i], g)); i += 1
    return saida


def _parte(p):
    """Traduz um trecho sem vírgulas/dois-pontos: 'Najdorf Variation', 'Gambit Accepted', 'Two Knights Defense'..."""
    p = p.strip()
    if not p: return p
    if p in _FAMILIAS: return _FAMILIAS[p]
    if p.startswith("with "): return "com " + _parte(p[5:])
    t = p.split()
    h = next((i for i in range(len(t) - 1, -1, -1) if t[i] in _SUBST), None)
    if h is None: return " ".join(_frases(t, "m"))
    nome, g = _SUBST[t[h]]
    # preposicionados ("do Rei", "dos Dois Cavalos") e adjetivos vão depois do substantivo, na ordem original
    return " ".join([nome] + _frases(t[:h], g) + _frases(t[h + 1:], g))


@lru_cache(maxsize=None)
def traduz(nome):
    """Nome da abertura em português. 'Sicilian Defense: Najdorf Variation' -> 'Defesa Siciliana: Variante Najdorf'."""
    return ": ".join(", ".join(_parte(s) for s in seg.split(", ")) for seg in nome.split(": "))


def nome_da_posicao(fen):
    """(eco, nome) da posição, no idioma atual, ou None se não for uma abertura da lista."""
    from .i18n import lang
    try: x = _DB.get(chess.Board(fen).epd())
    except ValueError: return None
    return (x[0], traduz(x[1]) if lang() != "en" else x[1]) if x else None


def nomes(fens):
    """Para cada posição (lista de FEN), [eco, nome_en, nome_pt] da abertura reconhecida mais recente, ou None.
    Mantém o último nome conhecido enquanto a partida segue por posições fora da lista."""
    saida, atual = [], None
    for f in fens:
        try:
            x = _DB.get(chess.Board(f).epd())
            if x: atual = [x[0], x[1], traduz(x[1])]
        except ValueError: pass
        saida.append(atual)
    return saida
