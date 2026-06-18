const tg = window.Telegram?.WebApp;
if (tg) { tg.ready(); tg.expand(); }

const API = '';

const PAIRS = {
  crypto: [
    { symbol: 'BTCUSDT',  name: 'BTC',   full: 'Bitcoin',        flag: '₿',   badge: 'hot' },
    { symbol: 'ETHUSDT',  name: 'ETH',   full: 'Ethereum',       flag: 'Ξ',   badge: 'hot' },
    { symbol: 'SOLUSDT',  name: 'SOL',   full: 'Solana',         flag: '◎',   badge: 'hot' },
    { symbol: 'BNBUSDT',  name: 'BNB',   full: 'BNB Chain',      flag: '🔶',  badge: '' },
    { symbol: 'XRPUSDT',  name: 'XRP',   full: 'Ripple',         flag: '✕',   badge: '' },
    { symbol: 'DOGEUSDT', name: 'DOGE',  full: 'Dogecoin',       flag: '🐕',  badge: '' },
    { symbol: 'AVAXUSDT', name: 'AVAX',  full: 'Avalanche',      flag: '🔺',  badge: '' },
    { symbol: 'LINKUSDT', name: 'LINK',  full: 'Chainlink',      flag: '🔗',  badge: '' },
    { symbol: 'ADAUSDT',  name: 'ADA',   full: 'Cardano',        flag: '₳',   badge: '' },
    { symbol: 'DOTUSDT',  name: 'DOT',   full: 'Polkadot',       flag: '●',   badge: '' },
    { symbol: 'MATICUSDT',name: 'MATIC', full: 'Polygon',        flag: '⬡',   badge: '' },
    { symbol: 'LTCUSDT',  name: 'LTC',   full: 'Litecoin',       flag: 'Ł',   badge: '' },
    { symbol: 'NEARUSDT', name: 'NEAR',  full: 'NEAR Protocol',  flag: '⬤',   badge: '' },
    { symbol: 'ATOMUSDT', name: 'ATOM',  full: 'Cosmos',         flag: '⚛',   badge: '' },
    { symbol: 'UNIUSDT',  name: 'UNI',   full: 'Uniswap',        flag: '🦄',  badge: '' },
  ],
  forex: [
    { symbol: 'XAUUSD',  name: 'GOLD',   full: 'Золото / USD',   flag: '🥇',  badge: 'gold' },
    { symbol: 'GBPJPY',  name: 'GBPJPY', full: 'Фунт / Иена',    flag: '🇬🇧', badge: 'hot' },
    { symbol: 'EURUSD',  name: 'EURUSD', full: 'Евро / Доллар',  flag: '🇪🇺', badge: '' },
    { symbol: 'GBPUSD',  name: 'GBPUSD', full: 'Фунт / Доллар',  flag: '🇬🇧', badge: '' },
    { symbol: 'USDJPY',  name: 'USDJPY', full: 'Доллар / Иена',  flag: '🇯🇵', badge: '' },
    { symbol: 'XAGUSD',  name: 'SILVER', full: 'Серебро / USD',  flag: '🥈',  badge: '' },
    { symbol: 'AUDUSD',  name: 'AUDUSD', full: 'Австралиец',     flag: '🇦🇺', badge: '' },
    { symbol: 'USDCAD',  name: 'USDCAD', full: 'Доллар / CAD',   flag: '🇨🇦', badge: '' },
    { symbol: 'USDCHF',  name: 'USDCHF', full: 'Доллар / Франк', flag: '🇨🇭', badge: '' },
    { symbol: 'NZDUSD',  name: 'NZDUSD', full: 'Новозеланд.',    flag: '🇳🇿', badge: '' },
    { symbol: 'EURJPY',  name: 'EURJPY', full: 'Евро / Иена',    flag: '🇪🇺', badge: '' },
    { symbol: 'EURGBP',  name: 'EURGBP', full: 'Евро / Фунт',    flag: '🇪🇺', badge: '' },
  ],
};

const HTF = { '1m': '15M', '5m': '1H', '15m': '4H' };

// МСК = UTC+3
const MSK_OFFSET = 3 * 60;

// Session schedule in MSK hours
const SESSIONS = [
  { id: 'asia',    name: '🌏 Азия',     startH: 2,  endH: 10, mskTime: '02:00–10:00' },
  { id: 'london',  name: '🇬🇧 Лондон', startH: 10, endH: 19, mskTime: '10:00–19:00' },
  { id: 'newyork', name: '🇺🇸 Нью-Йорк',startH: 16, endH: 25, mskTime: '16:00–01:00' },
];

let state = { type: 'crypto', symbol: 'BTCUSDT', tf: '1m' };

/* ── Init ─────────────────────────────────────────── */
function init() {
  renderGrid();
  updateHTF();
  startClock();
}

