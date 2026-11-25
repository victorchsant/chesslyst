# Chesslyst

**Chance de acerto no xadrez / Chance of finding the move, in chess**

Chesslyst analisa partidas de xadrez e mostra, a cada posição, quatro índices com uma leitura em linguagem natural (português e inglês):

| Índice | O que mede |
|---|---|
| **Engine** | a avaliação original da engine (Stockfish ou outra UCI), sem alteração |
| **Chance de Acerto** | a probabilidade de um jogador do nível (rating) do lado que joga encontrar um lance bom ali, calibrada com partidas reais |
| **Posição** | avaliação estática: material, estrutura de peões, atividade, segurança do rei, debilidades e postos avançados |
| **Jogada** | a qualidade do lance que acabou de ser jogado, com a explicação do que ele fez ("perdeu um cavalo na troca", "permitiu xeque-mate em 2"…) |

A interface é uma página HTML servida por um pequeno servidor local em Python. As engines rodam nativamente (não em WebAssembly).

## Como usar

### Opção 0: online, sem instalar nada
Abra **https://victorchsant.github.io/chesslyst/** em um navegador moderno. O programa roda inteiro no seu navegador (Python e Stockfish em WebAssembly), sem servidor: nada da sua análise sai do seu computador, e é gratuito. Limites desta versão: o Stockfish em WebAssembly é mais lento que o instalado, não há o modelo Maia (a Chance de Acerto usa uma estimativa feita a partir das avaliações da engine) e na primeira abertura são baixados cerca de 15 MB.

