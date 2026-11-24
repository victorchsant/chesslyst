/* Chesslyst online: faz a interface funcionar sem servidor.
   - carrega o Python no navegador (Pyodide) e o pacote do Chesslyst (app.zip);
   - roda o Stockfish em WebAssembly (worker do navegador);
   - intercepta as chamadas /api/... da interface e as entrega ao Python (webserver.py). */
(() => {
  const BASE = new URL('.', document.currentScript.src).href;
  const PYODIDE = 'https://cdn.jsdelivr.net/pyodide/v0.27.7/full/';
  window.ONLINE = true;
  window.SITE_BASE = BASE;

  // ---------- aviso de carregamento ----------
  const tela = document.createElement('div');
  tela.id = 'online-carga';
  tela.style.cssText = 'position:fixed;inset:0;z-index:999;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:14px;background:#0b0f17;color:#e6edf7;font:15px/1.5 "Segoe UI",system-ui,sans-serif;text-align:center;padding:24px';
  tela.innerHTML = '<div style="font:700 38px Georgia,serif;color:#35e0c2">Chesslyst</div><div id="carga-msg">Preparando o Python no seu navegador…</div><div style="width:min(320px,80vw);height:6px;background:#202a3d;border-radius:4px;overflow:hidden"><div id="carga-barra" style="height:100%;width:6%;background:#35e0c2;transition:width .4s"></div></div><div style="color:#8fa0bd;font-size:13px;max-width:420px">Na primeira vez são baixados cerca de 15 MB (Python e Stockfish); depois ficam guardados no navegador. Tudo roda no seu computador: nada da sua análise sai dele.</div>';
  document.addEventListener('DOMContentLoaded', () => document.body.appendChild(tela));
  const msg = (t, p) => { const m = document.getElementById('carga-msg'), b = document.getElementById('carga-barra'); if (m) m.textContent = t; if (b && p) b.style.width = p + '%'; };

  // ---------- Stockfish (WebAssembly) ----------
  class Motor {
    constructor() { this.cb = null; this.cadeia = Promise.resolve(); this.pronto = this._inicia(); }
    _inicia() {
      return new Promise((ok, erro) => {
        this.w = new Worker(BASE + 'motor/stockfish-19-lite-single.js');
        this.w.onmessage = e => {
          const l = typeof e.data === 'string' ? e.data : String(e.data);
          if (l === 'uciok') { this.w.postMessage('setoption name Hash value 32'); this.w.postMessage('isready'); }
          else if (l === 'readyok') ok();
          else if (this.cb) this.cb(l);
        };
        this.w.onerror = e => erro(new Error('motor: ' + (e.message || 'falhou')));
        this.w.postMessage('uci');
      });
    }
    _roda(fen, n, depth, jogada) {
      this.cadeia = this.cadeia.catch(() => {}).then(async () => {
        await this.pronto;
        return new Promise(fim => {
          const ult = {}, melhorEm = {};
          this.cb = l => {
            if (l.startsWith('info') && l.includes(' pv ') && l.includes(' score ') && !/ (lower|upper)bound/.test(l)) {
              const t = l.split(' '), g = k => { const i = t.indexOf(k); return i < 0 ? null : t[i + 1]; };
              const mp = +(g('multipv') || 1), d = +g('depth'), pv = t.slice(t.indexOf('pv') + 1);
              const i = t.indexOf('score'), tipo = t[i + 1], val = +t[i + 2];
              ult[mp] = { multipv: mp, depth: d, cp: tipo === 'cp' ? val : null, mate: tipo === 'mate' ? val : null, pv };
              if (mp === 1) melhorEm[d] = pv[0];
            } else if (l.startsWith('bestmove')) {
              this.cb = null;
              fim({ linhas: Object.keys(ult).map(Number).sort((a, b) => a - b).map(k => ult[k]), bestAt: melhorEm });
            }
          };
          this.w.postMessage('setoption name MultiPV value ' + n);
          this.w.postMessage('position fen ' + fen);
          this.w.postMessage('go depth ' + depth + (jogada ? ' searchmoves ' + jogada : ''));
        });
      });
      return this.cadeia;
    }
    analisa(fen, n, depth) { return this._roda(fen, n, depth, null); }
    async jogado(fen, uci, depth) {
      const r = await this._roda(fen, 1, depth, uci), l = r.linhas[0];
      return { cp: l.cp, mate: l.mate, pv: l.pv };
    }
    parar() { if (this.cb && this.w) this.w.postMessage('stop'); }
  }
  const motor = new Motor();
  window.sfAnalisa = async (fen, n, d) => JSON.stringify(await motor.analisa(fen, n, d));
  window.sfJogado = async (fen, uci, d) => JSON.stringify(await motor.jogado(fen, uci, d));
  window.sfParar = () => motor.parar();

  // ---------- Python (Pyodide) ----------
  const pronto = (async () => {
    await new Promise((ok, erro) => { const s = document.createElement('script'); s.src = PYODIDE + 'pyodide.js'; s.onload = ok; s.onerror = () => erro(new Error('não consegui baixar o Pyodide (sem internet?)')); document.head.appendChild(s); });
    msg('Iniciando o Python…', 25);
    const py = await loadPyodide({ indexURL: PYODIDE });
    msg('Carregando o Chesslyst…', 55);
    const zip = await (await fetch(BASE + 'app.zip')).arrayBuffer();
    py.unpackArchive(zip, 'zip', { extractDir: '/home/pyodide/app' });
    py.runPython("import sys; sys.path.insert(0, '/home/pyodide/app')");
    msg('Iniciando o Stockfish…', 75);
    await motor.pronto;
    await py.runPythonAsync('import webserver');
    msg('Pronto!', 100);
    setTimeout(() => tela.remove(), 250);
    return py.pyimport('webserver');
  })();
  pronto.catch(e => { msg('Erro ao carregar: ' + e.message + '. Recarregue a página.', 100); });

  // ---------- as chamadas /api/... da interface vão para o Python ----------
  const fetchOrig = window.fetch.bind(window);
  window.fetch = async (entrada, opcoes) => {
    const url = typeof entrada === 'string' ? entrada : String(entrada.href || entrada.url || entrada);
    let alvo; try { alvo = new URL(url, location.href); } catch (e) { return fetchOrig(entrada, opcoes); }
    const m = alvo.origin === location.origin ? (alvo.pathname + alvo.search).match(/^(\/api\/[^?]*)(\?.*)?$/) : null;   // só as chamadas da própria interface; Lichess etc. passam direto
    if (!m) return fetchOrig(entrada, opcoes);
    const ws = await pronto;
    const q = Object.fromEntries(new URLSearchParams(m[2] || ''));
    const cab = (opcoes && opcoes.headers) || {};
    const r = JSON.parse(await ws.handle((opcoes && opcoes.method) || 'GET', m[1], JSON.stringify(q), (opcoes && opcoes.body) || '', cab['X-Lang'] || 'pt'));
    return new Response(JSON.stringify(r.corpo), { status: r._status, headers: { 'Content-Type': 'application/json' } });
  };

  // ---------- retoques da interface na versão online ----------
  document.addEventListener('DOMContentLoaded', () => {
    const st = document.createElement('style');
    st.textContent = '#b-jan-eng,#jan-eng{display:none!important}';
    document.head.appendChild(st);
    const nota = document.querySelector('.sobre .nota');
    if (nota) nota.insertAdjacentHTML('afterend', '<p class="nota"><b>Versão online:</b> o programa roda inteiro no seu navegador (Python em WebAssembly e Stockfish em WebAssembly, que é mais lento que a versão instalada). Não há o modelo Maia nesta versão: a Chance de Acerto usa uma estimativa feita a partir das avaliações da engine. Para o modelo completo, baixe o Chesslyst.exe nas Releases do GitHub.</p>');
  });
})();
