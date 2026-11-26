/* Relatório da partida: apresentação em slides (com a voz do navegador) e documento no estilo de livro para salvar em PDF.
   Usa o que o index.html já tem: $, t, esc, api, cfg, S, LANG, pintaTab, setaMarkup, sqXY, DEST_COR, cavInicial. */
(() => {
'use strict';
const CSS = `
#rel{position:fixed;inset:0;z-index:500;background:var(--bg);display:flex;flex-direction:column}
.rel-top{display:flex;gap:8px;align-items:center;flex-wrap:wrap;padding:8px 14px;border-bottom:1px solid var(--bd);background:var(--bg2)}
.rel-top .grow{flex:1}.rel-top select{max-width:230px}
.rel-palco{flex:1;min-height:0;overflow:auto;padding:14px}
.rel-fala{position:sticky;bottom:0;margin-top:10px;background:var(--aviso-bg);border:1px solid var(--bd);border-radius:8px;padding:7px 12px;font-size:14px}
.rel-pe{display:flex;gap:10px;align-items:center;justify-content:center;padding:8px;border-top:1px solid var(--bd);background:var(--bg2);flex-wrap:wrap}
.rel-pe .pontos{display:flex;gap:5px;flex-wrap:wrap;justify-content:center;max-width:60vw}
.rel-pe .pontos i{width:10px;height:10px;border-radius:50%;background:var(--bd);cursor:pointer}.rel-pe .pontos i.on{background:var(--ac)}
table.rel-tb{border-collapse:collapse;width:100%;margin:8px 0}table.rel-tb td,table.rel-tb th{border-bottom:1px solid var(--bd);padding:4px 8px;text-align:center}
table.rel-tb td:first-child,table.rel-tb th:first-child{text-align:left}
table.rel-tb tr.destaque td{font-size:1.15em;background:#35e0c218}
table.rel-tb i.bola{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:6px}
#numeros table.rel-tb{font-size:12.5px;margin:4px 0}#numeros table.rel-tb td,#numeros table.rel-tb th{padding:2px 6px}
.prec{font-size:12.5px;border:1px solid var(--bd);border-radius:5px;padding:0 6px;margin-left:8px;cursor:help}
.rel-graf{width:100%;height:auto;background:var(--card);border:1px solid var(--bd);border-radius:8px}.rel-graf circle{cursor:pointer}
.critico{background:var(--aviso-bg);border-radius:6px;padding:7px 10px;margin:6px 0}
.critico.mini{padding:3px 8px;font-size:12.5px}
#lances b.cri{color:#e0383e;font-size:10px;margin-left:2px}`;
const estilo = document.createElement('style'); document.head.appendChild(estilo);

let R = null;                     // relatório recebido do programa
let slides = [], atual = 0, pecas = null;     // pecas: os blocos do livro, os mesmos do PDF e da versão interativa
const voz = {tocando: false, f: 0, ficha: 0, nome: localStorage.getItem('indiceVoz') || '', vel: +(localStorage.getItem('indiceVozVel') || 1)};
const temVoz = 'speechSynthesis' in window;
const q = (s, el) => (el || document).querySelector(s);

/* ---------- gráfico ---------- */
function graficoSvg(clicavel, H = 190) {
  const v = R.grafico, W = 760, n = v.length;
  if (n < 2) return '';
  const X = i => 10 + (W - 20) * i / (n - 1), Y = p => H - 10 - (H - 20) * p / 100;
  const pts = v.map((p, i) => `${X(i).toFixed(1)},${Y(p).toFixed(1)}`).join(' ');
  return `<svg class="rel-graf" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(t('Avaliação da engine ao longo da partida (acima do meio: brancas)'))}">
    <polygon points="10,${Y(50)} ${pts} ${X(n - 1)},${Y(50)}" fill="#35a98f" opacity=".22"/>
    <line x1="10" x2="${W - 10}" y1="${Y(50)}" y2="${Y(50)}" stroke="#8a93a6" stroke-dasharray="4 4"/>
    <polyline points="${pts}" fill="none" stroke="#1d8f77" stroke-width="2"/>
    ${R.marcos.map((m, k) => `<circle cx="${X(m.i)}" cy="${Y(v[m.i])}" r="5.5" fill="${m.critico ? '#e0383e' : '#e6a21e'}" stroke="#fff" ${clicavel ? `data-m="${k}"` : ''}><title>${esc(m.rotulo)}</title></circle>`).join('')}
  </svg>`;
}
const NOME_CLASSE = {brilhante: 'Brilhante', melhor: 'Melhor lance', excelente: 'Excelente', bom: 'Bom', imprecisao: 'Imprecisão', erro: 'Erro', grave: 'Erro grave'};
const DICA_PRECISAO = 'Precisão (0 a 100), pelo método do Lichess: cada lance recebe uma nota pelos pontos de chance de vitória que perdeu; o resultado junta a média que dá mais peso aos momentos agitados com a média harmônica, em que os lances ruins pesam mais. Como a engine e a profundidade são as daqui, o número pode diferir do Lichess.';
const pct = x => x == null ? '—' : num(x, 1) + '%';
/* tabela dos números da partida (usada no app, no resumo do relatório e na tabela final) */
function tabelaNumeros(N, nomeB, nomeP, {completa = true} = {}) {
  if (!N) return `<div class="mut">${t('Ainda não há lances analisados.')}</div>`;
  const B = N.B, P = N.P, v = (x, suf = '') => x == null ? '—' : x + suf;
  const l = (nome, a, b, cls = '') => `<tr class="${cls}"><td>${nome}</td><td>${a}</td><td>${b}</td></tr>`;
  const pior = x => x.pior ? `${esc(x.pior.lance)} (−${x.pior.perda})` : '—';
  let h = `<table class="rel-tb"><tr><th></th><th>${esc(nomeB)}</th><th>${esc(nomeP)}</th></tr>
    ${l(`<b>${t('Precisão')}</b>`, `<b>${pct(B.precisao)}</b>`, `<b>${pct(P.precisao)}</b>`, 'destaque')}
    ${l(t('Perda média por lance (centipeões)'), v(B.perda_cp), v(P.perda_cp))}
    ${l(t('Jogou o 1º lance da engine'), v(B.melhor_pct, '%'), v(P.melhor_pct, '%'))}
    ${Object.keys(NOME_CLASSE).filter(c => B.contagem[c] || P.contagem[c] || ['imprecisao', 'erro', 'grave'].includes(c)).map(c => l(`<i class="bola" style="background:${CLS_COR[c]}"></i>${t(NOME_CLASSE[c])}`, B.contagem[c], P.contagem[c])).join('')}
    ${l(t('Momentos críticos (achados)'), `${B.criticos} (${B.achados})`, `${P.criticos} (${P.achados})`)}`;
  if (completa) {
    h += `${l(t('Lances analisados'), B.lances, P.lances)}
      ${l(t('Chance média de acerto das posições (%)'), v(B.acerto), v(P.acerto))}
      ${l(t('Lance que mais custou (pontos de chance)'), pior(B), pior(P))}
      ${B.tempo_medio != null || P.tempo_medio != null ? l(t('Tempo médio por lance'), B.tempo_medio == null ? '—' : fmtT(B.tempo_medio), P.tempo_medio == null ? '—' : fmtT(P.tempo_medio)) : ''}`;
  }
  return h + '</table>';
}
function dadosPartida(N) {
  if (!N) return '';
  const g = N.partida, l = (a, b) => `<tr><td>${a}</td><td>${b}</td></tr>`;
  const ev = R.extremos || {};
  return `<table class="rel-tb"><tr><th>${t('A partida')}</th><th></th></tr>
    ${l(t('Resultado'), esc(R.capa.resultado === '*' ? t('em andamento') : R.capa.resultado))}
    ${R.abertura ? l(t('Abertura'), esc(R.abertura.titulo)) : ''}
    ${l(t('Número de lances'), g.lances)}
    ${g.analisados < g.total ? l(t('Meios-lances analisados'), `${g.analisados} / ${g.total}`) : ''}
    ${g.teoria_ate ? l(t('Teoria de mestres até o lance'), g.teoria_ate) : ''}
    ${l(t('Momentos críticos'), g.criticos)}${l(t('Mudanças de rumo'), g.viradas)}
    ${ev.B ? l(t('Maior avaliação a favor das brancas'), esc(ev.B)) : ''}${ev.P ? l(t('Maior avaliação a favor das pretas'), esc(ev.P)) : ''}</table>`;
}
window.tabelaNumeros = tabelaNumeros; window.DICA_PRECISAO = DICA_PRECISAO;

/* ---------- slides: um por bloco do livro, com os mesmos comentários, marcações e passadores ---------- */
function montaSlides() {
  pecas = pecasDoLivro(true, true);
  slides = [{tipo: 'topo', falas: R.falas_topo},
    ...R.livro.map((l, n) => ({tipo: 'bloco', n, l, falas: l.falas})),
    {tipo: 'lances', falas: []},
    {tipo: 'numeros', falas: R.falas_numeros}];
}
const nomeSlide = sl => sl.tipo === 'bloco' ? sl.l.titulo : t({topo: 'Resumo', lances: 'Todos os lances', numeros: 'Os números da partida'}[sl.tipo]);
function tamanho() {
  const sq = Math.floor(Math.min((innerHeight - 340) / 8, innerWidth * .46 / 8));
  q('#rel').style.setProperty('--sqs', Math.max(34, Math.min(66, sq)) + 'px');
}
function mostra(i) {
  atual = Math.max(0, Math.min(slides.length - 1, i));
  fechaJanela();
  const sl = slides[atual], palco = q('#rel .rel-palco');
  const html = sl.tipo === 'bloco' ? pecas.linhas[sl.n] : sl.tipo === 'topo' ? pecas.topo : sl.tipo === 'lances' ? pecas.lances : pecas.final;
  palco.innerHTML = `<div id="rel-sdoc" class="interativo"><div class="folha">${html}</div></div><div class="rel-fala" id="rel-fala" hidden></div>`;
  palco.scrollTop = 0; tamanho();
  ativaPassadores(q('#rel-sdoc'), dadosTabuleiros(pecas.quadros));
  q('#rel-n').textContent = `${atual + 1} / ${slides.length}`;
  q('#rel .pontos').innerHTML = slides.map((x, k) => `<i data-s="${k}" class="${k === atual ? 'on' : ''}" title="${esc(nomeSlide(x))}"></i>`).join('');
}
function vaiSlide(i) { const tocava = voz.tocando; calar(); mostra(i); if (tocava) tocar(); }

/* ---------- voz do navegador ---------- */
function vozes() {
  if (!temVoz) return [];
  const alvo = LANG === 'pt' ? 'pt' : 'en';
  return speechSynthesis.getVoices().filter(v => v.lang.toLowerCase().startsWith(alvo))
    .sort((a, b) => (b.lang === (LANG === 'pt' ? 'pt-BR' : 'en-US')) - (a.lang === (LANG === 'pt' ? 'pt-BR' : 'en-US')));
}
function listaVozes() {
  const sel = q('#rel-voz'); if (!sel) return;
  const L = vozes();
  sel.innerHTML = L.length ? L.map(v => `<option value="${esc(v.name)}">${esc(v.name)}</option>`).join('') : `<option value="">${t('voz padrão do navegador')}</option>`;
  if (L.some(v => v.name === voz.nome)) sel.value = voz.nome;
}
function botaoVoz() { const b = q('#rel-play'); if (b) b.textContent = voz.tocando ? t('⏸ Pausar') : t('▶ Ouvir'); }
function calar() { voz.ficha++; voz.tocando = false; voz.f = 0; if (temVoz) speechSynthesis.cancel(); botaoVoz(); }
function pausar() { voz.ficha++; voz.tocando = false; if (temVoz) speechSynthesis.cancel(); botaoVoz(); }   // retoma da mesma frase (a pausa nativa falha em alguns navegadores)
function tocar() { if (!temVoz) return; voz.tocando = true; botaoVoz(); fala(++voz.ficha); }
function fala(ficha) {
  if (ficha !== voz.ficha || !R) return;
  const s = slides[atual], f = s.falas[voz.f];
  if (!f) {                                          // fim do slide: passa para o próximo
    if (atual >= slides.length - 1) { calar(); return; }
    setTimeout(() => { if (ficha === voz.ficha) { voz.f = 0; mostra(atual + 1); fala(ficha); } }, 700);
    return;
  }
  const linha = q('#rel-sdoc .linha-doc');
  if (s.tipo === 'bloco' && linha && linha.ctl) {
    if (f.s !== undefined && f.k > 0) linha.ctl.passo(f.s, f.k, f.p);
    else if (f.p >= 0) linha.ctl.fixar(f.p, true);
    else linha.ctl.diagrama();
  }
  const leg = q('#rel-fala'); if (leg) { leg.hidden = false; leg.textContent = f.texto; }
  const u = new SpeechSynthesisUtterance(f.texto);
  const v = vozes().find(x => x.name === voz.nome) || vozes()[0];
  if (v) u.voice = v;
  u.lang = v ? v.lang : (LANG === 'pt' ? 'pt-BR' : 'en-US'); u.rate = voz.vel;
  u.onend = () => { if (ficha === voz.ficha) { voz.f++; setTimeout(() => fala(ficha), 180); } };
  u.onerror = e => {
    if (ficha !== voz.ficha || e.error === 'canceled' || e.error === 'interrupted') return;
    pausar(); if (leg) leg.textContent = t('O navegador não conseguiu usar a voz ({e}). Tente outra voz.', {e: e.error});
  };
  voz.utt = u;                                       // mantém a referência: alguns navegadores descartam a fala antes do fim
  speechSynthesis.speak(u);
}

/* ---------- o livro: PDF paginado (sem sobra de página) e versão interativa com passador ---------- */
/* Desenha os tabuleiros do livro e liga os passadores. Não depende de nada do programa: o código desta função vai
   junto no arquivo .html baixado, que funciona sozinho em qualquer navegador. */
function ativaPassadores(raiz, D) {
  const CORES = {B: '#35e0c2', P: '#b388ff', D: '#ff2d2d'};
  const xy = sq => { const f = sq.charCodeAt(0) - 97, r = 8 - +sq[1]; return D.flip ? [7 - f, 7 - r] : [f, r]; };
  const rects = casas => (casas || []).map(([sq, lado, tipo]) => {
    const [x, y] = xy(sq), c = CORES[lado] || CORES.B;
    return tipo === 'tinta' ? `<rect x="${x}" y="${y}" width="1" height="1" fill="${c}" opacity=".35"/>`
      : `<rect x="${x + .04}" y="${y + .04}" width=".92" height=".92" rx=".1" fill="${c}" fill-opacity=".22" stroke="${c}" stroke-width=".09"/>`;
  }).join('');
  const setas = (lista, ocupadas, grande) => (lista || []).map(([a, b, cor, ordem]) => {
    const [x1, y1] = xy(a), [x2, y2] = xy(b), A = [x1 + .5, y1 + .5], Z = [x2 + .5, y2 + .5];
    const L = Math.hypot(Z[0] - A[0], Z[1] - A[1]) || 1, ux = (Z[0] - A[0]) / L, uy = (Z[1] - A[1]) / L;
    /* a seta fica abaixo das peças: se a casa de chegada está ocupada, a ponta para na borda da peça; entre casas
       vizinhas ela encurta para caber no vão */
    const ocupado = !!(ocupadas && ocupadas.has(b)), recuo = ocupado ? .38 : 0, larg = ocupado ? .21 : .19;
    const h = ocupado ? Math.max(.26, Math.min(.35, L - recuo - .34)) : .35;
    const P = [Z[0] - ux * recuo, Z[1] - uy * recuo], E = [P[0] - ux * h, P[1] - uy * h];
    /* o número fica no trecho livre; numa seta curta ele sai para o lado, para não sumir debaixo das peças */
    const curta = L < 1.6, meio = curta ? [(A[0] + Z[0]) / 2 - uy * .36, (A[1] + Z[1]) / 2 + ux * .36] : [(A[0] + E[0]) / 2, (A[1] + E[1]) / 2];
    const num = ordem ? `<circle cx="${meio[0]}" cy="${meio[1]}" r="${grande ? .26 : .19}" fill="#fff" stroke="${cor}" stroke-width=".05"/><text x="${meio[0]}" y="${meio[1] + (grande ? .13 : .095)}" text-anchor="middle" font-size="${grande ? .38 : .27}" font-weight="700" font-family="Segoe UI,sans-serif" fill="#111">${ordem}</text>` : '';
    return `<line x1="${A[0]}" y1="${A[1]}" x2="${E[0]}" y2="${E[1]}" stroke="${cor}" stroke-width=".13" stroke-linecap="round" opacity=".95"/><polygon points="${P[0]},${P[1]} ${E[0] - uy * larg},${E[1] + ux * larg} ${E[0] + uy * larg},${E[1] - ux * larg}" fill="${cor}"/>${num}`;
  }).join('');
  const CHEIAS = {K: '\u265A', Q: '\u265B', R: '\u265C', B: '\u265D', N: '\u265E', P: '\u265F'};
  const VAZADAS = {K: '\u2654', Q: '\u2655', R: '\u2656', B: '\u2657', N: '\u2658', P: '\u2659'};
  /* a peça no estilo escolhido em Aparência; os cavalos da metade esquerda olham para dentro, como no programa */
  function peca(p, coluna, mini) {
    const branca = p === p.toUpperCase(), tipo = p.toUpperCase(), estilo = D.estilo;
    const olha = D.cav === 'todos' || (D.cav === 'pretos' && !branca);
    const vira = tipo === 'N' && estilo !== 'letras' && olha && coluna < 4;
    let miolo;
    if (estilo === 'vetor' && D.pecas) miolo = D.pecas[p];
    else if (estilo === 'letras') miolo = `<circle cx="22.5" cy="22.5" r="17" fill="${branca ? '#f5f5f5' : '#222'}" stroke="${branca ? '#000' : '#ddd'}" stroke-width="2"/><text x="22.5" y="30" text-anchor="middle" font-family="Georgia,serif" font-weight="700" font-size="21" fill="${branca ? '#111' : '#f5f5f5'}">${tipo}</text>`;
    else {
      const glifo = (estilo === 'contorno' && branca ? VAZADAS : CHEIAS)[tipo] + '\uFE0E';
      const cor = estilo === 'contorno' ? ['#000', 'none', 0] : estilo === 'neon' ? (branca ? ['#e4fbff', '#1199ee', 1.6] : ['#ffc2ce', '#e01144', 1.6])
        : (branca ? ['#ffffff', '#000000', mini ? 5.4 : 3.2] : mini ? ['#000000', '#000000', 1.2] : ['#161616', '#ffffff', .7]);
      miolo = `<text x="22.5" y="23" text-anchor="middle" dominant-baseline="central" font-family="'Segoe UI Symbol','DejaVu Sans',sans-serif" font-size="${mini ? 44 : 41}" fill="${cor[0]}" stroke="${cor[1]}" stroke-width="${cor[2]}"${estilo === 'classico' && !branca ? ' stroke-opacity=".55"' : ''} stroke-linejoin="round" style="paint-order:stroke">${glifo}</text>`;
    }
    return `<span class="p"${vira ? ' style="transform:scaleX(-1)"' : ''}><svg viewBox="0 0 45 45">${miolo}</svg></span>`;
  }
  function desenha(el, fen, op) {
    const linhas = fen.split(' ')[0].split('/').map(l => [].concat(...[...l].map(c => /\d/.test(c) ? Array(+c).fill('') : [c])));
    const ult = op.ult || [];
    const mini = !(el.parentElement && el.parentElement.classList.contains('fig'));   // miniatura: contorno mais forte
    el.ocupadas = new Set();
    linhas.forEach((l, r) => l.forEach((p, c) => { if (p) el.ocupadas.add('abcdefgh'[c] + (8 - r)); }));
    let h = '';
    for (let r = 0; r < 8; r++) for (let c = 0; c < 8; c++) {
      const fr = D.flip ? 7 - r : r, fc = D.flip ? 7 - c : c, p = linhas[fr][fc], nome = 'abcdefgh'[fc] + (8 - fr);
      h += `<div class="c ${(r + c) % 2 ? 'd' : 'l'}${ult.includes(nome) ? ' ult' : ''}">${D.coord && c === 0 ? `<i class="r">${8 - fr}</i>` : ''}${D.coord && r === 7 ? `<i class="f">${'abcdefgh'[fc]}</i>` : ''}${p ? peca(p, c, mini) : ''}</div>`;
    }
    const cores = D.cores ? ` style="--clara:${D.cores[0]};--escura:${D.cores[1]}"` : '';
    el.innerHTML = `<div class="rl-tab"${cores}>${h}<svg class="seta" viewBox="0 0 8 8">${rects(op.casas)}${setas(op.setas, el.ocupadas, op.grande)}</svg><svg class="seta rl-camada" viewBox="0 0 8 8"></svg></div>`;
  }
  raiz.querySelectorAll('.rtab[data-q]').forEach(el => {
    const q = D.quadros[+el.dataset.q];
    desenha(el, q.fen, q);
    if (D.parado || !el.parentElement.classList.contains('fig')) return;     // miniaturas e PDF: só o desenho
    const linha = el.closest('.linha-doc');
    if (!linha) return;
    const ctl = linha.querySelector('.passador'), onde = linha.querySelector('.onde');
    const seqs = q.seqs || [];
    const principal = seqs.length ? {s: 0, k: q.inicial >= 0 ? q.inicial : seqs[0].passos.length - 1} : {s: 0, k: 0};
    let s = principal.s, k = principal.k, fora = false, fixo = -1;
    const escreve = x => { if (onde) onde.textContent = x; };
    const acende = n => {
      linha.querySelectorAll('p[data-p]').forEach(x => x.classList.toggle('on', +x.dataset.p === n));
      const alvo = linha.querySelector(`p[data-p="${n}"]`);
      if (alvo && alvo.closest('#rel-sdoc')) alvo.scrollIntoView({block: 'nearest'});
    };
    const botoes = () => { if (ctl) ctl.querySelectorAll('[data-seq]').forEach(b => b.classList.toggle('on', fora && +b.dataset.seq === s)); };
    function diagrama() { fixo = -1; fora = false; s = principal.s; k = principal.k; desenha(el, q.fen, q); escreve(D.txt.diagrama); acende(-1); botoes(); }
    /* um passo de uma linha do passador (n = comentário que fica aceso) */
    function passo(sn, kn, n) {
      if (!seqs[sn]) return;
      s = sn; k = Math.max(0, Math.min(seqs[sn].passos.length - 1, kn)); fora = true;
      const seq = seqs[s], p = seq.passos[k];
      desenha(el, p.fen, {ult: p.uci ? [p.uci.slice(0, 2), p.uci.slice(2, 4)] : [],
        setas: !p.uci && seq.passos[1] ? [[seq.passos[1].uci.slice(0, 2), seq.passos[1].uci.slice(2, 4), seq.cor]] : []});
      escreve((p.rotulo || D.txt.inicio) + ` (${k}/${seq.passos.length - 1})`);
      acende(n === undefined ? fixo : n); botoes();
    }
    /* as marcas de um comentário, na posição a que ele se refere */
    function fixar(n, semAlternar) {
      if (fixo === n && !semAlternar) return diagrama();
      const m = q.marcas && q.marcas[n];
      if (!m) { diagrama(); fixo = n; acende(n); return; }
      fixo = n;
      const temLinha = m.seq !== undefined && m.seq !== null && seqs[m.seq];
      if (temLinha) { s = m.seq; k = 0; fora = true; } else { fora = false; s = principal.s; k = principal.k; }
      const temMarcas = (m.casas && m.casas.length) || (m.setas && m.setas.length) || m.fen;
      if (!temMarcas && temLinha) return passo(m.seq, 0, n);
      desenha(el, m.fen || (temLinha ? seqs[m.seq].passos[0].fen : q.fen), {casas: m.casas || [], setas: m.setas || []});
      escreve(m.nota || (temLinha ? seqs[m.seq].rotulo : D.txt.marcado));
      acende(n); botoes();
    }
    linha.ctl = {fixar, passo, diagrama};
    linha.addEventListener('click', e => {
      const par = e.target.closest('p[data-p]');
      if (par) fixar(+par.dataset.p);
    });
    linha.addEventListener('mouseover', e => {        // passar o mouse num lance ou casa em negrito marca este tabuleiro
      const m = e.target.closest('.mc'), sobre = el.querySelector('svg.rl-camada'); if (!m || !sobre || !m.dataset.c || m.dataset.f) return;
      const lado = m.dataset.l || 'B', u = m.dataset.s;
      sobre.innerHTML = rects(m.dataset.c.split(',').map(c => [c, lado, m.dataset.t || 'anel'])) + (u ? setas([[u.slice(0, 2), u.slice(2, 4), CORES[lado] || CORES.B]], el.ocupadas) : '');
    });
    linha.addEventListener('mouseout', e => { if (e.target.closest('.mc')) { const sobre = el.querySelector('svg.rl-camada'); if (sobre) sobre.innerHTML = ''; } });
    if (!ctl || !seqs.length) return;
    ctl.addEventListener('click', e => {
      const b = e.target.closest('button'); if (!b) return;
      fixo = -1;
      if (b.dataset.seq !== undefined) return passo(+b.dataset.seq, 0, -1);
      if (b.dataset.a === 'diag') return diagrama();
      const max = seqs[s].passos.length - 1;
      const base = fora ? k : principal.k;
      passo(s, b.dataset.a === 'ini' ? 0 : b.dataset.a === 'fim' ? max : base + (b.dataset.a === 'prox' ? 1 : -1), -1);
    });
    escreve(D.txt.diagrama);
  });
  if (!D.parado) janelaDeLances();

  /* slides e livro interativo: passar o mouse num lance abre um tabuleiro pequeno com a posição; clicar o fixa;
     o ✕, um clique fora ou Esc fecham. Os ouvintes são do documento e são postos uma única vez. */
  function janelaDeLances() {
    raiz.querySelectorAll('.mc[data-f]').forEach(m => { m.title = ''; });    // sem a dica do comentário por cima da janela
    let J = document.rlJanela;
    if (J) { J.D = D; J.desenha = desenha; return; }
    J = document.rlJanela = {D, desenha, alvo: null, fixa: false};
    const caixa = () => document.getElementById('rl-pop');
    const lance = e => { const m = e.target && e.target.closest ? e.target.closest('.mc[data-f]') : null; return m && m.closest('#rel-sdoc, #rel-doc.interativo') ? m : null; };
    J.fecha = () => { const p = caixa(); if (p) p.remove(); J.alvo = null; J.fixa = false; };
    J.abre = (alvo, fixa) => {
      J.fecha(); J.alvo = alvo; J.fixa = fixa;
      const fen = alvo.dataset.f, u = alvo.dataset.s || '', campos = fen.split(' '), n = +campos[5] || 1;
      const rotulo = (campos[1] === 'b' ? n + '.' : (n - 1) + '\u2026') + alvo.textContent.replace(/[!?]+$/, '');
      const p = document.createElement('div'); p.id = 'rl-pop'; if (fixa) p.className = 'fixa';
      p.innerHTML = '<div class="rl-pop-tit"><b></b><button type="button">✕</button></div><div class="fig"><div class="rtab"></div></div>' + (fixa ? '' : '<div class="rl-pop-dica"></div>');
      p.querySelector('b').textContent = J.D.txt.apos.replace('{x}', rotulo);
      p.querySelector('button').title = J.D.txt.fechar; p.querySelector('button').onclick = J.fecha;
      if (!fixa) p.querySelector('.rl-pop-dica').textContent = J.D.txt.fixar;
      document.body.appendChild(p);
      const casa = [u.slice(0, 2), u.slice(2, 4)];
      J.desenha(p.querySelector('.rtab'), fen, u ? {ult: casa, setas: [[casa[0], casa[1], CORES[campos[1] === 'b' ? 'B' : 'P']]]} : {});
      const r = alvo.getBoundingClientRect(), w = p.offsetWidth, h = p.offsetHeight, f = 8;
      let x = r.right + 14, y = Math.min(Math.max(f, r.top + r.height / 2 - h / 2), innerHeight - h - f);
      if (x + w > innerWidth - f) x = r.left - w - 14;
      if (x < f) { x = Math.max(f, Math.min(r.left, innerWidth - w - f)); y = r.bottom + 10 + h < innerHeight ? r.bottom + 10 : Math.max(f, r.top - h - 10); }
      p.style.left = x + 'px'; p.style.top = Math.max(f, y) + 'px';
    };
    document.addEventListener('mouseover', e => { const m = lance(e); if (m && !J.fixa && J.alvo !== m) J.abre(m, false); }, true);
    document.addEventListener('mouseout', e => { const m = lance(e); if (m && !J.fixa && !(e.relatedTarget && m.contains(e.relatedTarget))) J.fecha(); }, true);
    document.addEventListener('click', e => {
      const m = lance(e);
      if (m) {                                       // fixa a janela, sem acionar o comentário em volta
        e.stopPropagation(); e.preventDefault(); J.abre(m, true);
        document.dispatchEvent(new CustomEvent('rl-fixou'));
        return;
      }
      if (caixa() && !(e.target.closest && e.target.closest('#rl-pop'))) J.fecha();
    }, true);
    document.addEventListener('scroll', () => { if (!J.fixa) J.fecha(); }, true);
    document.addEventListener('keydown', e => { if (e.key === 'Escape') J.fecha(); });
  }
}

const CSS_DOC = `
.rtab>div{position:relative;display:grid;grid-template-columns:repeat(8,var(--sq));grid-template-rows:repeat(8,var(--sq));width:max-content;user-select:none}
#rel-doc{position:fixed;inset:0;z-index:600;overflow:auto;background:#6b7280}
#rel-doc .barra-doc{position:sticky;top:0;z-index:5;display:flex;gap:10px;align-items:center;flex-wrap:wrap;padding:8px 14px;background:var(--bg2,#0e1420);color:var(--tx,#e6edf7);border-bottom:1px solid var(--bd,#26324a);font:13px "Segoe UI",system-ui,sans-serif}
:is(#rel-doc,#rel-sdoc) .folha{--clara:#f0d9b5;--escura:#b58863;color:#111;font:11.3px/1.4 Georgia,"Times New Roman",serif}
:is(#rel-doc,#rel-sdoc,#rl-pop) .c{position:relative;display:flex;align-items:center;justify-content:center;font-size:calc(var(--sq)*.8);line-height:1}
:is(#rel-doc,#rel-sdoc,#rl-pop) .c.l{background:var(--clara)}:is(#rel-doc,#rel-sdoc,#rl-pop) .c.d{background:var(--escura)}
:is(#rel-doc,#rel-sdoc,#rl-pop) .c.ult::after{content:"";position:absolute;inset:0;background:rgba(255,213,0,.38)}
:is(#rel-doc,#rel-sdoc,#rl-pop) .c i{position:absolute;z-index:3;font:600 calc(var(--sq)*.2)/1 "Segoe UI",sans-serif;opacity:.85}:is(#rel-doc,#rel-sdoc,#rl-pop) .c i.r{left:1px;top:1px}:is(#rel-doc,#rel-sdoc,#rl-pop) .c i.f{right:1px;bottom:0}
:is(#rel-doc,#rel-sdoc,#rl-pop) .c.l i{color:var(--escura)}:is(#rel-doc,#rel-sdoc,#rl-pop) .c.d i{color:var(--clara)}
:is(#rel-doc,#rel-sdoc,#rl-pop) .p{position:relative;z-index:2;display:block;width:96%;height:96%;line-height:0}
:is(#rel-doc,#rel-sdoc,#rl-pop) .p svg{display:block;width:100%;height:100%;overflow:visible}
:is(#rel-doc,#rel-sdoc,#rl-pop) svg.seta{position:absolute;inset:0;width:100%;height:100%;z-index:1;pointer-events:none}:is(#rel-doc,#rel-sdoc,#rl-pop) svg.rl-camada{z-index:3;opacity:.9}
#rl-pop{position:fixed;z-index:900;background:#fff;color:#111;border:1px solid #6b7280;border-radius:8px;box-shadow:0 8px 30px #0008;padding:7px 8px;font:12px "Segoe UI",system-ui,sans-serif;text-align:left}
#rl-pop.fixa{border:2px solid #0f9d84}
#rl-pop .rl-pop-tit{display:flex;gap:10px;align-items:center;justify-content:space-between;margin-bottom:5px}
#rl-pop .rl-pop-tit button{border:0;background:none;color:#444;font-size:13px;cursor:pointer;padding:0 2px}
#rl-pop .fig{margin:0;padding:1px}#rl-pop .rtab{--sq:30px;--clara:#f0d9b5;--escura:#b58863}#rl-pop .rtab>div{outline:1px solid #000}
#rl-pop .rl-pop-dica{font-size:10.5px;color:#555;margin-top:5px;max-width:240px}
:is(#rel-doc.interativo,#rel-sdoc) .mc[data-f]{cursor:pointer;border-radius:3px}:is(#rel-doc.interativo,#rel-sdoc) .mc[data-f]:hover{background:#cdeee6}
:is(#rel-doc,#rel-sdoc) .rl-ref{display:inline-block;min-width:13px;height:13px;border-radius:7px;background:#1f2937;color:#fff;font:700 9px/13px "Segoe UI",sans-serif;text-align:center;font-style:normal;margin-right:4px;vertical-align:1px;-webkit-print-color-adjust:exact;print-color-adjust:exact}
:is(#rel-doc,#rel-sdoc) .marcas-pdf{display:flex;flex-wrap:wrap;gap:6px 8px;align-items:flex-start;padding:4px 0 6px}
:is(#rel-doc,#rel-sdoc) .marcas-pdf figure{margin:0;--sq:14px;width:calc(var(--sq)*8 + 2px);padding:1px}
:is(#rel-doc,#rel-sdoc) .marcas-pdf .c i{display:none}
:is(#rel-doc,#rel-sdoc) .marcas-pdf figcaption{font-size:9px;line-height:1.2;margin-top:2px}
:is(#rel-doc,#rel-sdoc) h1{font-size:21px;margin:0}:is(#rel-doc,#rel-sdoc) .sub{font-size:11.5px;color:#333}
:is(#rel-doc,#rel-sdoc) h2{font-size:15px;border-bottom:2px solid #111;padding-bottom:2px;margin:10px 0 8px}
:is(#rel-doc,#rel-sdoc) h3{font-size:13px;margin:0}:is(#rel-doc,#rel-sdoc) h4{font-size:10px;text-transform:uppercase;letter-spacing:.6px;color:#555;margin:0 0 2px}
:is(#rel-doc,#rel-sdoc) .topo{display:flex;gap:14px;margin:8px 0 6px;align-items:stretch}
:is(#rel-doc,#rel-sdoc) .precisoes{flex:0 0 190px;border:1px solid #999;border-radius:6px;padding:5px 9px}
:is(#rel-doc,#rel-sdoc) .precisoes>div{font-size:10px;text-transform:uppercase;letter-spacing:.6px;color:#555}
:is(#rel-doc,#rel-sdoc) .precisoes p{margin:5px 0 0;line-height:1.15}:is(#rel-doc,#rel-sdoc) .precisoes span{display:block;font-size:10.5px}:is(#rel-doc,#rel-sdoc) .precisoes b{font-size:19px}
:is(#rel-doc,#rel-sdoc) .graf{flex:1;min-width:0}:is(#rel-doc,#rel-sdoc) .leg-graf{font-size:9.5px;color:#444}
:is(#rel-doc,#rel-sdoc) svg.rel-graf{width:100%;height:auto;background:#fff;border:1px solid #999;border-radius:6px}
:is(#rel-doc,#rel-sdoc) .fio{background:#f3f4f6;border-radius:6px;padding:5px 10px;margin-bottom:4px}:is(#rel-doc,#rel-sdoc) .fio ul{margin:0;padding-left:16px}:is(#rel-doc,#rel-sdoc) .fio p{margin:0 0 3px}
:is(#rel-doc,#rel-sdoc) .linha-doc{display:flex;gap:14px;align-items:flex-start;padding:7px 0 5px;border-top:1px solid #bbb}
:is(#rel-doc,#rel-sdoc) .linha-doc>.fig{flex:0 0 calc(var(--sq)*8 + 4px)}:is(#rel-doc,#rel-sdoc) .linha-doc>div{flex:1;min-width:0}
:is(#rel-doc,#rel-sdoc) .fig{margin:0;padding:2px;overflow:hidden;--sq:27px}:is(#rel-doc,#rel-sdoc) .linha-doc{--sq:27px}
/* contorno no lugar da borda e recorte: a borda do tabuleiro seguinte vazava para o pé da página anterior na impressão */
:is(#rel-doc,#rel-sdoc) .rtab>div{border:0;outline:1px solid #000;overflow:hidden;contain:paint}:is(#rel-doc,#rel-sdoc) .linha-doc .fig{--sq:inherit}
:is(#rel-doc,#rel-sdoc) figcaption{font-size:9.5px;color:#333;margin-top:3px;line-height:1.3}
:is(#rel-doc,#rel-sdoc) .linha-doc p{margin:3px 0}:is(#rel-doc,#rel-sdoc) .meta{font-size:10px;color:#444}
:is(#rel-doc,#rel-sdoc) .rot{font-weight:700;font-style:italic;color:#444}:is(#rel-doc,#rel-sdoc) p.foco .rot{font-style:normal;color:#14532d}
:is(#rel-doc,#rel-sdoc) .selo{font-size:9.5px;font-weight:700;color:#555;text-transform:uppercase;letter-spacing:.5px}
:is(#rel-doc,#rel-sdoc) .linha-doc.lv-momento .selo{color:#b3261e}:is(#rel-doc,#rel-sdoc) .linha-doc.lv-variante .selo{color:#146c43}
:is(#rel-doc,#rel-sdoc) .mc{font-weight:700;border:0;padding:0;background:none}
:is(#rel-doc,#rel-sdoc) .tira{display:flex;gap:6px;justify-content:space-between;padding:2px 2px 6px}
:is(#rel-doc,#rel-sdoc) .tira figure{margin:0;--sq:15.6px;text-align:center}:is(#rel-doc,#rel-sdoc) .tira .c i{display:none}
:is(#rel-doc,#rel-sdoc) .tira figcaption{font-size:9px;margin-top:2px}
:is(#rel-doc,#rel-sdoc) .tira:not(:has(figure:nth-child(4))){justify-content:flex-start;gap:14px}
:is(#rel-doc,#rel-sdoc) .linha-doc.lv-variante~div .tira figure{--sq:15px}  /* no bloco recuado cabem 5 sem cortar */
:is(#rel-doc,#rel-sdoc) .tira.coluna{justify-content:flex-start;gap:8px;padding-bottom:0}
:is(#rel-doc,#rel-sdoc) .tira-tit{font-size:9.5px;color:#555;text-transform:uppercase;letter-spacing:.5px;margin:0 0 2px;border-top:1px dotted #bbb;padding-top:3px}
:is(#rel-doc,#rel-sdoc) .colunas{column-count:4;column-gap:16px;column-rule:1px solid #ccc;font-size:9.8px}
:is(#rel-doc,#rel-sdoc) .par{display:grid;grid-template-columns:20px 1fr 1fr;break-inside:avoid;line-height:1.45}:is(#rel-doc,#rel-sdoc) .par i{color:#555;font-style:normal}:is(#rel-doc,#rel-sdoc) .par small{color:#555;font-size:8.6px}
:is(#rel-doc,#rel-sdoc) .nota-lances,:is(#rel-doc,#rel-sdoc) .rodape{font-size:9px;color:#444;margin-top:4px}
:is(#rel-doc,#rel-sdoc) .final p{margin:2px 0 6px}
:is(#rel-doc,#rel-sdoc) .duas{display:grid;grid-template-columns:minmax(0,1.55fr) minmax(0,1fr);gap:16px;align-items:start}
:is(#rel-doc,#rel-sdoc) table{border-collapse:collapse;width:100%;font-size:10px}:is(#rel-doc,#rel-sdoc) td,:is(#rel-doc,#rel-sdoc) th{border-bottom:1px solid #ccc;padding:1px 4px;text-align:center}
:is(#rel-doc,#rel-sdoc) table.rel-tb{margin:0}:is(#rel-doc,#rel-sdoc) table.rel-tb tr.destaque td{font-size:1.1em;background:#35e0c218}
:is(#rel-doc,#rel-sdoc) table.rel-tb i.bola{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:6px}
:is(#rel-doc,#rel-sdoc) table.rel-tb td:first-child,:is(#rel-doc,#rel-sdoc) table.rel-tb th:first-child{text-align:left}
/* páginas A4: a medida na tela é a mesma da impressão (182 x 273 mm) */
:is(#rel-doc,#rel-sdoc) .papel{width:794px;margin:16px auto;background:#fff;padding:45px 53px;box-sizing:border-box;box-shadow:0 4px 24px #0006}
:is(#rel-doc,#rel-sdoc) .pagina{width:688px;height:1024px;overflow:hidden;display:flex;flex-direction:column}
:is(#rel-doc,#rel-sdoc) .pagina>.unidade,:is(#rel-doc,#rel-sdoc) .medidor>.unidade{display:flow-root;flex:0 0 auto}
:is(#rel-doc,#rel-sdoc) .pagina.justa{justify-content:space-between}
:is(#rel-doc,#rel-sdoc) .medidor{position:absolute;left:-9999px;top:0;width:688px}
/* livro interativo: uma coluna contínua, com o passador embaixo de cada tabuleiro */
:is(#rel-doc,#rel-sdoc).interativo .folha{max-width:940px;margin:16px auto;background:#fff;padding:26px 30px;font-size:14px}
:is(#rel-doc,#rel-sdoc).interativo .linha-doc{--sq:40px;padding:14px 0}
:is(#rel-doc,#rel-sdoc).interativo h3{font-size:16px}:is(#rel-doc,#rel-sdoc).interativo .meta,:is(#rel-doc,#rel-sdoc).interativo figcaption{font-size:12px}:is(#rel-doc,#rel-sdoc).interativo .selo{font-size:11px}
:is(#rel-doc,#rel-sdoc) .passador{margin-top:6px;font:12px "Segoe UI",system-ui,sans-serif}
:is(#rel-doc,#rel-sdoc) .passador .botoes,:is(#rel-doc,#rel-sdoc) .passador .linhas{display:flex;gap:4px;flex-wrap:wrap}:is(#rel-doc,#rel-sdoc) .passador .linhas{margin-top:5px}
:is(#rel-doc,#rel-sdoc) .passador button{font:600 13px "Segoe UI Symbol","Segoe UI",sans-serif;background:#eef2ff;color:#1e3a8a;border:1px solid #93a3d8;border-radius:5px;padding:4px 0;cursor:pointer;flex:1}
:is(#rel-doc,#rel-sdoc) .passador .linhas button{flex:1 1 100%;text-align:left;padding:3px 8px;font-size:11.5px;background:#fff}
:is(#rel-doc,#rel-sdoc) .passador button.on{background:#1e3a8a;color:#fff}:is(#rel-doc,#rel-sdoc) .passador .onde{font-weight:700;margin-top:5px;min-height:17px}
@media(max-width:700px){:is(#rel-doc,#rel-sdoc).interativo .linha-doc{flex-direction:column;align-items:center;--sq:min(40px,11vw)}:is(#rel-doc,#rel-sdoc) .colunas{column-count:2}:is(#rel-doc,#rel-sdoc) .duas{grid-template-columns:1fr}:is(#rel-doc,#rel-sdoc) .topo{flex-direction:column}:is(#rel-doc,#rel-sdoc) .precisoes{flex:0 0 auto}}
/* comentários clicáveis e itens recuados (variantes, ideias, deslizes, golpes) */
:is(#rel-doc,#rel-sdoc) p.item{margin:2px 0 2px 12px;padding:1px 0 1px 8px;border-left:3px solid #cbd5e1}
:is(#rel-doc,#rel-sdoc) p.cab{margin-bottom:1px}
:is(#rel-doc,#rel-sdoc) p[data-p]{cursor:pointer;border-radius:4px}
:is(#rel-doc,#rel-sdoc) p.item.item{border-radius:0}
:is(#rel-doc,#rel-sdoc) p[data-p]:hover{background:#eef6ff}
:is(#rel-doc,#rel-sdoc) p[data-p].on{background:#fff3bf}
:is(#rel-doc,#rel-sdoc) .chaves{font-size:9.5px;color:#444;margin-top:3px}
:is(#rel-doc,#rel-sdoc) .chaves i{display:inline-block;width:9px;height:9px;border-radius:2px;margin:0 3px 0 8px;vertical-align:middle}
/* a variante é um item do momento acima: o bloco inteiro (tabuleiro, texto e miniaturas) entra com recuo e uma linha-guia.
   A classe repetida dá prioridade sobre as regras do livro interativo e dos slides. */
:is(#rel-doc,#rel-sdoc) .linha-doc.lv-variante.lv-variante{margin-left:40px;padding-left:12px;border-left:3px solid #8fcfa9}
:is(#rel-doc,#rel-sdoc) .linha-doc.lv-variante~div{margin-left:40px;padding-left:12px;border-left:3px solid #8fcfa9}
@media(max-width:700px){:is(#rel-doc,#rel-sdoc) .linha-doc.lv-variante.lv-variante,:is(#rel-doc,#rel-sdoc) .linha-doc.lv-variante~div{margin-left:12px;padding-left:6px}}
/* nos slides: o bloco ocupa a tela, o tabuleiro fica grande e os comentários rolam ao lado */
#rel-sdoc .folha{max-width:1240px;margin:0 auto;background:#fff;border-radius:10px;padding:14px 22px;font-size:15px}
#rel-sdoc.interativo .linha-doc{--sq:var(--sqs,46px);border:0;padding:0;gap:24px}
#rel-sdoc.interativo .linha-doc>div:last-child{max-height:calc(100vh - 185px);overflow:auto;padding-right:8px}
#rel-sdoc.interativo h3{font-size:21px;margin-bottom:2px}#rel-sdoc .linha-doc p{margin:6px 0}
#rel-sdoc .colunas{font-size:13px}#rel-sdoc .par small{font-size:11px}#rel-sdoc table{font-size:13px}
#rel-sdoc h1{font-size:28px}#rel-sdoc .fio{font-size:15px}#rel-sdoc svg.rel-graf circle{cursor:pointer}
@media(max-width:820px){#rel-sdoc.interativo .linha-doc{flex-direction:column;align-items:center;--sq:min(46px,11vw)}#rel-sdoc.interativo .linha-doc>div:last-child{max-height:none}}
@page{size:A4;margin:12mm 14mm}
@media print{
  body.rel-imprimindo{background:#fff!important;margin:0}
  body.rel-imprimindo>*:not(#rel-doc){display:none!important}
  body.rel-imprimindo #rel-doc{position:static;overflow:visible;background:#fff}
  body.rel-imprimindo #rel-doc .barra-doc,body.rel-imprimindo #rel-doc .passador{display:none}
  body.rel-imprimindo #rel-doc .folha{margin:0;padding:0;max-width:none}
  body.rel-imprimindo #rel-doc .papel{width:auto;margin:0;padding:0;box-shadow:none;break-after:page}
  body.rel-imprimindo #rel-doc .papel:last-child{break-after:auto}
  body.rel-imprimindo #rel-doc.interativo .linha-doc{break-inside:avoid;--sq:27px}
  body.rel-imprimindo #rel-doc *{-webkit-print-color-adjust:exact;print-color-adjust:exact}
}`;

function listaCompacta(tabela) {                      // todos os lances em colunas, um número por linha
  const nums = new Map();
  tabela.forEach(l => { if (!nums.has(l.n)) nums.set(l.n, {}); nums.get(l.n)[l.brancas ? 'b' : 'p'] = l; });
  const meio = l => l ? `<span><b>${l.critico ? '◆' : ''}<span${l.fen ? ` class="mc" data-f="${esc(l.fen)}" data-s="${esc(l.uci)}"` : ''}>${esc(l.san)}</span></b> <small>${esc(l.aval)}</small></span>` : '<span>…</span>';
  return `<div class="colunas">${[...nums].map(([n, x]) => `<div class="par"><i>${n}.</i>${meio(x.b)}${x.p ? meio(x.p) : '<span></span>'}</div>`).join('')}</div>`;
}
const legendaCores = L => L.map(([cor, x]) => `<span style="white-space:nowrap"><span style="display:inline-block;width:14px;height:4px;background:${cor};vertical-align:middle"></span> ${esc(x)}</span>`).join(' · ');

/* os pedaços do livro, iguais no PDF e na versão interativa */
function pecasDoLivro(interativo, clicavel) {
  const c = R.capa, N = R.numeros, prec = x => N && N[x].precisao != null ? pct(N[x].precisao) : '—';
  const quadros = [];
  const quadro = q => quadros.push(q) - 1;
  const topo = `<h1>${esc(c.brancas)} ${c.elo_b ? `(${esc(c.elo_b)})` : ''} × ${esc(c.pretas)} ${c.elo_p ? `(${esc(c.elo_p)})` : ''}</h1>
    <div class="sub">${esc(c.detalhe)}</div>${c.parcial ? `<div><b>${esc(c.parcial)}</b></div>` : ''}
    <div class="topo"><div class="precisoes"><div>${t('Precisão')}</div><p><span>${esc(c.brancas)}</span><b>${prec('B')}</b></p><p><span>${esc(c.pretas)}</span><b>${prec('P')}</b></p></div>
      <div class="graf">${graficoSvg(!!clicavel, 150)}<div class="leg-graf">${t('Avaliação da engine ao longo da partida (acima do meio: brancas)')}</div></div></div>
    <div class="fio"><h4>${t('O fio da partida')}</h4><p>${esc(R.fases)} <b>${esc(R.desfecho)}</b></p><ul>${R.fio.map(x => `<li>${x}</li>`).join('')}</ul></div>
    <div class="chaves">${interativo ? '' : `<span class="rl-ref">a</span> ${t('liga o comentário ao tabuleiro pequeno com as marcações dele')} · `}${t('Marcações no tabuleiro:')}<i style="background:#35e0c2"></i>${t('brancas')}<i style="background:#b388ff"></i>${t('pretas')}<i style="background:#ff2d2d"></i>${t('ataque ou peça mal defendida')}<i style="background:#1e9e5a"></i>${t('melhor lance')}${interativo ? ' · ' + t('Clique num comentário para ver as marcações dele.') : ''}</div>`;
  const minis = [];
  const linhas = R.livro.map((l, n) => {
    const marcas = l.paragrafos.map(p => p.cab ? null : (p.marca || p.seq != null ? {...(p.marca || {}), seq: p.seq} : null));
    const impressas = interativo ? {letra: {}, figuras: []} : marcasImpressas(l, marcas, quadro);
    minis.push(impressas.figuras);
    const id = quadro({fen: l.fen, setas: l.setas, casas: l.casas, ult: l.ult, seqs: interativo ? l.seqs : null, inicial: l.inicial, marcas});
    const ctl = interativo && l.seqs.length ? `<div class="passador"><div class="botoes"><button data-a="ini" title="${esc(t('Começo'))}">⏮</button><button data-a="ant" title="${esc(t('Lance anterior'))}">◀</button><button data-a="diag" title="${esc(t('Voltar ao diagrama'))}">◉</button><button data-a="prox" title="${esc(t('Próximo lance'))}">▶</button><button data-a="fim" title="${esc(t('Fim'))}">⏭</button></div>
      <div class="onde"></div><div class="linhas">${l.seqs.map((s, k) => `<button data-seq="${k}" style="border-left:4px solid ${s.cor}">${esc(s.rotulo)}</button>`).join('')}</div></div>` : '';
    return `<section class="linha-doc lv-${l.tipo}"><div class="fig" style="flex:0 0 calc(var(--sq)*8 + 4px)"><div class="rtab" data-q="${id}"></div><figcaption><b>${t('Diagrama {n}', {n: n + 1})}</b> — ${esc(l.figura)}${l.legenda.length ? '<br>' + legendaCores(l.legenda) : ''}</figcaption>${ctl}</div>
      <div><div class="selo">${esc(l.selo)}</div><h3>${esc(l.titulo)}</h3>${l.meta ? `<div class="meta">${esc(l.meta)}</div>` : ''}
      ${l.paragrafos.map((p, k) => `<p class="${p.foco ? 'foco ' : ''}${p.item ? 'item ' : ''}${p.cab ? 'cab' : ''}"${interativo && marcas[k] ? ` data-p="${k}" title="${esc(t('Clique para ver no tabuleiro'))}"` : ''}${p.item && p.cor ? ` style="border-left-color:${p.cor}"` : ''}>${impressas.letra[k] ? `<span class="rl-ref">${impressas.letra[k]}</span>` : ''}${p.rotulo ? `<span class="rot"${p.cor ? ` style="color:${p.cor}"` : ''}>${esc(p.rotulo)}.</span> ` : ''}${p.html}</p>`).join('')}</div></section>`;
  });
  const lances = `<h2>${t('Todos os lances')}</h2>${listaCompacta(R.tabela)}<div class="nota-lances">◆ ${t('momento crítico')} · ${t('o número é a avaliação antes do lance (positivo: brancas)')}</div>`;
  const final = `<div class="final"><h2>${t('Tabela final: os números da partida')}</h2><p>${esc(R.conclusao.texto)}</p><div class="duas">${tabelaNumeros(N, c.brancas, c.pretas)}${dadosPartida(N)}</div>
    <div class="rodape">${t(DICA_PRECISAO)} ${t('Relatório gerado pelo Chesslyst.')}</div></div>`;
  return {topo, linhas, minis, lances, final, quadros, quadro};
}
/* o que um comentário marca e o diagrama principal não mostra: no papel não há clique nem mouse, então cada marcação
   vira um tabuleiro pequeno, ligado ao comentário por uma letra. Marcações iguais dividem o mesmo tabuleiro. */
function marcasImpressas(l, marcas, quadro) {
  const letra = {}, feitas = new Map(), figuras = [], maiuscula = x => x.charAt(0).toUpperCase() + x.slice(1), lugar = fen => fen.split(' ')[0];
  const casaNoDiagrama = c => (l.casas || []).some(x => x[0] === c[0] && x[1] === c[1]);
  const setaNoDiagrama = s => !s[3] && (l.setas || []).some(x => x[0] === s[0] && x[1] === s[1]);
  let grupo = '';
  l.paragrafos.forEach((p, k) => {
    if (p.cab) { grupo = p.rotulo; return; }
    if (!p.item) grupo = '';
    const m = marcas[k]; if (!m) return;
    const casas = m.casas || [], setas = m.setas || [], fen = m.fen || l.fen, mesma = lugar(fen) === lugar(l.fen);
    if (!casas.length && !setas.length && mesma) return;
    if (mesma && casas.every(casaNoDiagrama) && setas.every(setaNoDiagrama)) return;      // já está no diagrama
    const chave = JSON.stringify([lugar(fen), casas.map(String).sort(), setas.map(String).sort()]);
    let f = feitas.get(chave);
    if (!f) {
      const nome = String.fromCharCode(97 + figuras.length % 26);
      f = {nome, quadro: quadro({fen, casas, setas, ult: mesma ? l.ult : [], grande: true}), titulos: [], nota: m.nota || ''};
      feitas.set(chave, f); figuras.push(f);
    }
    const titulo = p.rotulo || grupo;
    if (titulo && !f.titulos.includes(titulo)) f.titulos.push(titulo);
    letra[k] = f.nome;
  });
  return {letra, figuras: figuras.map(f => `<figure><div class="rtab" data-q="${f.quadro}"></div><figcaption><span class="rl-ref">${f.nome}</span>${esc(maiuscula([f.titulos.join(' / '), f.nota].filter(Boolean).join(' · ') || t('Marcações do comentário')))}</figcaption></figure>`)};
}
function dadosTabuleiros(quadros) { return {estilo: cfg.peca, cav: cfg.cav, cores: [cfg.clara, cfg.escura], pecas: cfg.peca === 'vetor' ? window.PECAS_SVG : null, flip: !!cfg.flip, coord: !!cfg.coord, quadros, txt: {diagrama: t('Posição do diagrama'), inicio: t('Começo da linha'), marcado: t('Marcações do comentário'), apos: t('Posição após {x}', {x: '{x}'}), fixar: t('Clique no lance para fixar esta janela.'), fechar: t('Fechar (Esc)')}}; }

/* miniaturas: as posições do caminho que levam ao diagrama (ou que a engine mostra a partir dele) */
function tiraDaLinha(l, quadro) {
  const seq = l.tipo === 'momento' ? (l.seqs[1] || l.seqs[0]) : l.seqs[0];
  if (!seq || seq.passos.length < 3) return '';
  const p = seq.passos.slice(1), n = Math.min(5, p.length);
  const escolhidos = [...new Set(Array.from({length: n}, (_, i) => Math.round((i + 1) * p.length / n) - 1))].map(i => p[i]);
  return `<div class="tira-tit">${esc(l.tipo === 'momento' ? seq.rotulo : (l.tipo === 'variante' ? t('A linha, passo a passo') : t('O caminho até o diagrama')))}</div><div class="tira">${escolhidos.map(x =>
    `<figure><div class="rtab" data-q="${quadro({fen: x.fen, ult: [x.uci.slice(0, 2), x.uci.slice(2, 4)]})}"></div><figcaption>${esc(x.rotulo)}</figcaption></figure>`).join('')}</div>`;
}
/* ao lado do tabuleiro, quando o texto é curto: os primeiros lances de uma linha daquele momento, em miniaturas */
function tiraNaColuna(l, quadro, n) {
  const seq = l.tipo === 'momento' ? (l.seqs[2] || l.seqs[1]) : l.seqs[0];
  if (!seq || seq.passos.length < 2) return '';
  const p = seq.passos.slice(1, n + 1);
  const rotulo = l.tipo === 'momento' ? seq.rotulo : (l.tipo === 'variante' ? t('A linha, passo a passo') : t('O caminho até o diagrama'));
  const escolhidos = l.tipo === 'momento' || l.tipo === 'variante' ? p
    : Array.from({length: Math.min(n, seq.passos.length - 1)}, (_, i) => seq.passos[Math.round((i + 1) * (seq.passos.length - 1) / (Math.min(n, seq.passos.length - 1) + 1))]);
  return `<div class="tira-tit">${esc(rotulo)}</div><div class="tira coluna">${escolhidos.map(x =>
    `<figure><div class="rtab" data-q="${quadro({fen: x.fen, ult: [x.uci.slice(0, 2), x.uci.slice(2, 4)]})}"></div><figcaption>${esc(x.rotulo)}</figcaption></figure>`).join('')}</div>`;
}
/* "a partida em imagens": completa o que sobrar de uma página */
function tiraDaPartida(imagens, quadro) {
  return `<div class="tira">${imagens.map(x => `<figure><div class="rtab" data-q="${quadro({fen: x.fen, ult: [x.uci.slice(0, 2), x.uci.slice(2, 4)]})}"></div><figcaption>${esc(x.rotulo)}</figcaption></figure>`).join('')}</div>`;
}

/* distribui os blocos em páginas A4 e usa o espaço que sobra: miniaturas do caminho, tabuleiros maiores e imagens da partida */
function pagina(doc, P) {
  const H = 1022, folha = q('.folha', doc);
  const medidor = document.createElement('div'); medidor.className = 'medidor'; folha.appendChild(medidor);
  const D = {...dadosTabuleiros(P.quadros), parado: true};      // a prévia mostra exatamente o que vai para o arquivo
  const unidade = (html, linha) => { const u = document.createElement('div'); u.className = 'unidade'; u.innerHTML = html; u.linha = linha; medidor.appendChild(u); ativaPassadores(u, D); return u; };
  const alt = u => u.getBoundingClientRect().height;
  const unidades = [unidade(P.topo), ...P.linhas.map((h, i) => unidade(h, R.livro[i])), unidade(P.lances), unidade(P.final)];
  const preencheColuna = u => {                     // vão ao lado do tabuleiro: miniaturas do tamanho que couber, sem aumentar o bloco
    if (u.coluna) return;
    const fig = q('.linha-doc > .fig', u), texto = fig.nextElementSibling;
    const vao = alt(fig) - alt(texto), largura = texto.getBoundingClientRect().width;
    const sq = Math.min(18, Math.floor((vao - 36) / 8 * 2) / 2);      // 36 px: título, legenda e folgas
    if (sq < 9) return;
    const n = Math.min(5, Math.floor((largura + 8) / (8 * sq + 10)));
    for (const tam of [sq, sq - 1]) {
      const html = tiraNaColuna(u.linha, P.quadro, n); if (!html) return;
      const antes = alt(u), extra = document.createElement('div'); extra.innerHTML = html;
      extra.querySelectorAll('figure').forEach(f => f.style.setProperty('--sq', tam + 'px'));
      texto.appendChild(extra); ativaPassadores(extra, D);
      if (alt(u) <= antes + 2) { u.coluna = true; return; }
      extra.remove();
    }
  };
  /* as marcações dos comentários entram sempre: no vão ao lado do tabuleiro e, o que não couber, embaixo do bloco */
  const poeMarcas = (u, figuras) => {
    if (!figuras.length) return;
    const fig = q('.linha-doc > .fig', u), texto = fig.nextElementSibling;
    const monta = (naColuna, lado) => {                      // naColuna: quantas vão ao lado do tabuleiro
      u.querySelectorAll('.marcas-pdf').forEach(x => x.remove());
      [[texto, figuras.slice(0, naColuna)], [u, figuras.slice(naColuna)]].forEach(([onde, lote]) => {
        if (!lote.length) return;
        const caixa = document.createElement('div'); caixa.className = 'marcas-pdf'; caixa.innerHTML = lote.join('');
        if (lado) caixa.querySelectorAll('figure').forEach(f => f.style.setProperty('--sq', lado + 'px'));
        onde.appendChild(caixa); ativaPassadores(caixa, D);
      });
      return alt(u);
    };
    let cabem = 0;
    while (cabem < figuras.length) {                         // quantas cabem no vão sem aumentar o bloco
      monta(cabem + 1);
      if (alt(texto) > alt(fig) + 2) break;
      cabem++;
    }
    const opcoes = [...new Set([cabem, figuras.length, 0])].map(n => [monta(n), n]).sort((a, b) => a[0] - b[0] || b[1] - a[1]);
    monta(opcoes[0][1]);
    if (alt(u) > H) monta(opcoes[0][1], 12);                 // um bloco nunca passa de uma página
  };
  unidades.filter(u => u.linha).forEach(u => poeMarcas(u, P.minis[R.livro.indexOf(u.linha)] || []));
  unidades.filter(u => u.linha).forEach(preencheColuna);
  const paginas = [[]]; let usado = 0;
  unidades.forEach(u => { const h = alt(u); if (usado + h > H && paginas[paginas.length - 1].length) { paginas.push([]); usado = 0; } paginas[paginas.length - 1].push(u); usado += h; });
  const soma = pg => pg.reduce((a, u) => a + alt(u), 0);
  let imagem = 0;                                     // as imagens seguem a ordem da partida
  const usadas = [];
  paginas.forEach((pg, n) => {
    const linhas = pg.filter(u => u.linha);
    // 1) miniaturas do caminho, uma por bloco, enquanto couberem
    for (const u of linhas) {
      if (u.coluna) continue;
      const html = tiraDaLinha(u.linha, P.quadro); if (!html) continue;
      const extra = document.createElement('div'); extra.innerHTML = html; u.appendChild(extra); ativaPassadores(extra, D);
      if (soma(pg) > H) extra.remove();
    }
    // 2) tabuleiros um pouco maiores
    for (let sq = 28; sq <= 32; sq++) {
      for (const u of linhas.filter(x => !x.coluna)) {
        const s = q('.linha-doc', u), antes = s.style.getPropertyValue('--sq');
        s.style.setProperty('--sq', sq + 'px');
        if (soma(pg) > H) { if (antes) s.style.setProperty('--sq', antes); else s.style.removeProperty('--sq'); }
      }
    }
    linhas.filter(u => !u.querySelector('.tira')).forEach(preencheColuna);   // tabuleiros maiores abrem vãos novos
    // 3) o que ainda sobrar recebe a partida em imagens
    let primeira = true;
    const total = R.imagens.length;
    while (total && H - soma(pg) > 128) {
      const cabem = Math.max(1, Math.floor((H - soma(pg) - (primeira ? 36 : 0)) / 146));
      if (primeira) { var passo = Math.max(1, Math.floor(total / Math.min(total, cabem * 5))); imagem = 0; }
      const lote = [];
      while (lote.length < 5 && imagem < total) { const k = Math.min(total - 1, imagem + passo - 1); lote.push(R.imagens[k]); imagem += passo; }
      if (!lote.length) break;
      const u = unidade((primeira ? `<h2>${t('A partida em imagens')}</h2>` : '') + tiraDaPartida(lote, P.quadro));
      const antes_do_fim = pg.findIndex(x => q('.final', x));     // na última página, as imagens ficam antes da tabela final
      const onde = antes_do_fim >= 0 ? antes_do_fim : pg.length;
      pg.splice(onde, 0, u);
      if (soma(pg) > H) { pg.splice(onde, 1); u.remove(); break; }
      primeira = false; usadas.push(n);
    }
  });
  const sobras = paginas.map(pg => H - soma(pg));    // medidas com os blocos ainda na tela
  const montadas = paginas.map((pg, n) => {
    const papel = document.createElement('div'); papel.className = 'papel';
    const el = document.createElement('div'); el.className = 'pagina';
    if (sobras[n] < 160 && pg.length > 1) el.classList.add('justa');   // sobra pequena: reparte entre os blocos
    papel.appendChild(el); pg.forEach(u => el.appendChild(u));
    return papel;
  });
  folha.innerHTML = '';
  montadas.forEach(x => folha.appendChild(x));
  return paginas.length;
}

function montaDocumento(interativo) {
  pausar(); fechaDocumento();
  const c = R.capa, doc = document.createElement('div'); doc.id = 'rel-doc'; if (interativo) doc.className = 'interativo';
  const P = pecasDoLivro(interativo);
  doc.innerHTML = `<div class="barra-doc">${interativo
    ? `<button class="pri" id="rd-baixa">${t('💾 Baixar o livro interativo')}</button><button id="rd-outro">${t('📄 Ver o PDF')}</button><button id="rd-volta">${t('← Voltar aos slides')}</button><span class="mut">${t('Use os botões embaixo de cada tabuleiro. O arquivo baixado abre em qualquer navegador.')}</span>`
    : `<button class="pri" id="rd-imprime">${t('🖨 Salvar como PDF')}</button><button id="rd-outro">${t('📖 Livro interativo')}</button><button id="rd-volta">${t('← Voltar aos slides')}</button><span class="mut">${t('Na janela de impressão, escolha o destino “Salvar como PDF”.')}</span>`}</div>
    <div class="folha">${interativo ? P.topo + P.linhas.join('') + P.lances + P.final : ''}</div>`;
  document.body.appendChild(doc);
  if (interativo) ativaPassadores(doc, dadosTabuleiros(P.quadros)); else pagina(doc, P);
  const nome = `${t('Relatório')} - ${c.brancas} x ${c.pretas}`.replace(/[\\/:*?"<>|]+/g, '-');
  q('#rd-volta', doc).onclick = fechaDocumento;
  q('#rd-outro', doc).onclick = () => montaDocumento(!interativo);
  if (interativo) q('#rd-baixa', doc).onclick = () => {
    const url = URL.createObjectURL(new Blob([arquivoInterativo()], {type: 'text/html'}));
    const a = document.createElement('a'); a.href = url; a.download = nome + '.html'; document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 4000);
  };
  else q('#rd-imprime', doc).onclick = () => {
    const titulo = document.title;
    document.title = nome;                            // vira o nome sugerido do arquivo
    document.body.classList.add('rel-imprimindo');
    const fim = () => { document.body.classList.remove('rel-imprimindo'); document.title = titulo; removeEventListener('afterprint', fim); };
    addEventListener('afterprint', fim);
    setTimeout(() => window.print(), 60);
  };
}
/* um único arquivo .html, sem depender do programa nem da internet */
function arquivoInterativo() {
  const P = pecasDoLivro(true), c = R.capa;
  const dados = JSON.stringify(dadosTabuleiros(P.quadros)).replace(/</g, '\\u003c');
  return `<!doctype html><html lang="${LANG === 'pt' ? 'pt-BR' : 'en'}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>${esc(c.brancas)} × ${esc(c.pretas)} — ${t('Relatório')}</title>
<style>body{margin:0;background:#6b7280}${CSS_DOC}
#rel-doc{position:static;overflow:visible}</style></head><body>
<div id="rel-doc" class="interativo"><div class="folha">${P.topo + P.linhas.join('') + P.lances + P.final}</div></div>
<script>${ativaPassadores.toString()}
ativaPassadores(document, ${dados});<` + `/script></body></html>`;
}
const abreDocumento = () => montaDocumento(false);
const fechaJanela = () => { if (document.rlJanela) document.rlJanela.fecha(); };
document.addEventListener('rl-fixou', () => { if (voz.tocando) pausar(); });   // quem fixa um lance assume: a narração pausa
function fechaDocumento() { fechaJanela(); const d = q('#rel-doc'); if (d) d.remove(); document.body.classList.remove('rel-imprimindo'); }

/* ---------- janela do relatório ---------- */
async function busca() {
  const d = await api('/api/relatorio', {id: S.job});
  if (!d || d.erro) { status(t('Erro: {e}', {e: (d && d.erro) || '?'})); return false; }
  R = d; montaSlides(); return true;
}
function fecha() { calar(); fechaDocumento(); const el = q('#rel'); if (el) el.remove(); R = null; }
async function abre() {
  if (!S.job || !S.rows.length) { status(t('Analise a partida primeiro: o relatório usa a análise já feita.')); return; }
  if (!await busca()) return;
  const el = document.createElement('div'); el.id = 'rel';
  el.innerHTML = `<div class="rel-top"><b style="font:700 20px Georgia,serif;color:var(--ac)">${t('Relatório')}</b>
    <div class="grow"></div>
    ${temVoz ? `<button class="pri" id="rel-play"></button><button id="rel-stop" title="${esc(t('Parar o áudio'))}">⏹</button><select id="rel-voz" title="${esc(t('Voz do navegador'))}"></select>
      <select id="rel-vel" title="${esc(t('Velocidade da voz'))}">${[0.8, 0.9, 1, 1.15, 1.3, 1.5].map(v => `<option value="${v}">${num(v, 2)}×</option>`).join('')}</select>`
      : `<span class="mut">${t('Este navegador não tem voz.')}</span>`}
    <button id="rel-livro">${t('📖 Livro interativo')}</button><button id="rel-pdf">${t('📄 Montar PDF')}</button><button id="rel-x" title="${esc(t('Fechar (Esc)'))}">✕</button></div>
    <div class="rel-palco"></div>
    <div class="rel-pe"><button id="rel-ant">◀</button><span id="rel-n"></span><button id="rel-prox">▶</button><div class="pontos"></div></div>`;
  document.body.appendChild(el);
  q('#rel-x').onclick = fecha; q('#rel-pdf').onclick = abreDocumento; q('#rel-livro').onclick = () => montaDocumento(true);
  q('#rel-ant').onclick = () => vaiSlide(atual - 1); q('#rel-prox').onclick = () => vaiSlide(atual + 1);
  if (temVoz) {
    q('#rel-play').onclick = () => voz.tocando ? pausar() : tocar();
    q('#rel-stop').onclick = () => { calar(); mostra(atual); };
    listaVozes(); speechSynthesis.onvoiceschanged = listaVozes;
    q('#rel-voz').onchange = e => { voz.nome = e.target.value; localStorage.setItem('indiceVoz', voz.nome); if (voz.tocando) { pausar(); tocar(); } };
    q('#rel-vel').value = String(voz.vel);
    q('#rel-vel').onchange = e => { voz.vel = +e.target.value; localStorage.setItem('indiceVozVel', voz.vel); if (voz.tocando) { pausar(); tocar(); } };
    botaoVoz();
  }
  el.addEventListener('click', e => {
    const d = e.target.closest('.pontos i'); if (d) return vaiSlide(+d.dataset.s);
    const g = e.target.closest('circle[data-m]');
    if (g) {                                          // ponto do gráfico: abre o slide daquele momento
      const i = R.marcos[+g.dataset.m].i, k = slides.findIndex(x => x.l && x.l.tipo === 'momento' && x.l.i === i);
      if (k >= 0) vaiSlide(k);
      return;
    }
    if (e.target.closest('p[data-p], .passador button')) pausar();   // quem clica assume o tabuleiro: a narração pausa
  });
  /* o passar do mouse dentro do relatório não mexe no tabuleiro do programa, que está atrás */
  el.addEventListener('mouseover', e => e.stopPropagation());
  el.addEventListener('mouseout', e => e.stopPropagation());
  mostra(0);
}
/* com o relatório aberto, o teclado é dele (as setas não mexem na partida por trás) */
addEventListener('keydown', e => {
  if (!q('#rel')) return;
  if (e.key === 'Escape') { if (q('#rl-pop')) fechaJanela(); else if (q('#rel-doc')) fechaDocumento(); else fecha(); }
  else if (e.target.closest && e.target.closest('select,input,textarea')) return;
  else if (!q('#rel-doc') && (e.key === 'ArrowRight' || e.key === 'PageDown')) vaiSlide(atual + 1);
  else if (!q('#rel-doc') && (e.key === 'ArrowLeft' || e.key === 'PageUp')) vaiSlide(atual - 1);
  else return;
  e.preventDefault(); e.stopImmediatePropagation();
}, true);
addEventListener('resize', () => { if (q('#rel')) tamanho(); });
addEventListener('pagehide', () => { if (temVoz) speechSynthesis.cancel(); });
estilo.textContent = CSS + CSS_DOC;
const bt = document.getElementById('b-relatorio'); if (bt) bt.onclick = abre;
})();