/* ── Clock + Sessions ─────────────────────────────── */
function getMSK() {
  const now = new Date();
  const utcMs = now.getTime() + now.getTimezoneOffset() * 60000;
  return new Date(utcMs + MSK_OFFSET * 60000);
}

function startClock() {
  function tick() {
    const msk = getMSK();
    const hh = String(msk.getHours()).padStart(2, '0');
    const mm = String(msk.getMinutes()).padStart(2, '0');
    const ss = String(msk.getSeconds()).padStart(2, '0');
    document.getElementById('clockTime').textContent = `${hh}:${mm}:${ss}`;
    updateSessions(msk.getHours());
  }
  tick();
  setInterval(tick, 1000);
}

function updateSessions(mskHour) {
  SESSIONS.forEach(sess => {
    const el = document.querySelector(`.sess-item[data-sess="${sess.id}"]`);
    if (!el) return;
    // handle overnight: newyork endH=25 means next day 01:00
    let active = false;
    if (sess.endH <= 24) {
      active = mskHour >= sess.startH && mskHour < sess.endH;
    } else {
      // overnight session: 16–01
      active = mskHour >= sess.startH || mskHour < (sess.endH - 24);
    }
    el.classList.toggle('active', active);
  });
}

/* ── Symbol Grid ──────────────────────────────────── */
function renderGrid() {
  const list = PAIRS[state.type];
  document.getElementById('symCount').textContent = `${list.length} пар`;
  document.getElementById('symbolGrid').innerHTML = list.map(p => `
    <div class="symbol-card ${p.symbol === state.symbol ? 'active' : ''}"
         onclick="selectSymbol('${p.symbol}')">
      ${p.badge ? `<div class="sym-badge ${p.badge}">${p.badge === 'gold' ? 'GOLD' : 'HOT'}</div>` : ''}
      <span class="sym-flag">${p.flag}</span>
      <div class="sym-name">${p.name}</div>
      <div class="sym-full">${p.full}</div>
    </div>
  `).join('');
}

function switchType(type) {
  state.type = type;
  document.querySelectorAll('.type-btn').forEach(b =>
    b.classList.toggle('active', b.dataset.type === type)
  );
  state.symbol = PAIRS[type][0].symbol;
  renderGrid();
  clearSignal();
}

function selectSymbol(sym) {
  state.symbol = sym;
  document.querySelectorAll('.symbol-card').forEach((c, i) =>
    c.classList.toggle('active', PAIRS[state.type][i]?.symbol === sym)
  );
  clearSignal();
}

function selectTF(tf) {
  state.tf = tf;
  document.querySelectorAll('.tf-btn').forEach(b =>
    b.classList.toggle('active', b.dataset.tf === tf)
  );
  updateHTF();
  clearSignal();
}

function updateHTF() {
  const htf = HTF[state.tf] || '4H';
  document.getElementById('htfText').innerHTML =
    `Анализ структуры на <b>${htf}</b> → точка входа на <b>${state.tf.toUpperCase()}</b>`;
}

/* ── Signal ───────────────────────────────────────── */
const LOADER_STEPS = [
  ['Анализирую HTF структуру…',  'Определяю Bias рынка'],
  ['Ищу Order Blocks…',          'Зоны институционального спроса/предложения'],
  ['Проверяю Fair Value Gaps…',  'Нахожу дисбалансы цены'],
  ['Анализирую ликвидность…',    'BSL / SSL уровни и Stop Hunt зоны'],
  ['Рассчитываю сигнал…',        'Entry · SL · TP · Risk:Reward'],
];

async function getSignal() {
  const btn = document.getElementById('signalBtn');
  const overlay = document.getElementById('overlay');
  btn.disabled = true;
  overlay.classList.remove('hidden');
  let step = 0;
  const timer = setInterval(() => {
    const s = LOADER_STEPS[step % LOADER_STEPS.length];
    document.getElementById('loaderText').textContent = s[0];
    document.getElementById('loaderSub').textContent  = s[1];
    step++;
  }, 900);

  try {
    const r = await fetch(`${API}/api/signal/${state.symbol}/${state.tf}`);
    clearInterval(timer);
    overlay.classList.add('hidden');
    if (r.status === 404) { showNoSignal(); return; }
    if (!r.ok) { showNoSignal(); return; }
    renderSignal(await r.json());
  } catch {
    clearInterval(timer);
    overlay.classList.add('hidden');
    showNoSignal();
  } finally {
    btn.disabled = false;
  }
}

