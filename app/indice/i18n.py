"""Idiomas (pt / en) dos textos gerados pelo programa. O idioma vale por thread/pedido (contextvars).

T(chave, **dados) devolve o texto no idioma atual; P(q, chave) escolhe singular/plural ("sing|plur");
num(x, casas) formata número com vírgula (pt) ou ponto (en).
"""
from __future__ import annotations
import contextvars

_L = contextvars.ContextVar("lang", default="pt")


def set_lang(l):
    _L.set("en" if str(l or "").lower().startswith("en") else "pt")


def lang():
    return _L.get()


def T(chave, **kw):
    pt, en = TXT[chave]
    s = en if _L.get() == "en" else pt
    return s.format(**kw) if kw else s


def P(q, chave):
    """Verbo/substantivo no singular (q == 1) ou plural, a partir de um texto 'sing|plur'."""
    a, b = T(chave).split("|")
    return a if q == 1 else b


def num(x, casas=1):
    s = f"{x:.{casas}f}"
    return s.replace(".", ",") if _L.get() == "pt" else s


def pontos(v):
    """Unidade 'ponto(s)'. Português: singular até 1; inglês: singular só no 1 exato."""
    sing = v <= 1.0 if _L.get() == "pt" else round(v, 1) == 1.0
    a, b = T("u.ponto").split("|")
    return a if sing else b