### Opção 1: Windows, com o `Chesslyst.exe` (recomendada)
Baixe o `Chesslyst.exe` na página de [Releases](https://github.com/victorchsant/chesslyst/releases) e dê dois cliques. **Não precisa instalar o Python.** O programa abre a interface no navegador e se encerra sozinho depois que você fecha a página.
- Engines baixadas, configurações e caches ficam em `%LOCALAPPDATA%\Chesslyst`.
- Como o `.exe` não é assinado digitalmente, o Windows (SmartScreen) ou o antivírus podem avisar na primeira vez: use *Mais informações → Executar assim mesmo*. O código-fonte completo está neste repositório, e você mesmo pode gerar o `.exe` com `python app/exe/construir.py`.

### Opção 2: com o Python, em qualquer sistema (`Chesslyst.pyw`)
Requer **Python 3.10+** e internet na primeira execução.

- **Windows:** abra o `Chesslyst.pyw` **com o Python** (dois cliques se os arquivos `.pyw` já estiverem associados a ele; senão, botão direito → *Abrir com* → Python).
- **Linux e macOS** (ou pelo terminal): `python Chesslyst.pyw`. Com `--terminal` o programa mostra o que o servidor imprime.

Na primeira vez o programa cria uma pasta `.venv`, instala o `python-chess` e abre a interface no navegador. Nada é instalado fora da pasta do projeto.

### Engines (nas duas opções)
Em **🖥 Engines**, baixe o Stockfish (e, se quiser o modelo de jogadores, o Lc0 com as redes Maia) ou cadastre qualquer engine UCI que você já tenha. O Lc0 só tem pacote oficial pronto no Windows; em Linux e macOS instale-o por conta própria ou use só o Stockfish.

### Fontes de partidas
PGN colado ou arquivo · partida do Lichess (por ID, inclusive ao vivo) · transmissões de torneios do Lichess.

### Relatório da partida
Depois de analisar, **📑 Relatório** monta, a partir da análise já feita:
- **Slides** com os mesmos diagramas, comentários e passadores do PDF e do livro interativo, e **áudio com a voz do navegador**, que destaca o comentário lido e mostra as marcações dele;
- **marcações por comentário:** nos slides e no livro interativo, clicar num comentário mostra no tabuleiro as casas e setas dele (nas variantes, setas numeradas), na posição a que ele se refere. No PDF, cada marcação é impressa num **tabuleiro pequeno ligado ao comentário por uma letra**, e a prévia mostra exatamente o que será salvo;
- nos slides e no livro interativo, passar o mouse num lance abre uma **janela com a posição**; clicar a fixa;
- variantes recuadas, como itens do momento a que pertencem;
- **PDF** no estilo de livro (tabuleiro à esquerda, explicação à direita), com as páginas preenchidas por miniaturas dos lances, salvo pela janela de impressão (*Salvar como PDF*);
- **Livro interativo**: um único arquivo `.html`, que abre em qualquer navegador, com um passador em cada tabuleiro;
- o relatório segue a *Aparência* escolhida (estilo das peças e cores do tabuleiro);
- **focos por fase**, escolhidos pelo programa: abertura (desenvolvimento, centro, mobilidade, peças protegidas), meio-jogo (táticas, rei, debilidades, peças soltas, mobilidade) e final (táticas, atividade do rei, estrutura de peões, material). Nem toda partida chega ao final;
- o relatório conta **como a partida terminou** em empate por repetição, onde ela saiu da teoria e as reflexões mais longas no relógio; no momento crítico com um só lance, mostra **por que a segunda opção falha**;
- **tabela final** com os números da partida.

### Momento Crítico e precisão
- **Momento Crítico:** só um lance resolve a posição e ele não é óbvio, ou o lance jogado muda o rumo da partida.
- **Precisão** de cada jogador (0 a 100), pelo método usado pelo Lichess: nota de cada lance pelos pontos de chance de vitória perdidos, combinando a média ponderada pela oscilação da avaliação com a média harmônica. Como a engine e a profundidade podem ser outras, o número pode diferir do Lichess.
- Quando um ganho, uma perda ou um mate só se decide numa **linha mais longa**, o texto escreve a variante da engine.
- O texto só diz que um lado ganha material quando a avaliação da engine confirma; uma retomada é descrita como troca. Numa troca desigual, a frase diz o que se ganha e o que se entrega.
- Na notação, **★** é o primeiro lance da engine e **✓** um lance excelente; os sinais **!!**, **?!**, **?** e **??** marcam brilhantes, imprecisões e erros.

As ideias, as fases e os focos são identificados por regras sobre a análise da engine: descrevem ações concretas, mas não reconhecem planos estratégicos longos.

### Recursos
- Lances e casas citados nas explicações aparecem em negrito e são marcados no tabuleiro.
- Nos **lances de variantes** da interpretação e das linhas de cálculo, passar o mouse abre uma **janela pequena com a posição**; clicar a fixa, e o ✕, um clique fora ou Esc a fecham.
- Posição em detalhes, com bispos ruins, mobilidade dos cavalos, ilhas, peões isolados e passados e peças desprotegidas.
- Navegação pelos lances sem depender da análise; linhas de cálculo clicáveis (a variante aparece no tabuleiro).
- Várias engines ao mesmo tempo, com aviso quando divergem.
- Tempo de relógio (`[%clk]`) considerado na chance de acerto, quando o PGN traz.
- Temas de tabuleiro e peças, tema claro/escuro, layouts configuráveis, atalhos de teclado (← → Home End, `F` vira o tabuleiro).
- Teoria de abertura (Lichess) e finais com tabela Syzygy (Lichess): apenas a posição (FEN) é enviada.

## Segurança e privacidade
O servidor escuta somente em `127.0.0.1`, recusa pedidos de outros sites e só executa engines cadastradas por você. Nenhum dado seu é enviado, a não ser a posição (FEN) nas consultas de teoria e finais ao Lichess.

## Estrutura
```
Chesslyst.pyw              launcher multiplataforma: o único arquivo para abrir o programa
README.md  LICENSE  .gitignore
app/
  server.py                servidor local e API
  indice/                  núcleo: fórmula, explicações, posição, engines, Lichess, aberturas
  web/                     interface (HTML, JS)
  calibracao/              parâmetros calibrados (acerto, tempo) e pesos do índice de posição
  exemplos/                partida de demonstração (uso sem internet)
  testes/test_core.py      testes do núcleo
  exe/                     como gerar o Chesslyst.exe (PyInstaller): exe_main.py e construir.py
  online/                  versão online (GitHub Pages): webserver.py, shim.js, construir_site.py e publicar.py
  requirements.txt
```
O que o programa cria ao rodar (ambiente `.venv`, engines baixadas, `engines.json`, caches e `servidor.log`) fica dentro de `app/` (ou, no `.exe`, em `%LOCALAPPDATA%\Chesslyst`) e não vai para o Git.

## Limites
O índice mede a dificuldade **objetiva** do lance; não vê estado emocional, cansaço nem preparação. As redes Maia só vão até 1900; acima disso o ajuste vem da calibração. Itens do Índice de Posição marcados com † têm peso definido por regra, não confirmado pelos dados.

## Licença e créditos
Chesslyst é software livre sob a **GNU GPL-3.0** (veja [LICENSE](LICENSE)).

Desenvolvido por **Víctor Chaves Santos** com o **Claude** (Anthropic, modelo Claude Sonnet 5.5), em novembro de 2026.

O desenho vetorial das peças, opcional em *Aparência* (`app/web/pecas.js`), é o conjunto de **Colin M.L. Burnett** (GFDL, BSD e GPL), gerado a partir do python-chess.

Componentes de terceiros (não redistribuídos aqui; cada um segue sua licença):
- [python-chess](https://github.com/niklasf/python-chess), GPL-3.0, instalado via `pip`
- [Stockfish](https://github.com/official-stockfish/Stockfish), GPL-3.0, baixado pelo usuário
- [Lc0](https://github.com/LeelaChessZero/lc0), GPL-3.0, baixado pelo usuário
- [Maia](https://github.com/CSSLab/maia-chess), redes de pesos baixadas pelo usuário (veja a licença do projeto)
- [Lichess](https://lichess.org) API aberta, para transmissões, teoria e tablebase

---

## English

Chesslyst analyses chess games and shows four indices per position, each with a plain-language reading (Portuguese and English): the original **engine** evaluation, the **chance of finding the move** for a player of the given rating, a static **position** score, and the quality of the **last move** with an explanation of what it did. The UI is an HTML page served by a small local Python server; engines run natively.

After the analysis, **Report** builds narrated slides (browser voice), a book-style PDF and a standalone interactive HTML book with a step-through control on each board, with phase-based focuses, critical moments, player accuracy (Lichess method) and a final table of game numbers.

**Run:** On Windows, download `Chesslyst.exe` from Releases (no Python needed) or, with Python 3.10+, open `Chesslyst.pyw` with Python (double-click if `.pyw` files are associated with it, otherwise right-click → *Open with* → Python), or run `python Chesslyst.pyw` (Linux/macOS). On first run it creates a `.venv` and installs `python-chess`. Then, in the **Engines** window, download Stockfish (and optionally Lc0 with the Maia networks) or register any UCI engine.

**License:** GNU GPL-3.0. Built by Víctor Chaves Santos with Claude (Anthropic, Claude Sonnet 5.5), November 2026.