function renderSignal(s) {
  clearSignal();
  const isLong  = s.type === 'LONG';
  const clr     = isLong ? 'var(--long)'  : 'var(--short)';
  const headCls = isLong ? 'long-head'    : 'short-head';
  const icon    = isLong ? '▲'            : '▼';
  const dir     = isLong ? 'LONG'         : 'SHORT';
  const rrPct   = Math.min(100, (s.rr_ratio / 5) * 100);
  const confClr = s.confidence >= 75 ? clr : s.confidence >= 55 ? 'var(--gold)' : 'var(--short)';
  const qTag    = s.confidence >= 75
    ? '<span class="quality-tag q-high">Высокое</span>'
    : s.confidence >= 55
    ? '<span class="quality-tag q-mid">Среднее</span>'
    : '<span class="quality-tag q-low">Низкое</span>';

  // get current pair info
  const pair = [...PAIRS.crypto, ...PAIRS.forex].find(p => p.symbol === s.symbol);
  const pairFlag = pair?.flag || '';
  const pairFull = pair?.full || s.symbol;

  document.getElementById('signalResult').innerHTML = `
    <div class="signal-result">
      <div class="sig-head ${headCls}">
        <div class="sig-head-bg"></div>
        <div class="sig-top">
          <div class="sig-type">
            <div class="sig-type-icon">${icon}</div>
            ${dir}
            <span style="font-size:13px;font-weight:600;color:var(--text2);margin-left:4px">${pairFlag} ${pairFull}</span>
          </div>
          ${s.current_price != null ? `<div style="font-size:12px;color:var(--text2);margin-top:2px">Текущая цена: <b style="color:var(--text1)">${s.current_price}</b></div>` : ''}
          <div class="conf-badge">
            <div class="conf-pct" style="color:${confClr}">${s.confidence}%</div>
            <div class="conf-label">уверен.</div>
          </div>
        </div>
        <div class="sig-setup-row">
          <div>
            <div class="sig-setup">${s.setup_type}</div>
            <div class="sig-meta">${s.session} · ${s.timeframe.toUpperCase()} · ${s.timestamp}</div>
          </div>
          ${qTag}
        </div>
      </div>
      <div class="sig-body">
        <div class="levels-grid">
          <div class="level-box entry-box">
            <div class="lv-lbl">Вход</div>
            <div class="lv-val">${s.entry}</div>
          </div>
          <div class="level-box sl-box">
            <div class="lv-lbl">Стоп</div>
            <div class="lv-val" style="color:var(--short)">${s.sl}</div>
          </div>
          <div class="level-box">
            <div class="lv-lbl tp1c">TP 1 &nbsp;<span style="opacity:.45;font-weight:500">(1.5R)</span></div>
            <div class="lv-val" style="color:#a855f7">${s.tp1}</div>
          </div>
          <div class="level-box" style="grid-column:span 2">
            <div class="lv-lbl tp2c">TP 2 &nbsp;<span style="opacity:.45;font-weight:500">(2.5R)</span></div>
            <div class="lv-val" style="color:var(--long)">${s.tp2}</div>
          </div>
          <div class="level-box tp3-box">
            <div class="lv-lbl tp3c">TP 3 — Зона ликвидности</div>
            <div class="lv-val" style="color:var(--gold)">${s.tp3}</div>
          </div>
        </div>
        <div class="rr-block">
          <div class="rr-top">
            <span class="rr-label">Risk : Reward</span>
            <span class="rr-val">1 : ${s.rr_ratio}</span>
          </div>
          <div class="rr-track"><div class="rr-fill" style="width:${rrPct}%"></div></div>
          <div class="phase-row">
            <div class="phase-tag">📊 ${s.market_phase}</div>
          </div>
        </div>
      </div>
    </div>`;
  show('signalResult');

  if (s.confluences?.length) {
    document.getElementById('confList').innerHTML =
      s.confluences.map(c => `<div class="conf-item">${c}</div>`).join('');
    show('confluencePanel');
  }
  if (s.risk_info) {
    const ri = s.risk_info;
    document.getElementById('riskGrid').innerHTML = `
      <div class="risk-grid">
        <div class="risk-box"><div class="risk-lbl">Риск</div><div class="risk-val" style="color:var(--short)">${ri.risk_pct}%</div></div>
        <div class="risk-box"><div class="risk-lbl">SL пипсов</div><div class="risk-val">${ri.sl_pips}</div></div>
        <div class="risk-box"><div class="risk-lbl">Лоты ($1000)</div><div class="risk-val" style="color:var(--accent)">${ri.lots}</div></div>
        <div class="risk-box"><div class="risk-lbl">Сумма риска</div><div class="risk-val">$${ri.risk_amount}</div></div>
      </div>`;
    show('riskPanel');
  }
  tg?.HapticFeedback?.notificationOccurred('success');
  document.getElementById('signalResult').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function showNoSignal() { clearSignal(); show('noSignal'); }
function clearSignal() {
  ['signalResult','noSignal','confluencePanel','riskPanel'].forEach(hide);
}
function show(id) { document.getElementById(id)?.classList.remove('hidden'); }
function hide(id) { document.getElementById(id)?.classList.add('hidden'); }

init();