TXT = {
    # ---------- faixas do índice de acerto
    "b1.n": ("Quase certo", "Almost certain"), "b1.d": ("qualquer jogador de elite acha o lance", "any elite player finds the move"),
    "b2.n": ("Fácil", "Easy"), "b2.d": ("o lance é natural, erro seria raro", "the move is natural, a mistake would be rare"),
    "b3.n": ("Exige atenção", "Needs attention"), "b3.d": ("existe risco real de errar, mas é achável", "there is a real risk of going wrong, but it can be found"),
    "b4.n": ("Difícil", "Hard"), "b4.d": ("poucos jogadores acham o lance; precisão fina necessária", "few players find the move; fine precision is needed"),
    "b5.n": ("Muito difícil", "Very hard"), "b5.d": ("praticamente só a engine acha; vantagem teórica quase não se converte", "practically only the engine finds it; the theoretical advantage is rarely converted"),
    # ---------- motivos
    "r.teoria": ("Posição de teoria: muito jogada por mestres.", "Opening theory: a position played very often by masters."),
    "r.unico": ("Lance quase forçado: o segundo melhor ({san}) já piora bastante a posição.", "Almost forced move: the second best ({san}) already makes the position clearly worse."),
    "r.so_um": ("Só um lance mantém a avaliação; os outros candidatos custam caro.", "Only one move keeps the evaluation; the other candidates are costly."),
    "r.mate": ("Mate forçado em {m}: tática curta e clara, fácil de calcular.", "Forced mate in {m}: a short, clear tactic, easy to calculate."),
    "r.contra": ("Lance contraintuitivo: a engine só o enxerga com cálculo profundo.", "Counterintuitive move: the engine only sees it with deep calculation."),
    "r.ft_win": ("Final técnico{kind}: vitória teórica, mas só {w} de {l} lances legais {v} o ganho. Exige precisão de cálculo muito fina.",
                 "Technical endgame{kind}: theoretically won, but only {w} of {l} legal moves {v} the win. It requires very fine calculation."),
    "v.mantem": ("mantém|mantêm", "keeps|keep"),
    "r.ft_win_n": ("Final{kind} ganho na tablebase, com {w} de {l} lances vencedores.", "Won endgame{kind} in the tablebase, with {w} of {l} winning moves."),
    "r.ft_draw": ("Final técnico{kind}: empate teórico, mas só {h} de {l} lances legais {v} a posição; um deslize e ela está perdida.",
                  "Technical endgame{kind}: theoretical draw, but only {h} of {l} legal moves {v} the position; one slip and it is lost."),
    "v.segura": ("segura|seguram", "holds|hold"),
    "r.ft_draw_n": ("Final{kind} empatado na tablebase; {h} de {l} lances {v}.", "Drawn endgame{kind} in the tablebase; {h} of {l} moves {v}."),
    "r.arm": ("Armadilha: o lance mais natural ({san}) é um erro.", "Trap: the most natural move ({san}) is a mistake."),
    "r.div": ("As engines divergem: {lista} (a referência prefere {san}). Posição de difícil decisão até para engines.",
              "The engines disagree: {lista} (the reference prefers {san}). A position that is hard to decide even for engines."),
    "r.div_item": ("{nome} prefere {san}", "{nome} prefers {san}"),
    "r.conc": ("As {n} engines concordam no lance.", "All {n} engines agree on the move."),
    "r.conc2": ("As 2 engines concordam no lance.", "Both engines agree on the move."),
    "r.clock": ("No relógio: {t}.", "On the clock: {t}."), "r.pouco": (" Pouco tempo.", " Little time left."),
    "r.gasto": ("Gastou {g}; restavam {r} no relógio.", "Spent {g}; {r} left on the clock."),
    # ---------- frase principal
    "h.vant_dif": ("Vantagem clara para quem joga, mas {d}.", "Clear advantage for the side to move, but {d}."),
    "h.vant": ("Vantagem clara para quem joga: {d}.", "Clear advantage for the side to move: {d}."),
    "h.ruim_dif": ("Posição difícil para quem joga: {d}.", "Difficult position for the side to move: {d}."),
    "h.ruim": ("Posição difícil para quem joga: {d}.", "Difficult position for the side to move: {d}."),
    "h.melhor": ("Posição um pouco melhor para quem joga: {d}.", "Position slightly better for the side to move: {d}."),
    "h.pior": ("Posição um pouco pior para quem joga: {d}.", "Position slightly worse for the side to move: {d}."),
    "h.eq": ("Posição equilibrada: {d}.", "Balanced position: {d}."),
    # ---------- índice de jogada
    "c.melhor": ("Melhor lance", "Best move"), "c.excelente": ("Excelente", "Excellent"), "c.bom": ("Bom", "Good"),
    "c.imprecisao": ("Imprecisão", "Inaccuracy"), "c.erro": ("Erro", "Mistake"), "c.grave": ("Erro grave", "Blunder"),
    "c.brilhante": ("Brilhante", "Brilliant"),
    "u.ponto": ("ponto|pontos", "point|points"),
    "j.brilhante": ("Brilhante: lance muito preciso e pouco intuitivo.", "Brilliant: a very precise, non-obvious move."),
    "j.melhor": ("Melhor lance da posição.", "Best move in the position."),
    "j.pouca": ("Quase tão bom quanto o melhor lance.", "Almost as good as the best move."),
    "j.muita": ("Piorou a posição", "Made the position worse"),
    "j.escapar": (" e deixou a vitória escapar", " and let the win slip away"),
    "j.perdida": (" e a posição ficou perdida", " and the position became lost"),
    "j.facil": (" O lance certo era fácil de achar.", " The right move was easy to find."),
    # ---------- material (descrição curta)
    "m.peao": ("um peão a mais", "a pawn up"), "m.dois": ("dois peões a mais", "two pawns up"), "m.peca": ("uma peça a mais", "a piece up"),
    "m.peca_peao": ("uma peça e um peão a mais", "a piece and a pawn up"), "m.torre": ("uma torre a mais", "a rook up"),
    "m.dama": ("uma dama a mais", "a queen up"), "m.mais": ("{n} peões a mais", "{n} pawns up"),
    # ---------- explicação do lance
    "x.mate1": ("Dá xeque-mate.", "Delivers checkmate."), "x.mate_forcado": ("Leva ao xeque-mate em {n}.", "Leads to checkmate in {n}."),
    "x.captura": ("Captura {p}.", "Captures {p}."), "x.xeque": ("Dá xeque.", "Gives check."),
    "x.roque": ("Roque: coloca o rei em segurança.", "Castling: puts the king to safety."), "x.promove": ("Promove o peão.", "Promotes the pawn."),
    "x.sacrificio": ("Sacrifício: entrega {p} para obter uma posição muito melhor.", "Sacrifice: gives up {p} for a much better position."),
    "x.preciso": ("Lance muito preciso e pouco intuitivo.", "A very precise, non-obvious move."),
    "x.quase": ("Quase tão bom quanto o melhor lance ({m}).", "Almost as good as the best move ({m})."),
    "x.bom": ("Bom lance, mas {m} era um pouco melhor.", "A good move, but {m} was slightly better."),
    "x.permitiu_mate": ("Permitiu xeque-mate em {n}.", "Allowed checkmate in {n}."),
    "x.perdeu_mate": ("Perdeu o xeque-mate em {n}.", "Missed checkmate in {n}."),
    "x.perdeu_troca": ("Perdeu {p} na troca.", "Lost {p} in the exchange."), "x.perdeu": ("Perdeu {p}.", "Lost {p}."),
    "x.sem_defesa": ("Deixou {p} sem defesa.", "Left {p} undefended."),
    "x.deixou_ganhar": ("Deixou de ganhar {p}.", "Missed winning {p}."),
    "x.risco": ("Deixou {p} em risco.", "Left {p} en prise."), "x.perdeu_roque": ("Perdeu o direito de rocar.", "Gave up the right to castle."),
    "x.desenv": ("Desenvolve {o}.", "Develops {o}."), "x.centraliza": ("Centraliza {o}.", "Centralizes {o}."),
    "x.mob_mais": ("Dá mais mobilidade {o}.", "Gives {o} more mobility."), "x.mob_menos": ("Reduz a mobilidade {o}.", "Reduces {o}'s mobility."),
    "x.ataca": ("Ataca {p}.", "Attacks {p}."), "x.piorou_mob": ("Piorou a posição. {e}", "Made the position worse. {e}"),
    "x.perde_em": ("Perde {p} em {n} lances.", "Loses {p} in {n} moves."),
    "y.dobra": ("Dobra as torres na coluna {c}.", "Doubles the rooks on the {c}-file."), "yg.dobra": ("dobrando as torres na coluna {c}", "doubling the rooks on the {c}-file"),
    "y.aberta": ("Põe a torre na coluna {c} aberta.", "Puts the rook on the open {c}-file."), "yg.aberta": ("pondo a torre na coluna {c} aberta", "putting the rook on the open {c}-file"),
    "y.semi": ("Põe a torre na coluna {c} semiaberta.", "Puts the rook on the half-open {c}-file."), "yg.semi": ("pondo a torre na coluna {c} semiaberta", "putting the rook on the half-open {c}-file"),
    "y.setima": ("Leva a torre à sétima fileira.", "Brings the rook to the seventh rank."), "yg.setima": ("levando a torre à sétima fileira", "bringing the rook to the seventh rank"),
    "y.posto": ("Leva {o} a um posto avançado em {s}.", "Takes {o} to an outpost on {s}."), "yg.posto": ("levando {o} a um posto avançado em {s}", "taking {o} to an outpost on {s}"),
    "y.passado": ("Avança o peão passado.", "Pushes the passed pawn."), "yg.passado": ("avançando o peão passado", "pushing the passed pawn"),
    "y.fianchetto": ("Faz o fianchetto do bispo.", "Fianchettoes the bishop."), "yg.fianchetto": ("fazendo o fianchetto do bispo", "fianchettoing the bishop"),
    "y.quebra": ("Ataca um peão adversário com um avanço de peão.", "Attacks an enemy pawn with a pawn advance."), "yg.quebra": ("atacando um peão adversário", "attacking an enemy pawn"),
    "y.garfo": ("Ataque duplo: ataca {a} e {b}.", "Fork: attacks {a} and {b}."), "yg.garfo": ("atacando {a} e {b} ao mesmo tempo", "with a fork on {a} and {b}"),
    "y.cravada": ("Crava {p} contra o rei.", "Pins {p} against the king."), "yg.cravada": ("cravando {p} contra o rei", "pinning {p} against the king"),
    "y.salva": ("Tira {p} do ataque.", "Moves {p} out of attack."), "yg.salva": ("tirando {p} do ataque", "moving {p} out of attack"),
    "y.protege": ("Protege {p}.", "Defends {p}."), "yg.protege": ("protegendo {p}", "defending {p}"),
    "y.rei": ("Ativa o rei no final.", "Activates the king in the endgame."), "yg.rei": ("ativando o rei", "activating the king"),
    "pq.teoria": ("Teoria de abertura{ab}: posição já vista em {n} partidas de mestres.", "Opening theory{ab}: a position already seen in {n} master games."),
    "pq.teoria_m": ("Os mestres seguem sobretudo com {l}.", "Masters mostly continue with {l}."),
    "pq.ganha": ("O melhor lance ({m}) leva a ganhar {p} em {n} lances: é preciso calcular a variante até o fim.", "The best move ({m}) wins {p} in {n} moves: the line has to be calculated to the end."),
    "pq.xeque": ("O melhor lance ({m}) é um xeque, um lance forçante que costuma ser fácil de ver.", "The best move ({m}) is a check, a forcing move that is usually easy to spot."),
    "pq.captura": ("O melhor lance ({m}) é uma captura.", "The best move ({m}) is a capture."),
    "pq.ideia": ("A ideia do melhor lance ({m}): {i}.", "The idea behind the best move ({m}): {i}."),
    "pq.varios": ("Vários lances mantêm a posição ({l}): a escolha é livre, por isso é fácil acertar.", "Several moves keep the position ({l}): there is a free choice, so it is easy to get right."),
    "pq.risco": ("Há peças em risco na posição: convém calcular as ameaças antes de mover.", "There are pieces at risk: calculate the threats before moving."),
    "x.mate_em": ("mate em {n}", "mate in {n}"),
    "x.sobe_i": ("A avaliação sobe de {a} para {b}: a engine confirma a ideia de {m}{i}.", "The evaluation rises from {a} to {b}: the engine confirms the idea of {m}{i}."),
    "x.sobe": ("A avaliação sobe de {a} para {b} depois deste lance.", "The evaluation rises from {a} to {b} after this move."),
    "pz.mob_mais": ("Aumenta a mobilidade das peças.", "Increases piece mobility."), "pz.mob_menos": ("Reduz a mobilidade das peças.", "Reduces piece mobility."),
    "pz.desenv_mais": ("Avança o desenvolvimento das peças.", "Advances piece development."), "pz.desenv_menos": ("Atrasa o desenvolvimento das peças.", "Delays piece development."),
    "pz.centro_mais": ("Reforça o controle do centro.", "Strengthens control of the center."), "pz.centro_menos": ("Perde controle do centro.", "Loses control of the center."),
    "pz.espaco_mais": ("Ganha espaço.", "Gains space."), "pz.espaco_menos": ("Perde espaço.", "Loses space."),
    "pz.rei_mais": ("Deixa o rei mais seguro.", "Makes the king safer."), "pz.rei_menos": ("Enfraquece a segurança do rei.", "Weakens the king's safety."),
    "pz.reif_mais": ("Aproxima o rei do centro.", "Brings the king toward the center."), "pz.reif_menos": ("Afasta o rei do centro.", "Moves the king away from the center."),
    "pz.torres_mais": ("Melhora a posição das torres.", "Improves the rooks' placement."), "pz.torres_menos": ("Piora a posição das torres.", "Worsens the rooks' placement."),
    "pz.bispos_menos": ("Abre mão do par de bispos.", "Gives up the bishop pair."),
    "pz.dob_mais": ("Desfaz peões dobrados.", "Undoes doubled pawns."), "pz.dob_menos": ("Cria peões dobrados.", "Creates doubled pawns."),
    "pz.iso_mais": ("Resolve um peão isolado.", "Fixes an isolated pawn."), "pz.iso_menos": ("Cria um peão isolado.", "Creates an isolated pawn."),
    "pz.pas_mais": ("Cria um peão passado.", "Creates a passed pawn."), "pz.pas_menos": ("Perde um peão passado.", "Loses a passed pawn."),
    "pz.risco_mais": ("Alivia peças em risco.", "Relieves pieces at risk."), "pz.risco_menos": ("Deixa uma peça em risco.", "Leaves a piece at risk."),
    "pz.fracas_mais": ("Reduz casas fracas.", "Reduces weak squares."), "pz.fracas_menos": ("Cria casas fracas.", "Creates weak squares."),
    "pz.posto_mais": ("Leva uma peça a um posto avançado.", "Brings a piece to an outpost."), "pz.posto_menos": ("Perde um posto avançado.", "Loses an outpost."),
    "db.mais": ("As {l} têm mais debilidades ({o}).", "{l} has more weaknesses ({o})."), "db.e": (" e ", " and "),
    "db.casas": ("casas fracas", "weak squares"), "db.pecas": ("peças expostas", "exposed pieces"),
    "db.sob_ataque": ("{n} {v} sob ataque", "{n} {v} under attack"), "db.peca": ("peça|peças", "piece|pieces"),
    "db.ocupa": ("{p} adversário ocupa {s}", "an enemy {p} occupies {s}"), "db.controla": ("peças menores adversárias controlam {s}", "enemy minor pieces control {s}"), "db.controla1": ("uma peça menor adversária controla {s}", "an enemy minor piece controls {s}"),
    "db.aproveita": ("O adversário já as aproveita: {c}.", "The opponent is already exploiting them: {c}."),
    "db.nao": ("O adversário ainda não as aproveita.", "The opponent is not exploiting them yet."),
    "db.p2": ("um cavalo", "knight"), "db.p3": ("um bispo", "bishop"), "db.p4": ("uma torre", "rook"), "db.p5": ("uma dama", "queen"),
    "gv.rei": ("rei longe de ataques", "a king away from attacks"), "gv.reif": ("rei ativo", "an active king"),
    "gv.estrutura": ("estrutura de peões", "pawn structure"), "gv.atividade": ("atividade das peças", "piece activity"),
    "gv.debilidades": ("debilidades do adversário", "the opponent's weaknesses"), "gv.postos": ("peças em postos avançados", "pieces on outposts"),
    "gv.material": ("material", "material"),
    "po.item": ("{p} das {c} em {s}", "{c} {p} on {s}"), "po.p2": ("cavalo", "knight"), "po.p3": ("bispo", "bishop"),
    "po.um": ("Posto avançado: {l}.", "Outpost: {l}."), "po.varios": ("Postos avançados: {l}.", "Outposts: {l}."),
    "gv.fuga": ("rei com casas de fuga", "a king with escape squares"),
    "pz.rzona_mais": ("Afasta os ataques da zona do rei.", "Pushes attacks away from the king's zone."), "pz.rzona_menos": ("Expõe as casas ao redor do rei.", "Exposes the squares around the king."),
    "pz.raiox_mais": ("Fecha uma linha de raio-x contra o rei.", "Closes an x-ray line against the king."), "pz.raiox_menos": ("Abre uma linha de raio-x contra o rei.", "Opens an x-ray line against the king."),
    "pz.fuga_mais": ("Dá casas de fuga ao rei.", "Gives the king escape squares."), "pz.fuga_menos": ("Tira casas de fuga do rei.", "Takes escape squares away from the king."),
    "rk.base": ("O rei das {l} está sob pressão: {m}.", "{l}'s king is under pressure: {m}."),
    "rk.xeque": ("em xeque, com {n} {v}", "in check, with {n} {v}"), "rk.resp": ("resposta legal|respostas legais", "legal reply|legal replies"),
    "rk.fuga": ("quase sem casas de fuga", "almost no escape squares"), "rk.zona": ("várias casas ao redor atacadas", "several surrounding squares attacked"),
    "rk.raiox": ("linha de raio-x apontada para ele", "an x-ray line pointed at it"),
    "rp.rep2": ("Esta posição já apareceu {n} vezes na partida (repetição de lances).", "This position has appeared {n} times in the game (repetition)."),
    "rp.rep3": ("Esta posição apareceu {n} vezes: empate por repetição.", "This position has appeared {n} times: draw by repetition."),
    "rp.perpetuo": ("As {l} dão xeques seguidos e a posição se repete ({n}ª vez){e}: xeque perpétuo, empate por repetição.", "{l} keeps giving checks and the position repeats (time {n}){e}: perpetual check, draw by repetition."),
    "rp.so": (", e o rei adversário só tem {n} {v}", ", and the enemy king has only {n} {v}"), "rp.resp": ("resposta|respostas", "reply|replies"),
    "g.moderada": ("moderada", "Moderate"),
    "p.favor": ("A favor das {l}: {i}.", "In favor of {l}: {i}."),
    "p.motor_eq": ("A engine, porém, vê o jogo equilibrado.", "The engine, however, sees a balanced game."),
    "pf.mobilidade": ("mobilidade das peças", "piece mobility"), "pf.desenvolvimento": ("melhor desenvolvimento", "better development"),
    "pf.torres": ("torres mais ativas", "more active rooks"), "pf.centro": ("controle do centro", "control of the center"),
    "pf.espaco": ("mais espaço", "more space"), "pf.par_de_bispos": ("par de bispos", "the bishop pair"),
    "pf.seguranca_rei": ("rei mais seguro", "a safer king"), "pf.rei_zona": ("rei menos pressionado", "a king under less pressure"),
    "pf.rei_raiox": ("rei sem raio-x contra ele", "no x-ray against the king"), "pf.rei_fuga": ("rei com casas de fuga", "a king with escape squares"),
    "pf.rei_final": ("rei mais ativo", "a more active king"), "pf.pecas_em_risco": ("peças do adversário em risco", "enemy pieces at risk"),
    "pf.casas_fracas": ("casas fracas do adversário", "the opponent's weak squares"), "pf.postos_avancados": ("postos avançados", "outposts"),
    "pf.peoes_dobrados": ("peões dobrados do adversário", "the opponent's doubled pawns"),
    "pf.peoes_isolados": ("peões isolados do adversário", "the opponent's isolated pawns"), "pf.peoes_passados": ("peão passado", "a passed pawn"),
    "db.mais": ("As {l} têm mais debilidades: {o}.", "{l} has more weaknesses: {o}."),
    "db.casas_em": ("casas fracas em {s}", "weak squares on {s}"), "db.pecas_em": ("peças expostas ({p})", "exposed pieces ({p})"),
    "db.ja_atacadas": ("as peças expostas já estão sob ataque", "the exposed pieces are already under attack"),
    "db.ocupa": ("{p} ocupa uma delas", "{p} occupies one of them"), "db.controla": ("{p} controla {s}", "{p} controls {s}"),
    "po.um": ("Posto avançado: {l}.", "Outpost: {l}."), "po.varios": ("Postos avançados: {l}.", "Outposts: {l}."),
    "rk.base": ("{k} está sob pressão: {m}.", "{k} is under pressure: {m}."),
    "it.pecas_desprotegidas.n": ("Peças desprotegidas", "Unprotected pieces"),
    "it.pecas_desprotegidas.d": ("peças sem nenhuma proteção, ou com mais atacantes do que defensores; inclui os peões. Informativo: não altera o índice", "pieces with no protection at all, or with more attackers than defenders; pawns included. Informative: does not change the index"),
    "it.casas_desprotegidas.n": ("Casas desprotegidas", "Unprotected squares"),
    "it.casas_desprotegidas.d": ("casas das três primeiras fileiras de cada lado, sem peça própria, que nenhuma peça ou peão desse lado defende. Informativo: não altera o índice", "squares in each side's first three ranks, without an own piece, that no piece or pawn of that side defends. Informative: does not change the index"),
    "x.escapar": ("Deixou a vitória escapar.", "Let the win slip away."), "x.perdida": ("A posição ficou perdida.", "The position became lost."),
    "x.vantagem": ("Jogou fora a vantagem.", "Threw away the advantage."), "x.piorou": ("Piorou a posição.", "Made the position worse."),
    "x.melhor_era": (" O melhor era {m}{i}.", " The best was {m}{i}."),
    "x.i_mate": (", que levava ao xeque-mate em {n}", ", which led to checkmate in {n}"), "x.i_ganha": (", que ganhava {p}", ", which won {p}"),
    "x.i_xeque": (", com xeque", ", with check"), "x.i_captura": (", capturando {p}", ", capturing {p}"),
    "x.i_evita": (", que evitava a perda", ", which avoided the loss"), "x.i_evita_mate": (", que evitava o mate", ", which avoided the mate"), "x.i_vant": (", mantendo a vantagem", ", keeping the advantage"),
    "x.i_seg": (", segurando a posição", ", holding the position"), "x.i_eq": (", mantendo o equilíbrio", ", keeping the balance"),
    # ---------- explicação da avaliação da engine
    "a.eq": ("Avaliação equilibrada", "Balanced evaluation"),
    "a.lev": ("Leve vantagem das {l}", "Slight edge for {l}"), "a.clara": ("Vantagem das {l}", "{l} is better"),
    "a.dec": ("Vantagem decisiva das {l}", "{l} is winning"),
    "a.mate": ("Vantagem decisiva das {l}: mate forçado em {n}.", "{l} is winning: forced mate in {n}."),
    "a.c_perde": ("as {l} perdem {p} {w}", "{l} loses {p} {w}"),
    "a.c_material": ("as {l} estão com {d}", "{l} is {d}"),
    "a.c_pos": ("a vantagem vem de {a} e {b}", "the edge comes from {a} and {b}"), "a.c_pos1": ("a vantagem vem de {a}", "the edge comes from {a}"),
    "a.c_pos0": ("a variante principal não ganha material", "the main line wins no material"),
    "a.q_prox": ("no próximo lance", "on the next move"), "a.q_pouco": ("em poucos lances", "within a few moves"),
    "a.q_adiante": ("mais adiante na variante", "later in the main line"),
    # ---------- posicional
    "w.brancas": ("brancas", "White"), "w.pretas": ("pretas", "Black"), "w.equilibrio": ("equilíbrio", "balanced"),
    "p.mat": ("Material: as {l} estão com {d}. ", "Material: {l} is {d}. "),
    "p.eq": ("Jogo posicional equilibrado.", "The position is positionally balanced."),
    "p.vant": ("Vantagem posicional {g} das {l}", "{g} positional advantage for {l}"),
    "g.leve": ("leve", "Slight"), "g.clara": ("clara", "Clear"), "g.grande": ("grande", "Large"),
    "p.item": ("{nome} ({l})", "{nome} ({l})"),
    "it.material.n": ("Material", "Material"), "it.material.d": ("diferença de material (peão 1, cavalo 3, bispo 3, torre 5, dama 9)", "material difference (pawn 1, knight 3, bishop 3, rook 5, queen 9)"),
    "it.peoes_dobrados.n": ("Peões dobrados", "Doubled pawns"), "it.peoes_dobrados.d": ("dois peões na mesma coluna enfraquecem a estrutura", "two pawns on the same file weaken the structure"),
    "it.peoes_isolados.n": ("Peões isolados", "Isolated pawns"), "it.peoes_isolados.d": ("peões sem vizinhos nas colunas ao lado, difíceis de defender", "pawns with no neighbors on the adjacent files, hard to defend"),
    "it.peoes_passados.n": ("Peões passados", "Passed pawns"), "it.peoes_passados.d": ("peões sem peão adversário à frente que possa detê-los", "pawns with no enemy pawn ahead that can stop them"),
    "it.mobilidade.n": ("Mobilidade das peças", "Piece mobility"), "it.mobilidade.d": ("quantas casas as peças controlam", "how many squares the pieces control"),
    "it.desenvolvimento.n": ("Desenvolvimento", "Development"), "it.desenvolvimento.d": ("peças menores que ainda não saíram da fileira inicial", "minor pieces that have not left the back rank yet"),
    "it.torres.n": ("Torres ativas", "Active rooks"), "it.torres.d": ("torres em colunas abertas ou na 7ª fileira", "rooks on open files or on the 7th rank"),
    "it.centro.n": ("Controle do centro", "Center control"), "it.centro.d": ("peões e ataques sobre d4, e4, d5 e e5", "pawns and attacks on d4, e4, d5 and e5"),
    "it.espaco.n": ("Espaço", "Space"), "it.espaco.d": ("peões avançados que ganham espaço", "advanced pawns that gain space"),
    "it.par_de_bispos.n": ("Par de bispos", "Bishop pair"), "it.par_de_bispos.d": ("o lado que tem os dois bispos", "the side that has both bishops"),
    "it.seguranca_rei.n": ("Segurança do rei", "King safety"), "it.seguranca_rei.d": ("escudo de peões à frente do rei", "pawn shield in front of the king"),
    "it.rei_zona.n": ("Casas do rei sob ataque", "King-zone squares under attack"), "it.rei_zona.d": ("casas ao redor do rei atacadas por peças adversárias (as peças mais fortes pesam mais)", "squares around the king attacked by enemy pieces (stronger pieces weigh more)"),
    "it.rei_raiox.n": ("Raio-x contra o rei", "X-ray against the king"), "it.rei_raiox.d": ("peças adversárias de longo alcance apontadas para o rei com uma única peça no meio", "enemy long-range pieces aimed at the king with a single piece in between"),
    "it.rei_fuga.n": ("Casas de fuga do rei", "King escape squares"), "it.rei_fuga.d": ("casas vizinhas livres e não atacadas; poucas casas de fuga deixam o rei vulnerável a mates", "free, unattacked neighboring squares; few escape squares leave the king vulnerable to mates"),
    "it.rei_final.n": ("Rei ativo no final", "Active king in the endgame"), "it.rei_final.d": ("rei centralizado quando há poucas peças", "a centralized king when few pieces are left"),
    "it.pecas_em_risco.n": ("Peças em risco", "Pieces at risk"), "it.pecas_em_risco.d": ("peças atacadas sem defesa ou por peça de menor valor", "pieces attacked without defense or by a lower-valued piece"),
    "it.casas_fracas.n": ("Casas fracas", "Weak squares"), "it.casas_fracas.d": ("casas do meio que nenhum peão seu poderá mais defender", "central squares that none of its pawns can defend anymore"),
    "it.postos_avancados.n": ("Postos avançados", "Outposts"), "it.postos_avancados.d": ("cavalos/bispos em casa avançada, defendidos por peão e sem peão que os expulse", "knights/bishops on an advanced square, protected by a pawn and with no enemy pawn able to kick them out"),
    "g.material": ("Material", "Material"), "g.estrutura": ("Estrutura de peões", "Pawn structure"), "g.atividade": ("Atividade das peças", "Piece activity"),
    "g.rei": ("Rei", "King"), "g.debilidades": ("Debilidades", "Weaknesses"), "g.postos": ("Postos avançados", "Outposts"),
    # ---------- posição final
    "f.mate": ("Xeque-mate: vitória das {l}.", "Checkmate: {l} wins."), "f.empate": ("Fim da partida: empate.", "Game over: draw."),
    "f.faixa": ("Fim da partida", "Game over"),
    # ---------- engines / servidor / downloads
    "e.nenhuma": ("Nenhuma engine configurada. Abra \"Engines e modelo de jogadores\" e baixe o Stockfish (ou cadastre uma engine UCI sua).",
                  "No engine configured. Open \"Engines and player model\" and download Stockfish (or register your own UCI engine)."),
    "e.confira": (" (confira caminho, argumentos e opções)", " (check the path, arguments and options)"),
    "e.naoachou": ("arquivo não encontrado: {p}", "file not found: {p}"),
    "e.naouci": ("não respondeu como engine UCI: {e}", "did not respond as a UCI engine: {e}"),
    "e.falhou": ("respondeu ao UCI, mas falhou ao analisar ({e}). Confira argumentos/rede.", "answered UCI, but failed to analyze ({e}). Check the arguments/network."),
    "s.fonte": ("fonte indisponível: {e}", "source unavailable: {e}"), "s.jogo": ("jogo não encontrado", "game not found"),
    "d.iniciando": ("iniciando…", "starting…"), "d.baixando": ("baixando {a}…", "downloading {a}…"), "d.extraindo": ("extraindo…", "extracting…"),
    "d.ok": ("instalado ({v})", "installed ({v})"),
    "d.sempacote": ("sem pacote oficial para este sistema; instale pelo seu gerenciador de pacotes e cadastre em Engines",
                    "no official package for this system; install it with your package manager and register it under Engines"),
    "d.hash": ("hash diferente do informado pelo GitHub em {a}; download descartado", "hash differs from the one reported by GitHub for {a}; download discarded"),
    "d.semexe": ("baixado, mas o executável não foi encontrado", "downloaded, but the executable was not found"),
    "dl.stockfish.n": ("Stockfish", "Stockfish"), "dl.stockfish.d": ("A engine mais forte e usada como referência do índice.", "The strongest engine, used as the index reference."),
    "dl.lc0.n": ("Lc0 (Leela Chess Zero, CPU)", "Lc0 (Leela Chess Zero, CPU)"), "dl.lc0.d": ("Necessário para executar as redes Maia (modelo de jogadores).", "Needed to run the Maia networks (player model)."),
    "dl.maia.n": ("Redes Maia 1100–1900", "Maia networks 1100–1900"), "dl.maia.d": ("Pesos que imitam jogadores de cada faixa de rating.", "Weights that imitate players of each rating range."),
}
