/* Relatório da partida: apresentação em slides (com a voz do navegador) e documento no estilo de livro para salvar em PDF.
   Usa o que o index.html já tem: $, t, esc, api, cfg, S, LANG, pintaTab, setaMarkup, sqXY, DEST_COR, cavInicial. */
(() => {
'use strict';
const CSS = `
#rel{position:fixed;inset:0;z-index:500;background:var(--bg);display:flex;flex-direction:column}
.rel-top{display:flex;gap:8px;align-items:center;flex-wrap:wrap;padding:8px 14px;border-bottom:1px solid var(--bd);background:var(--bg2)}
.rel-top .grow{flex:1}.rel-top select{max-width:230px}
.rel-palco{flex:1;min-height:0;overflow:auto;padding:14px}
.rel-slide{display:grid;grid-template-columns:max-content minmax(280px,640px);gap:24px;justify-content:center;align-items:start}
.rel-slide.so{grid-template-columns:minmax(280px,860px)}
.rel-col{position:sticky;top:0}
.rtab>div{position:relative;display:grid;grid-template-columns:repeat(8,var(--sq));grid-template-rows:repeat(8,var(--sq));border:2px solid #000;border-radius:3px;width:max-content;user-select:none}
.rtab svg.rhover{z-index:3;opacity:.92}
.rel-leg{display:flex;gap:14px;flex-wrap:wrap;font-size:12.5px;margin-top:6px;max-width:calc(var(--sq)*8)}
.rel-leg i{display:inline-block;width:18px;height:5px;border-radius:3px;vertical-align:middle;margin-right:5px}
.rel-passo{min-height:20px;margin-top:4px;font-weight:600}
.rel-texto h2{margin:0 0 4px;font:700 24px Georgia,serif}.rel-texto h3{margin:14px 0 4px;font-size:12px;text-transform:uppercase;letter-spacing:.6px;color:var(--mut)}
.rel-texto ul{margin:4px 0;padding-left:18px}.rel-texto li{margin-bottom:6px}
.rel-selo{display:inline-block;border-radius:5px;padding:2px 8px;font-size:12px;font-weight:700;background:var(--card2);border:1px solid var(--bd)}
.rel-selo.cri,.critico{border-left:4px solid #e0383e}
.rel-lances{font:15px/1.7 Georgia,serif;background:var(--card);border:1px solid var(--bd);border-radius:8px;padding:8px 12px;margin:8px 0}
.rel-var{background:var(--card);border:1px solid var(--bd);border-radius:8px;padding:8px 12px;margin:8px 0}
.rel-var b.t{display:block;font-size:12.5px;margin-bottom:4px}
.rel-var button{font:600 14px Georgia,serif;padding:2px 7px;margin:2px}
.rel-var button.on{background:var(--ac);color:var(--pri-tx);border-color:var(--ac)}
.rel-fala{position:sticky;bottom:0;margin-top:10px;background:var(--aviso-bg);border:1px solid var(--bd);border-radius:8px;padding:7px 12px;font-size:14px}
.rel-pe{display:flex;gap:10px;align-items:center;justify-content:center;padding:8px;border-top:1px solid var(--bd);background:var(--bg2);flex-wrap:wrap}
.rel-pe .pontos{display:flex;gap:5px;flex-wrap:wrap;justify-content:center;max-width:60vw}
.rel-pe .pontos i{width:10px;height:10px;border-radius:50%;background:var(--bd);cursor:pointer}.rel-pe .pontos i.on{background:var(--ac)}
.rel-capa{text-align:center;padding:5vh 10px}.rel-capa .nomes{font:700 34px Georgia,serif;line-height:1.35}.rel-capa .res{font:700 46px Georgia,serif;margin:12px}
table.rel-tb{border-collapse:collapse;width:100%;margin:8px 0}table.rel-tb td,table.rel-tb th{border-bottom:1px solid var(--bd);padding:4px 8px;text-align:center}
table.rel-tb td:first-child,table.rel-tb th:first-child{text-align:left}
table.rel-tb tr.destaque td{font-size:1.15em;background:#35e0c218}
table.rel-tb i.bola{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:6px}
#numeros table.rel-tb{font-size:12.5px;margin:4px 0}#numeros table.rel-tb td,#numeros table.rel-tb th{padding:2px 6px}
.prec{font-size:12.5px;border:1px solid var(--bd);border-radius:5px;padding:0 6px;margin-left:8px;cursor:help}
.rel-graf{width:100%;height:auto;background:var(--card);border:1px solid var(--bd);border-radius:8px}.rel-graf circle{cursor:pointer}
.critico{background:var(--aviso-bg);border-radius:6px;padding:7px 10px;margin:6px 0}
.critico.mini{padding:3px 8px;font-size:12.5px}
#lances b.cri{color:#e0383e;font-size:10px;margin-left:2px}
@media(max-width:820px){.rel-slide{grid-template-columns:minmax(0,1fr)}.rel-col{position:static;justify-self:center}}`;
const estilo = document.createElement('style'); document.head.appendChild(estilo);

let R = null;                     // relatório recebido do programa
let slides = [], atual = 0, modo = 'principais';
let vista = {v: -1, k: 0};        // variante e lance mostrados no diagrama do slide
const voz = {tocando: false, f: 0, ficha: 0, nome: localStorage.getItem('indiceVoz') || '', vel: +(localStorage.getItem('indiceVozVel') || 1)};
const temVoz = 'speechSynthesis' in window;
const q = (s, el) => (el || document).querySelector(s);

/* ---------- diagramas ---------- */
let nTab = 0;
function marcasSvg(casas) {
  return (casas || []).slice().sort((a, b) => (b[2] === 'tinta') - (a[2] === 'tinta')).map(([sq, lado, tipo]) => {
    const [x, y] = sqXY(sq), c = DEST_COR[lado] || DEST_COR.B;
    return tipo === 'tinta' ? `<rect x="${x}" y="${y}" width="1" height="1" fill="${c}" opacity=".35"/>`
      : `<rect x="${x + .04}" y="${y + .04}" width=".92" height=".92" rx=".1" fill="${c}" fill-opacity=".2" stroke="${c}" stroke-width=".09"/>`;
  }).join('');
}
function diagrama(caixa, fen, {setas = [], casas = [], ult = []} = {}) {
  const el = document.createElement('div'); caixa.innerHTML = ''; caixa.appendChild(el);
  const id = 'rt' + (++nTab);
  pintaTab(el, fen, ult, null, '', id, cavInicial(fen));
  el.children[el.children.length - 2].innerHTML = marcasSvg(casas);
  el.lastElementChild.innerHTML = setas.map(([a, b, cor]) => setaMarkup(a + b, cor)).join('');
  el.insertAdjacentHTML('beforeend', '<svg class="seta rhover" viewBox="0 0 8 8"></svg>');
}

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

/* ---------- slides ---------- */
function montaSlides() {
  slides = [{tipo: 'capa', falas: R.capa.falas}, {tipo: 'resumo', falas: R.falas_resumo}];
  if (R.abertura) slides.push({tipo: 'abertura', falas: R.abertura.falas});
  R.momentos.forEach((m, k) => slides.push({tipo: 'momento', m, k, falas: m.falas}));
  slides.push({tipo: 'fim', falas: R.conclusao.falas});
  slides.push({tipo: 'numeros', falas: R.falas_numeros});
}
function comentariosHtml(L) {
  return (L || []).map(c => `<div class="coment"><b>${c.lance}</b> <span class="mut">(${c.classe})</span> ${c.html}</div>`).join('');
}
function slideHtml(s) {
  const c = R.capa;
  if (s.tipo === 'capa') return `<div class="rel-slide so"><div class="rel-texto rel-capa">
    <div class="mut">${t('Relatório da partida')}</div>
    <div class="nomes">${esc(c.brancas)} <span class="mut">${esc(c.elo_b)}</span><br>×<br>${esc(c.pretas)} <span class="mut">${esc(c.elo_p)}</span></div>
    <div class="res">${esc({'1-0': '1 – 0', '0-1': '0 – 1', '1/2-1/2': '½ – ½'}[c.resultado] || '')}</div>
    <div>${esc(c.detalhe)}</div>${c.parcial ? `<p><b>${esc(c.parcial)}</b></p>` : ''}
    <p class="mut">${t('Use ◀ ▶ (ou as setas do teclado) para passar os slides, ou “▶ Ouvir” para a apresentação narrada.')}</p></div></div>`;
  if (s.tipo === 'numeros') return `<div class="rel-slide so"><div class="rel-texto"><h2>${t('Os números da partida')}</h2>
    ${tabelaNumeros(R.numeros, c.brancas, c.pretas)}${dadosPartida(R.numeros)}<p class="mut">${t(DICA_PRECISAO)}</p></div></div>`;
  if (s.tipo === 'resumo') return `<div class="rel-slide so"><div class="rel-texto"><h2>${t('Resumo')}</h2>${tabelaNumeros(R.numeros, c.brancas, c.pretas, {completa: false})}
    <h3>${t('Avaliação da engine ao longo da partida (acima do meio: brancas)')}</h3>${graficoSvg(true)}
    <div class="mut">${t('Pontos vermelhos: momentos críticos; amarelos: outros lances em destaque. Clique para abrir.')}</div></div></div>`;
  if (s.tipo === 'abertura') return `<div class="rel-slide"><div class="rel-col"><div class="rtab" id="rel-tab"></div></div>
    <div class="rel-texto"><span class="rel-selo">${t('Abertura')}</span><h2>${esc(R.abertura.titulo)}</h2><p>${esc(R.abertura.texto)}</p>
    ${R.abertura.lances ? `<div class="rel-lances">${R.abertura.lances}</div>` : ''}</div></div>`;
  if (s.tipo === 'fim') return `<div class="rel-slide"><div class="rel-col"><div class="rtab" id="rel-tab"></div><div class="rel-passo">${t('Última posição analisada')}</div></div>
    <div class="rel-texto"><h2>${t('Conclusão')}</h2>${R.conclusao.lances ? `<h3>${t('Os últimos lances')}</h3><div class="rel-lances">${R.conclusao.lances}</div>` : ''}
    ${modo === 'completo' ? comentariosHtml(R.conclusao.comentarios) : ''}<p>${esc(R.conclusao.texto)}</p></div></div>`;
  const m = s.m;
  const bloco = b => `<h3>${esc(b.rotulo)}</h3><div>${b.html}</div>`;
  return `<div class="rel-slide"><div class="rel-col"><div class="rtab" id="rel-tab"></div>
      <div class="rel-passo" id="rel-passo"></div><div class="rel-leg">${m.legenda.map(([cor, x]) => `<span><i style="background:${cor}"></i>${esc(x)}</span>`).join('')}</div></div>
    <div class="rel-texto"><span class="rel-selo ${m.tipo === 'critico' ? 'cri' : ''}">${esc(m.selo)}</span><h2>${esc(m.titulo)}</h2>
      <div class="mut">${t('Avaliação (brancas)')}: ${esc(m.aval)} · ${t('Chance de acerto')}: ${m.acerto}% (${esc(m.faixa)})</div>
      ${m.antes ? `<h3>${t('Lances até aqui')}</h3><div class="rel-lances">${m.antes}</div>` : ''}
      ${modo === 'completo' ? comentariosHtml(m.antes_comentarios) : ''}
      ${m.blocos.filter(b => b.principal).map(bloco).join('')}
      ${m.variantes.map((v, n) => `<div class="rel-var" style="border-left:4px solid ${v.cor}"><b class="t">${esc(v.titulo)}</b>
        <button data-v="${n}" data-k="0" title="${esc(t('posição inicial da variante'))}">⏮</button>${v.passos.map((p, k) => `<button data-v="${n}" data-k="${k + 1}">${esc(p.rotulo)}</button>`).join('')}</div>`).join('')}
      <details><summary>${t('Mais detalhes: por quê e a posição')}</summary>${m.blocos.filter(b => !b.principal).map(bloco).join('')}</details></div></div>`;
}
function desenhaDiagrama() {
  const caixa = q('#rel-tab'); if (!caixa) return;
  const s = slides[atual];
  if (s.tipo === 'abertura') return diagrama(caixa, R.abertura.fen);
  if (s.tipo === 'fim') return diagrama(caixa, R.conclusao.fen, {ult: R.conclusao.ult});
  const m = s.m, v = m.variantes[vista.v];
  const passo = q('#rel-passo');
  if (!v) { diagrama(caixa, m.fen, {setas: m.setas, casas: m.casas}); if (passo) passo.textContent = ''; }
  else if (vista.k === 0) {
    const p = v.passos[0]; diagrama(caixa, m.fen, {setas: [[p.uci.slice(0, 2), p.uci.slice(2, 4), v.cor]]});
    if (passo) passo.textContent = v.titulo;
  } else {
    const p = v.passos[vista.k - 1]; diagrama(caixa, p.fen, {setas: [[p.uci.slice(0, 2), p.uci.slice(2, 4), v.cor]], ult: [p.uci.slice(0, 2), p.uci.slice(2, 4)]});
    if (passo) passo.textContent = t('Posição após {x}', {x: p.rotulo});
  }
  q('#rel').querySelectorAll('.rel-var button').forEach(b => b.classList.toggle('on', +b.dataset.v === vista.v && +b.dataset.k === vista.k));
}
function tamanho() {
  const h = innerHeight - 230, w = innerWidth > 820 ? innerWidth * .46 : innerWidth - 40;
  q('#rel').style.setProperty('--sq', Math.max(30, Math.min(72, Math.floor(Math.min(h, w) / 8))) + 'px');
}
function mostra(i) {
  atual = Math.max(0, Math.min(slides.length - 1, i)); vista = {v: -1, k: 0};
  const palco = q('#rel .rel-palco');
  palco.innerHTML = slideHtml(slides[atual]) + '<div class="rel-fala" id="rel-fala" hidden></div>';
  palco.scrollTop = 0; tamanho(); desenhaDiagrama();
  q('#rel-n').textContent = `${atual + 1} / ${slides.length}`;
  q('#rel .pontos').innerHTML = slides.map((s, k) => `<i data-s="${k}" class="${k === atual ? 'on' : ''}" title="${esc(s.m ? s.m.titulo : t({capa: 'Capa', resumo: 'Resumo', abertura: 'Abertura', fim: 'Conclusão', numeros: 'Os números da partida'}[s.tipo]))}"></i>`).join('');
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
  if (s.tipo === 'momento' && (f.v !== vista.v || f.k !== vista.k)) { vista = {v: f.v, k: f.k}; desenhaDiagrama(); }
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
  const setas = lista => (lista || []).map(([a, b, cor]) => {
    const [x1, y1] = xy(a), [x2, y2] = xy(b), A = [x1 + .5, y1 + .5], Z = [x2 + .5, y2 + .5];
    const L = Math.hypot(Z[0] - A[0], Z[1] - A[1]) || 1, ux = (Z[0] - A[0]) / L, uy = (Z[1] - A[1]) / L, E = [Z[0] - ux * .35, Z[1] - uy * .35];
    return `<line x1="${A[0]}" y1="${A[1]}" x2="${E[0]}" y2="${E[1]}" stroke="${cor}" stroke-width=".13" stroke-linecap="round" opacity=".95"/><polygon points="${Z[0]},${Z[1]} ${E[0] - uy * .19},${E[1] + ux * .19} ${E[0] + uy * .19},${E[1] - ux * .19}" fill="${cor}"/>`;
  }).join('');
  function desenha(el, fen, op) {
    const linhas = fen.split(' ')[0].split('/').map(l => [].concat(...[...l].map(c => /\d/.test(c) ? Array(+c).fill('') : [c])));
    const ult = op.ult || [];
    let h = '';
    for (let r = 0; r < 8; r++) for (let c = 0; c < 8; c++) {
      const fr = D.flip ? 7 - r : r, fc = D.flip ? 7 - c : c, p = linhas[fr][fc], nome = 'abcdefgh'[fc] + (8 - fr);
      h += `<div class="c ${(r + c) % 2 ? 'd' : 'l'}${ult.includes(nome) ? ' ult' : ''}">${D.coord && c === 0 ? `<i class="r">${8 - fr}</i>` : ''}${D.coord && r === 7 ? `<i class="f">${'abcdefgh'[fc]}</i>` : ''}${p ? `<span class="p"><svg viewBox="0 0 45 45">${D.pecas[p]}</svg></span>` : ''}</div>`;
    }
    el.innerHTML = `<div class="est-classico">${h}<svg class="seta" viewBox="0 0 8 8">${rects(op.casas)}${setas(op.setas)}</svg><svg class="seta sobre" viewBox="0 0 8 8"></svg></div>`;
  }
  raiz.querySelectorAll('.rtab[data-q]').forEach(el => {
    const q = D.quadros[+el.dataset.q];
    const linha = el.closest('.linha-doc'), ctl = linha && linha.querySelector('.passador');
    desenha(el, q.fen, q);
    if (linha) {                                      // passar o mouse num lance ou casa em negrito marca este tabuleiro
      linha.addEventListener('mouseover', e => {
        const m = e.target.closest('.mc'), s = el.querySelector('svg.sobre'); if (!m || !s || !m.dataset.c) return;
        const lado = m.dataset.l || 'B', u = m.dataset.s;
        s.innerHTML = rects(m.dataset.c.split(',').map(c => [c, lado, m.dataset.t || 'anel'])) + (u ? setas([[u.slice(0, 2), u.slice(2, 4), CORES[lado] || CORES.B]]) : '');
      });
      linha.addEventListener('mouseout', e => { if (e.target.closest('.mc')) { const s = el.querySelector('svg.sobre'); if (s) s.innerHTML = ''; } });
    }
    if (!ctl || !q.seqs || !q.seqs.length) return;
    const principal = {s: 0, k: q.inicial >= 0 ? q.inicial : q.seqs[0].passos.length - 1};
    const noDiagrama = q.inicial >= 0 || q.fen.split(' ')[0] === q.seqs[0].passos[principal.k].fen.split(' ')[0];
    let s = 0, k = principal.k, diagrama = true;
    const legenda = ctl.querySelector('.onde');
    function mostra() {
      const seq = q.seqs[s], p = seq.passos[k];
      const ehDiagrama = diagrama || (noDiagrama && s === principal.s && k === principal.k);
      if (ehDiagrama) desenha(el, q.fen, q);
      else desenha(el, p.fen, {ult: p.uci ? [p.uci.slice(0, 2), p.uci.slice(2, 4)] : [],
        setas: !p.uci && seq.passos[1] ? [[seq.passos[1].uci.slice(0, 2), seq.passos[1].uci.slice(2, 4), seq.cor]] : []});
      legenda.textContent = ehDiagrama ? D.txt.diagrama : (p.rotulo || D.txt.inicio) + ` (${k}/${seq.passos.length - 1})`;
      ctl.querySelectorAll('[data-seq]').forEach(b => b.classList.toggle('on', !ehDiagrama && +b.dataset.seq === s));
    }
    ctl.addEventListener('click', e => {
      const b = e.target.closest('button'); if (!b) return;
      const max = () => q.seqs[s].passos.length - 1;
      if (b.dataset.seq !== undefined) { s = +b.dataset.seq; k = 0; diagrama = false; }
      else if (b.dataset.a === 'diag') { s = principal.s; k = principal.k; diagrama = true; }
      else {
        if (diagrama) diagrama = false;
        if (b.dataset.a === 'ini') k = 0; else if (b.dataset.a === 'fim') k = max();
        else k = Math.max(0, Math.min(max(), k + (b.dataset.a === 'prox' ? 1 : -1)));
      }
      mostra();
    });
    legenda.textContent = D.txt.diagrama;
  });
}

const CSS_DOC = `
.rtab>div{position:relative;display:grid;grid-template-columns:repeat(8,var(--sq));grid-template-rows:repeat(8,var(--sq));width:max-content;user-select:none}
#rel-doc{position:fixed;inset:0;z-index:600;overflow:auto;background:#6b7280}
#rel-doc .barra-doc{position:sticky;top:0;z-index:5;display:flex;gap:10px;align-items:center;flex-wrap:wrap;padding:8px 14px;background:var(--bg2,#0e1420);color:var(--tx,#e6edf7);border-bottom:1px solid var(--bd,#26324a);font:13px "Segoe UI",system-ui,sans-serif}
#rel-doc .folha{--clara:#f0d9b5;--escura:#b58863;color:#111;font:11.3px/1.4 Georgia,"Times New Roman",serif}
#rel-doc .c{position:relative;display:flex;align-items:center;justify-content:center;font-size:calc(var(--sq)*.8);line-height:1}
#rel-doc .c.l{background:var(--clara)}#rel-doc .c.d{background:var(--escura)}
#rel-doc .c.ult::after{content:"";position:absolute;inset:0;background:rgba(255,213,0,.38)}
#rel-doc .c i{position:absolute;z-index:3;font:600 calc(var(--sq)*.2)/1 "Segoe UI",sans-serif;opacity:.85}#rel-doc .c i.r{left:1px;top:1px}#rel-doc .c i.f{right:1px;bottom:0}
#rel-doc .c.l i{color:var(--escura)}#rel-doc .c.d i{color:var(--clara)}
#rel-doc .p{position:relative;z-index:2;display:block;width:96%;height:96%;line-height:0}
#rel-doc .p svg{display:block;width:100%;height:100%;overflow:visible}
#rel-doc svg.seta{position:absolute;inset:0;width:100%;height:100%;z-index:1;pointer-events:none}#rel-doc svg.sobre{z-index:3;opacity:.9}
#rel-doc h1{font-size:21px;margin:0}#rel-doc .sub{font-size:11.5px;color:#333}
#rel-doc h2{font-size:15px;border-bottom:2px solid #111;padding-bottom:2px;margin:10px 0 8px}
#rel-doc h3{font-size:13px;margin:0}#rel-doc h4{font-size:10px;text-transform:uppercase;letter-spacing:.6px;color:#555;margin:0 0 2px}
#rel-doc .topo{display:flex;gap:14px;margin:8px 0 6px;align-items:stretch}
#rel-doc .precisoes{flex:0 0 190px;border:1px solid #999;border-radius:6px;padding:5px 9px}
#rel-doc .precisoes>div{font-size:10px;text-transform:uppercase;letter-spacing:.6px;color:#555}
#rel-doc .precisoes p{margin:5px 0 0;line-height:1.15}#rel-doc .precisoes span{display:block;font-size:10.5px}#rel-doc .precisoes b{font-size:19px}
#rel-doc .graf{flex:1;min-width:0}#rel-doc .leg-graf{font-size:9.5px;color:#444}
#rel-doc svg.rel-graf{width:100%;height:auto;background:#fff;border:1px solid #999;border-radius:6px}
#rel-doc .fio{background:#f3f4f6;border-radius:6px;padding:5px 10px;margin-bottom:4px}#rel-doc .fio ul{margin:0;padding-left:16px}#rel-doc .fio p{margin:0 0 3px}
#rel-doc .linha-doc{display:flex;gap:14px;align-items:flex-start;padding:7px 0 5px;border-top:1px solid #bbb}
#rel-doc .linha-doc>.fig{flex:0 0 calc(var(--sq)*8 + 4px)}#rel-doc .linha-doc>div{flex:1;min-width:0}
#rel-doc .fig{margin:0;padding:2px;overflow:hidden;--sq:27px}#rel-doc .linha-doc{--sq:27px}
/* contorno no lugar da borda e recorte: a borda do tabuleiro seguinte vazava para o pé da página anterior na impressão */
#rel-doc .rtab>div{border:0;outline:1px solid #000;overflow:hidden;contain:paint}#rel-doc .linha-doc .fig{--sq:inherit}
#rel-doc figcaption{font-size:9.5px;color:#333;margin-top:3px;line-height:1.3}
#rel-doc .linha-doc p{margin:3px 0}#rel-doc .meta{font-size:10px;color:#444}
#rel-doc .rot{font-weight:700;font-style:italic;color:#444}#rel-doc p.foco .rot{font-style:normal;color:#14532d}
#rel-doc .selo{font-size:9.5px;font-weight:700;color:#555;text-transform:uppercase;letter-spacing:.5px}
#rel-doc .linha-doc.lv-momento .selo{color:#b3261e}#rel-doc .linha-doc.lv-variante .selo{color:#146c43}
#rel-doc .mc{font-weight:700;border:0;padding:0;background:none}
#rel-doc .tira{display:flex;gap:6px;justify-content:space-between;padding:2px 2px 6px}
#rel-doc .tira figure{margin:0;--sq:15.6px;text-align:center}#rel-doc .tira .c i{display:none}
#rel-doc .tira figcaption{font-size:9px;margin-top:2px}
#rel-doc .tira.coluna{justify-content:flex-start;gap:8px;padding-bottom:0}
#rel-doc .tira-tit{font-size:9.5px;color:#555;text-transform:uppercase;letter-spacing:.5px;margin:0 0 2px;border-top:1px dotted #bbb;padding-top:3px}
#rel-doc .colunas{column-count:4;column-gap:16px;column-rule:1px solid #ccc;font-size:9.8px}
#rel-doc .par{display:grid;grid-template-columns:20px 1fr 1fr;break-inside:avoid;line-height:1.45}#rel-doc .par i{color:#555;font-style:normal}#rel-doc .par small{color:#555;font-size:8.6px}
#rel-doc .nota-lances,#rel-doc .rodape{font-size:9px;color:#444;margin-top:4px}
#rel-doc .final p{margin:2px 0 6px}
#rel-doc .duas{display:grid;grid-template-columns:minmax(0,1.55fr) minmax(0,1fr);gap:16px;align-items:start}
#rel-doc table{border-collapse:collapse;width:100%;font-size:10px}#rel-doc td,#rel-doc th{border-bottom:1px solid #ccc;padding:1px 4px;text-align:center}
#rel-doc table.rel-tb{margin:0}#rel-doc table.rel-tb tr.destaque td{font-size:1.1em;background:#35e0c218}
#rel-doc table.rel-tb i.bola{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:6px}
#rel-doc table.rel-tb td:first-child,#rel-doc table.rel-tb th:first-child{text-align:left}
/* páginas A4: a medida na tela é a mesma da impressão (182 x 273 mm) */
#rel-doc .papel{width:794px;margin:16px auto;background:#fff;padding:45px 53px;box-sizing:border-box;box-shadow:0 4px 24px #0006}
#rel-doc .pagina{width:688px;height:1024px;overflow:hidden;display:flex;flex-direction:column}
#rel-doc .pagina>.unidade,#rel-doc .medidor>.unidade{display:flow-root;flex:0 0 auto}
#rel-doc .pagina.justa{justify-content:space-between}
#rel-doc .medidor{position:absolute;left:-9999px;top:0;width:688px}
/* livro interativo: uma coluna contínua, com o passador embaixo de cada tabuleiro */
#rel-doc.interativo .folha{max-width:940px;margin:16px auto;background:#fff;padding:26px 30px;font-size:14px}
#rel-doc.interativo .linha-doc{--sq:40px;padding:14px 0}
#rel-doc.interativo h3{font-size:16px}#rel-doc.interativo .meta,#rel-doc.interativo figcaption{font-size:12px}#rel-doc.interativo .selo{font-size:11px}
#rel-doc .passador{margin-top:6px;font:12px "Segoe UI",system-ui,sans-serif}
#rel-doc .passador .botoes,#rel-doc .passador .linhas{display:flex;gap:4px;flex-wrap:wrap}#rel-doc .passador .linhas{margin-top:5px}
#rel-doc .passador button{font:600 13px "Segoe UI Symbol","Segoe UI",sans-serif;background:#eef2ff;color:#1e3a8a;border:1px solid #93a3d8;border-radius:5px;padding:4px 0;cursor:pointer;flex:1}
#rel-doc .passador .linhas button{flex:1 1 100%;text-align:left;padding:3px 8px;font-size:11.5px;background:#fff}
#rel-doc .passador button.on{background:#1e3a8a;color:#fff}#rel-doc .passador .onde{font-weight:700;margin-top:5px;min-height:17px}
@media(max-width:700px){#rel-doc.interativo .linha-doc{flex-direction:column;align-items:center;--sq:min(40px,11vw)}#rel-doc .colunas{column-count:2}#rel-doc .duas{grid-template-columns:1fr}#rel-doc .topo{flex-direction:column}#rel-doc .precisoes{flex:0 0 auto}}
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
  const meio = l => l ? `<span><b>${l.critico ? '◆' : ''}${esc(l.san)}</b> <small>${esc(l.aval)}</small></span>` : '<span>…</span>';
  return `<div class="colunas">${[...nums].map(([n, x]) => `<div class="par"><i>${n}.</i>${meio(x.b)}${x.p ? meio(x.p) : '<span></span>'}</div>`).join('')}</div>`;
}
const legendaCores = L => L.map(([cor, x]) => `<span style="white-space:nowrap"><span style="display:inline-block;width:14px;height:4px;background:${cor};vertical-align:middle"></span> ${esc(x)}</span>`).join(' · ');

/* os pedaços do livro, iguais no PDF e na versão interativa */
function pecasDoLivro(interativo) {
  const c = R.capa, N = R.numeros, prec = x => N && N[x].precisao != null ? pct(N[x].precisao) : '—';
  const quadros = [];
  const quadro = q => quadros.push(q) - 1;
  const topo = `<h1>${esc(c.brancas)} ${c.elo_b ? `(${esc(c.elo_b)})` : ''} × ${esc(c.pretas)} ${c.elo_p ? `(${esc(c.elo_p)})` : ''}</h1>
    <div class="sub">${esc(c.detalhe)}</div>${c.parcial ? `<div><b>${esc(c.parcial)}</b></div>` : ''}
    <div class="topo"><div class="precisoes"><div>${t('Precisão')}</div><p><span>${esc(c.brancas)}</span><b>${prec('B')}</b></p><p><span>${esc(c.pretas)}</span><b>${prec('P')}</b></p></div>
      <div class="graf">${graficoSvg(false, 150)}<div class="leg-graf">${t('Avaliação da engine ao longo da partida (acima do meio: brancas)')}</div></div></div>
    <div class="fio"><h4>${t('O fio da partida')}</h4><p>${esc(R.fases)} <b>${esc(R.desfecho)}</b></p><ul>${R.fio.map(x => `<li>${x}</li>`).join('')}</ul></div>`;
  const linhas = R.livro.map((l, n) => {
    const id = quadro({fen: l.fen, setas: l.setas, casas: l.casas, ult: l.ult, seqs: interativo ? l.seqs : null, inicial: l.inicial});
    const ctl = interativo && l.seqs.length ? `<div class="passador"><div class="botoes"><button data-a="ini" title="${esc(t('Começo'))}">⏮</button><button data-a="ant" title="${esc(t('Lance anterior'))}">◀</button><button data-a="diag" title="${esc(t('Voltar ao diagrama'))}">◉</button><button data-a="prox" title="${esc(t('Próximo lance'))}">▶</button><button data-a="fim" title="${esc(t('Fim'))}">⏭</button></div>
      <div class="onde"></div><div class="linhas">${l.seqs.map((s, k) => `<button data-seq="${k}" style="border-left:4px solid ${s.cor}">${esc(s.rotulo)}</button>`).join('')}</div></div>` : '';
    return `<section class="linha-doc lv-${l.tipo}"><div class="fig" style="flex:0 0 calc(var(--sq)*8 + 4px)"><div class="rtab" data-q="${id}"></div><figcaption><b>${t('Diagrama {n}', {n: n + 1})}</b> — ${esc(l.figura)}${l.legenda.length ? '<br>' + legendaCores(l.legenda) : ''}</figcaption>${ctl}</div>
      <div><div class="selo">${esc(l.selo)}</div><h3>${esc(l.titulo)}</h3>${l.meta ? `<div class="meta">${esc(l.meta)}</div>` : ''}
      ${l.paragrafos.map(p => `<p class="${p.foco ? 'foco' : ''}">${p.rotulo ? `<span class="rot"${p.cor ? ` style="color:${p.cor}"` : ''}>${esc(p.rotulo)}.</span> ` : ''}${p.html}</p>`).join('')}</div></section>`;
  });
  const lances = `<h2>${t('Todos os lances')}</h2>${listaCompacta(R.tabela)}<div class="nota-lances">◆ ${t('momento crítico')} · ${t('o número é a avaliação antes do lance (positivo: brancas)')}</div>`;
  const final = `<div class="final"><h2>${t('Tabela final: os números da partida')}</h2><p>${esc(R.conclusao.texto)}</p><div class="duas">${tabelaNumeros(N, c.brancas, c.pretas)}${dadosPartida(N)}</div>
    <div class="rodape">${t(DICA_PRECISAO)} ${t('Relatório gerado pelo Chesslyst.')}</div></div>`;
  return {topo, linhas, lances, final, quadros, quadro};
}
function dadosTabuleiros(quadros) { return {pecas: window.PECAS_SVG, flip: !!cfg.flip, coord: !!cfg.coord, quadros, txt: {diagrama: t('Posição do diagrama'), inicio: t('Começo da linha')}}; }

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
  const D = dadosTabuleiros(P.quadros);
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
function fechaDocumento() { const d = q('#rel-doc'); if (d) d.remove(); document.body.classList.remove('rel-imprimindo'); }

/* ---------- janela do relatório ---------- */
async function busca() {
  const d = await api('/api/relatorio', {id: S.job, modo});
  if (!d || d.erro) { status(t('Erro: {e}', {e: (d && d.erro) || '?'})); return false; }
  R = d; montaSlides(); return true;
}
function fecha() { calar(); fechaDocumento(); const el = q('#rel'); if (el) el.remove(); R = null; }
async function abre() {
  if (!S.job || !S.rows.length) { status(t('Analise a partida primeiro: o relatório usa a análise já feita.')); return; }
  if (!await busca()) return;
  const el = document.createElement('div'); el.id = 'rel';
  el.innerHTML = `<div class="rel-top"><b style="font:700 20px Georgia,serif;color:var(--ac)">${t('Relatório')}</b>
    <select id="rel-modo" title="${esc(t('Quanto entra no relatório'))}"><option value="principais">${t('Principais momentos')}</option><option value="completo">${t('Partida completa, com comentários')}</option></select>
    <div class="grow"></div>
    ${temVoz ? `<button class="pri" id="rel-play"></button><button id="rel-stop" title="${esc(t('Parar o áudio'))}">⏹</button><select id="rel-voz" title="${esc(t('Voz do navegador'))}"></select>
      <select id="rel-vel" title="${esc(t('Velocidade da voz'))}">${[0.8, 0.9, 1, 1.15, 1.3, 1.5].map(v => `<option value="${v}">${num(v, 2)}×</option>`).join('')}</select>`
      : `<span class="mut">${t('Este navegador não tem voz.')}</span>`}
    <button id="rel-livro">${t('📖 Livro interativo')}</button><button id="rel-pdf">${t('📄 Montar PDF')}</button><button id="rel-x" title="${esc(t('Fechar (Esc)'))}">✕</button></div>
    <div class="rel-palco"></div>
    <div class="rel-pe"><button id="rel-ant">◀</button><span id="rel-n"></span><button id="rel-prox">▶</button><div class="pontos"></div></div>`;
  document.body.appendChild(el);
  q('#rel-modo').value = modo;
  q('#rel-modo').onchange = async e => { calar(); modo = e.target.value; if (await busca()) mostra(0); };
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
    const g = e.target.closest('circle[data-m]'); if (g) return vaiSlide(slides.findIndex(s => s.k === +g.dataset.m));
    const b = e.target.closest('.rel-var button'); if (b) { pausar(); vista = {v: +b.dataset.v, k: +b.dataset.k}; desenhaDiagrama(); }
  });
  /* passar o mouse num lance ou casa em negrito marca o diagrama do slide (e não o tabuleiro de trás) */
  el.addEventListener('mouseover', e => {
    e.stopPropagation();
    const m = e.target.closest('.mc'), s = q('#rel-tab svg.rhover'); if (!m || !s || !m.dataset.c) return;
    const lado = m.dataset.l || 'B', u = m.dataset.s;
    s.innerHTML = marcasSvg(m.dataset.c.split(',').map(c => [c, lado, m.dataset.t || 'anel'])) + (u ? setaMarkup(u, DEST_COR[lado] || DEST_COR.B) : '');
  });
  el.addEventListener('mouseout', e => { e.stopPropagation(); if (e.target.closest('.mc')) { const s = q('#rel-tab svg.rhover'); if (s) s.innerHTML = ''; } });
  mostra(0);
}
/* com o relatório aberto, o teclado é dele (as setas não mexem na partida por trás) */
addEventListener('keydown', e => {
  if (!q('#rel')) return;
  if (e.key === 'Escape') { if (q('#rel-doc')) fechaDocumento(); else fecha(); }
  else if (e.target.closest && e.target.closest('select,input,textarea')) return;
  else if (!q('#rel-doc') && (e.key === 'ArrowRight' || e.key === 'PageDown')) vaiSlide(atual + 1);
  else if (!q('#rel-doc') && (e.key === 'ArrowLeft' || e.key === 'PageUp')) vaiSlide(atual - 1);
  else return;
  e.preventDefault(); e.stopImmediatePropagation();
}, true);
addEventListener('resize', () => { if (q('#rel')) { tamanho(); desenhaDiagrama(); } });
addEventListener('pagehide', () => { if (temVoz) speechSynthesis.cancel(); });
estilo.textContent = CSS + CSS_DOC;
const bt = document.getElementById('b-relatorio'); if (bt) bt.onclick = abre;
})();
