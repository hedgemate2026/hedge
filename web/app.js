const state = {
  runs: [],
  currentRun: null,
  dashboard: null,
  assets: [],
  sensitivityTicker: null,
  loadingTimer: null,
  loadingStartedAt: null,
};

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function statusClass(type) {
  return type === 'error' ? 'error' : '';
}

function encodeArtifactPath(path) {
  return encodeURI(String(path ?? '')).replaceAll('#', '%23').replaceAll('?', '%3F');
}

async function fetchJson(url) {
  const sep = url.includes('?') ? '&' : '?';
  const response = await fetch(`${url}${sep}_ts=${Date.now()}`, {
    cache: 'no-store',
    headers: { 'Cache-Control': 'no-cache' },
  });
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json();
}

function setLoading(isLoading, title = '분석 중…', message = '잠시만 기다려 주세요. 최신 결과를 불러오고 있습니다.', options = {}) {
  const overlay = document.getElementById('loading-overlay');
  const card = document.querySelector('.loading-card');
  document.getElementById('loading-title').textContent = title;
  document.getElementById('loading-message').textContent = message;
  const elapsedNode = document.getElementById('loading-elapsed');
  const spinner = document.getElementById('loading-spinner');
  const confirmButton = document.getElementById('loading-confirm-button');
  const requireConfirm = Boolean(options.requireConfirm);
  const isError = Boolean(options.isError);
  if (state.loadingTimer) {
    clearInterval(state.loadingTimer);
    state.loadingTimer = null;
  }
  if (isLoading) {
    if (requireConfirm) {
      state.loadingStartedAt = null;
      elapsedNode.textContent = options.elapsedText || '분석 결과를 반영했습니다.';
    } else {
      state.loadingStartedAt = Date.now();
      elapsedNode.textContent = '0초 경과';
      state.loadingTimer = setInterval(() => {
        const sec = Math.max(0, Math.floor((Date.now() - state.loadingStartedAt) / 1000));
        elapsedNode.textContent = `${sec}초 경과`;
      }, 1000);
    }
  } else {
    state.loadingStartedAt = null;
    elapsedNode.textContent = '0초 경과';
  }
  spinner.classList.toggle('hidden', requireConfirm || !isLoading);
  confirmButton.classList.toggle('hidden', !isLoading || !requireConfirm);
  confirmButton.textContent = isError ? '확인' : '확인';
  if (card) card.classList.toggle('error', isError && isLoading);
  overlay.classList.toggle('hidden', !isLoading);
}

function formatValue(value, digits = 2) {
  if (value === null || value === undefined || value === '') return '-';
  if (typeof value === 'number') return value.toFixed(digits);
  return String(value);
}

function formatPct(value) {
  if (value === null || value === undefined || value === '') return '-';
  return `${Number(value).toFixed(2)}%`;
}

function formatSignedPct(value) {
  if (value === null || value === undefined || value === '') return '-';
  const n = Number(value);
  return `${n > 0 ? '+' : ''}${n.toFixed(2)}%`;
}

function status(message, type = '') {
  const root = document.getElementById('status-banner');
  root.replaceChildren();
  if (!message) return;
  const node = document.createElement('div');
  node.className = `status-message ${statusClass(type)}`.trim();
  node.textContent = message;
  root.appendChild(node);
}

function formatKrw(value) {
  if (value === null || value === undefined || value === '') return '-';
  const n = Number(value);
  if (Number.isNaN(n)) return '-';
  return `${Math.round(n).toLocaleString('ko-KR')}원`;
}

function normalizeAssetQuery(value) {
  return String(value || '').trim().toLowerCase();
}

function resolveAssetOption(query) {
  const normalized = normalizeAssetQuery(query);
  if (!normalized) return null;
  return state.assets.find((asset) => {
    const ticker = normalizeAssetQuery(asset.ticker);
    const label = normalizeAssetQuery(asset.label);
    const search = normalizeAssetQuery(asset.searchText);
    return normalized === ticker || normalized === label || search.includes(normalized);
  }) || null;
}

function assetLabelForTicker(ticker) {
  const asset = state.assets.find((item) => item.ticker === ticker);
  return asset ? asset.label : String(ticker || '');
}

function resolveSensitivityTicker(query, rows) {
  const asset = resolveAssetOption(query);
  if (asset && rows.some((row) => row.ticker === asset.ticker)) return asset.ticker;
  const normalized = normalizeAssetQuery(query);
  if (!normalized) return null;
  const direct = rows.find((row) => normalizeAssetQuery(row.ticker) === normalized);
  return direct ? direct.ticker : null;
}

function renderAssetOptions() {
  const datalist = document.getElementById('asset-options');
  datalist.replaceChildren();
  state.assets.forEach((asset) => {
    const option = document.createElement('option');
    option.value = asset.label;
    option.label = asset.ticker;
    datalist.appendChild(option);
  });
}

function updateSingleAssetPreview() {
  const preview = document.getElementById('single-asset-preview');
  const asset = resolveAssetOption(document.getElementById('single-asset-input').value);
  preview.textContent = asset ? `선택된 자산: ${asset.label} (${asset.ticker})` : '지원 자산명을 입력해 주세요.';
}

function createPortfolioRow(asset = '', amountKrw = '') {
  const row = document.createElement('div');
  row.className = 'portfolio-row';
  row.innerHTML = `
    <input class="text-input portfolio-asset-input" type="text" list="asset-options" placeholder="회사명/자산명 검색" />
    <input class="text-input portfolio-amount-input" type="number" min="1" step="1" placeholder="보유 금액 (KRW)" />
    <button type="button" class="ghost-button portfolio-remove-button">삭제</button>
  `;
  row.querySelector('.portfolio-asset-input').value = asset;
  row.querySelector('.portfolio-amount-input').value = amountKrw;
  row.querySelector('.portfolio-remove-button').addEventListener('click', () => {
    row.remove();
    updatePortfolioSummary();
  });
  row.querySelector('.portfolio-asset-input').addEventListener('input', updatePortfolioSummary);
  row.querySelector('.portfolio-amount-input').addEventListener('input', updatePortfolioSummary);
  return row;
}

function seedPortfolioRows() {
  const root = document.getElementById('portfolio-rows');
  root.replaceChildren();
  [
    ['Apple', 2000000],
    ['Microsoft', 2000000],
    ['NVIDIA', 2000000],
    ['삼성전자', 2000000],
    ['비트코인', 2000000],
  ].forEach(([asset, amount]) => root.appendChild(createPortfolioRow(asset, amount)));
  updatePortfolioSummary();
}

function collectPortfolioRows() {
  return Array.from(document.querySelectorAll('.portfolio-row')).map((row) => ({
    asset: row.querySelector('.portfolio-asset-input').value.trim(),
    amountKrw: Number(row.querySelector('.portfolio-amount-input').value || 0),
  })).filter((row) => row.asset || row.amountKrw);
}

function updatePortfolioSummary() {
  const rows = collectPortfolioRows();
  const total = rows.reduce((sum, row) => sum + (Number(row.amountKrw) || 0), 0);
  const validCount = rows.filter((row) => resolveAssetOption(row.asset) && Number(row.amountKrw) > 0).length;
  document.getElementById('portfolio-total').textContent = total > 0
    ? `총 보유 금액: ${formatKrw(total)} · 유효 자산 ${validCount}개`
    : '총 보유 금액: -';
}

function renderRunSelect() {
  const select = document.getElementById('run-select');
  select.replaceChildren();
  state.runs.forEach((run) => {
    const option = document.createElement('option');
    option.value = run;
    option.textContent = run;
    select.appendChild(option);
  });
  if (state.currentRun) select.value = state.currentRun;
  select.onchange = async (event) => {
    state.currentRun = event.target.value;
    await loadDashboard(state.currentRun);
  };
}

function metricCard(label, value, help) {
  return `
    <article class="glass-card metric-card">
      <div class="metric-label">${escapeHtml(label)}</div>
      <h3>${escapeHtml(value)}</h3>
      <p>${escapeHtml(help)}</p>
    </article>
  `;
}

function renderOverview(data) {
  const meta = data.meta || {};
  const dq = data.dqSummary || {};
  const validation = data.validationSummary || {};
  document.getElementById('overview-grid').innerHTML = [
    metricCard('분석 스냅샷', data.runId || '-', meta.analysisPeriod || '분석 기간'),
    metricCard('기준통화', meta.baseCurrency || 'KRW', '원화 기준 리스크 평가'),
    metricCard('대상 티커', meta.targetTickers || '-', '유니버스 크기'),
    metricCard('Stress 일수', meta.stressDays || '-', meta.benchmark || '벤치마크'),
    metricCard('DQ 상태', `${dq.pass ?? 0}/${dq.warn ?? 0}/${dq.fail ?? 0}`, 'PASS / WARN / FAIL'),
    metricCard('검증셋', `${validation.pass ?? 0}/${validation.fail ?? 0}`, 'PASS / FAIL'),
  ].join('');
}

function renderCompareSection(targetId, chipId, rows, chipText, emptyText) {
  const root = document.getElementById(targetId);
  const chip = document.getElementById(chipId);
  chip.textContent = chipText || '-';
  if (!rows || !rows.length) {
    root.innerHTML = `<div class="empty-state">${escapeHtml(emptyText)}</div>`;
    return;
  }

  const maxRisk = Math.max(...rows.map((row) => Math.abs(Number(row.cvar_95 || 0))), 0.0001);
  const scenarioCards = rows.map((row) => {
    const note = row.no_recommendation_reason ? `<div class="scenario-note">${escapeHtml(row.no_recommendation_reason)}</div>` : '';
    return `
      <div class="scenario-card">
        <div class="scenario-title">
          <h3>${escapeHtml(row.displayScenario || row.scenario)}</h3>
          ${note}
        </div>
        <div class="metric-pills">
          <span class="metric-pill">CVaR ${escapeHtml(formatValue(row.cvar_95, 4))}</span>
          <span class="metric-pill">MDD ${escapeHtml(formatValue(row.mdd, 4))}</span>
          <span class="metric-pill">Sharpe ${escapeHtml(formatValue(row.sharpe_krw_proxy, 3))}</span>
          <span class="metric-pill positive">CVaR 개선 ${escapeHtml(formatPct(row.cvar_improve_pct))}</span>
          <span class="metric-pill positive">MDD 개선 ${escapeHtml(formatPct(row.mdd_improve_pct))}</span>
          <span class="metric-pill positive">Sharpe 개선 ${escapeHtml(formatPct(row.sharpe_improve_pct))}</span>
        </div>
      </div>
    `;
  }).join('');

  const bars = rows.map((row) => {
    const width = `${(Math.abs(Number(row.cvar_95 || 0)) / maxRisk) * 100}%`;
    return `
      <div class="bar-row">
        <span>${escapeHtml(row.scenario.length > 12 ? row.scenario.slice(0, 12) + '…' : row.scenario)}</span>
        <div class="bar-track"><div class="bar-fill risk" style="width:${width}"></div></div>
        <strong>${escapeHtml(formatValue(row.cvar_95, 4))}</strong>
      </div>
    `;
  }).join('');

  root.innerHTML = `
    <div class="compare-grid">
      ${scenarioCards}
      <div class="scenario-card">
        <div class="scenario-title"><h3>CVaR 비교</h3></div>
        <div class="bar-cluster">${bars}</div>
      </div>
    </div>
  `;
}

function renderAllocation(targetId, detail, emptyText) {
  const root = document.getElementById(targetId);
  if (!detail || !detail.weights || !detail.weights.length) {
    root.innerHTML = `<div class="empty-state">${escapeHtml(emptyText)}</div>`;
    return;
  }
  const maxWeight = Math.max(...detail.weights.map((item) => Number(item.weightPct || 0)), 0.0001);
  root.innerHTML = `
    <div class="scenario-card">
      <div class="scenario-title">
        <h3>${escapeHtml(detail.displayLabel || '-')}</h3>
        <div class="scenario-note">${escapeHtml(detail.message || '추천 조합')}</div>
      </div>
      <div class="allocation-list">
        ${detail.weights.map((item) => `
          <div class="allocation-item">
            <div class="allocation-item-head">
              <div>
                <strong>${escapeHtml(item.displayName)}</strong>
                <span class="ticker-caption">${escapeHtml(item.ticker)}</span>
              </div>
              <strong>${escapeHtml(formatPct(item.weightPct))}</strong>
            </div>
            <div class="bar-track"><div class="bar-fill" style="width:${(Number(item.weightPct || 0) / maxWeight) * 100}%"></div></div>
          </div>
        `).join('')}
      </div>
    </div>
  `;
}

function renderTopHedges(rows) {
  const root = document.getElementById('top-hedges');
  if (!rows || !rows.length) {
    root.innerHTML = '<div class="empty-state">추천 후보 데이터가 없습니다.</div>';
    return;
  }
  const body = rows.map((row, index) => `
    <tr>
      <td><span class="rank-pill">${index + 1}</span></td>
      <td><strong>${escapeHtml(row.displayName || row.ticker)}</strong><div class="ticker-caption">${escapeHtml(row.ticker)}</div></td>
      <td><span class="bucket-chip">${escapeHtml(row.hedge_bucket)}</span></td>
      <td>${escapeHtml(formatValue(row.hes_score, 4))}</td>
      <td>${escapeHtml(formatValue(row.cvar_95_1y_krw, 4))}</td>
      <td>${escapeHtml(formatValue(row.sharpe_1y_krw_proxy, 3))}</td>
      <td>${escapeHtml(formatValue(row.adv_60, 0))}</td>
    </tr>
  `).join('');
  root.innerHTML = `
    <div class="table-wrap">
      <table class="data-table">
        <thead>
          <tr><th>#</th><th>자산</th><th>Bucket</th><th>HES</th><th>CVaR</th><th>Sharpe</th><th>ADV</th></tr>
        </thead>
        <tbody>${body}</tbody>
      </table>
    </div>
  `;
}

function renderRiskWatchlist(rows) {
  const root = document.getElementById('risk-watchlist');
  if (!rows || !rows.length) {
    root.innerHTML = '<div class="empty-state">리스크 데이터가 없습니다.</div>';
    return;
  }
  root.innerHTML = `
    <div class="table-wrap">
      <table class="data-table">
        <thead><tr><th>Ticker</th><th>Asset</th><th>MDD</th><th>CVaR</th><th>Sharpe</th></tr></thead>
        <tbody>
          ${rows.map((row) => `
            <tr>
              <td><strong>${escapeHtml(row.displayName || row.ticker)}</strong><div class="ticker-caption">${escapeHtml(row.ticker)}</div></td>
              <td>${escapeHtml(row.asset_class)}</td>
              <td>${escapeHtml(formatValue(row.mdd_1y_krw, 4))}</td>
              <td>${escapeHtml(formatValue(row.cvar_95_1y_krw, 4))}</td>
              <td>${escapeHtml(formatValue(row.sharpe_1y_krw_proxy, 3))}</td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
  `;
}

function directionChipClass(direction) {
  if (direction === 'positive') return 'positive';
  if (direction === 'negative') return 'negative';
  if (direction === 'neutral') return 'neutral';
  return 'warning';
}

function directionLabel(direction) {
  if (direction === 'positive') return '같은 방향';
  if (direction === 'negative') return '반대 방향';
  if (direction === 'neutral') return '중립';
  return '불명';
}

function sensitivityLevelChipClass(level) {
  if (level === 'high') return 'positive';
  if (level === 'medium') return '';
  return 'warning';
}

function renderSensitivitySection(data, preferredTicker = null) {
  const root = document.getElementById('asset-sensitivity');
  const chip = document.getElementById('sensitivity-chip');
  const preview = document.getElementById('sensitivity-asset-preview');
  const input = document.getElementById('sensitivity-asset-input');
  const rows = data.assetSensitivities || [];

  if (!rows.length) {
    chip.textContent = '-';
    preview.textContent = '민감도 산출물이 아직 없습니다.';
    root.innerHTML = '<div class="empty-state">자산 민감도 데이터가 없습니다.</div>';
    return;
  }

  const uniqueTickers = [...new Set(rows.map((row) => row.ticker).filter(Boolean))].sort();
  const requestedTicker = resolveSensitivityTicker(
    preferredTicker || input.value || state.sensitivityTicker || data.singleAssetTicker,
    rows,
  );
  const activeTicker = requestedTicker || state.sensitivityTicker || (data.singleAssetTicker && uniqueTickers.includes(data.singleAssetTicker) ? data.singleAssetTicker : null) || uniqueTickers[0];
  state.sensitivityTicker = activeTicker;

  if (document.activeElement !== input) {
    input.value = assetLabelForTicker(activeTicker);
  }

  const filtered = rows.filter((row) => row.ticker === activeTicker);
  const displayName = filtered[0]?.displayName || assetLabelForTicker(activeTicker);
  const structuralTags = [...new Set(filtered.flatMap((row) => String(row.structural_tags || '').split('|').filter(Boolean)))];
  const maxMagnitude = Math.max(...filtered.map((row) => Number(row.magnitude || 0)), 0.0001);

  chip.textContent = displayName;
  preview.textContent = `${displayName} (${activeTicker}) · factor ${filtered.length}개`;

  root.innerHTML = `
    <div class="scenario-card">
      <div class="scenario-title">
        <h3>${escapeHtml(displayName)} (${escapeHtml(activeTicker)})</h3>
        <div class="metric-pills">
          ${structuralTags.length
            ? structuralTags.map((tag) => `<span class="metric-pill neutral">${escapeHtml(tag)}</span>`).join('')
            : '<span class="metric-pill neutral">structural tag 없음</span>'}
        </div>
      </div>
      <div class="helper-text compact">direction은 같은 방향/반대 방향, magnitude는 반응 강도, 민감도 강도는 현재 기준의 약/중/강 수준입니다.</div>
    </div>
    <div class="sensitivity-grid">
      ${filtered.map((row) => {
        const sensitivityLevel = row.sensitivity_level || row.confidence || 'low';
        const width = `${(Number(row.magnitude || 0) / maxMagnitude) * 100}%`;
        const interpretation = row.direction === 'positive'
          ? row.sign_positive_meaning
          : row.direction === 'negative'
            ? row.sign_negative_meaning
            : '민감도 방향성이 뚜렷하지 않음';
        return `
          <article class="sensitivity-card">
            <div class="sensitivity-card-head">
              <div>
                <h3>${escapeHtml(row.factor_label || row.factor)}</h3>
                <p>${escapeHtml(interpretation || '')}</p>
              </div>
              <div class="sensitivity-meta">
                <span class="metric-pill ${directionChipClass(row.direction)}">${escapeHtml(directionLabel(row.direction))}</span>
                <span class="metric-pill ${sensitivityLevelChipClass(sensitivityLevel)}">민감도 강도 ${escapeHtml(String(sensitivityLevel).toUpperCase())}</span>
              </div>
            </div>
            <div class="sensitivity-bar-wrap">
              <div class="sensitivity-bar-caption">
                <span>Magnitude</span>
                <strong>${escapeHtml(formatValue(row.magnitude, 4))}</strong>
              </div>
              <div class="bar-track"><div class="bar-fill" style="width:${width}"></div></div>
            </div>
            <div class="sensitivity-tags">
              <span class="chip-soft">basis: ${escapeHtml(row.value_basis || '-')}</span>
              <span class="chip-soft">raw: ${escapeHtml(formatValue(row.raw_value, 4))}</span>
            </div>
            <p>${escapeHtml(row.evidence_metrics || '')}</p>
          </article>
        `;
      }).join('')}
    </div>
  `;
}

function renderNextActions(actions) {
  const root = document.getElementById('next-actions');
  root.replaceChildren();
  (actions && actions.length ? actions : ['추가 액션 없음']).forEach((item) => {
    const li = document.createElement('li');
    li.textContent = item;
    root.appendChild(li);
  });
}

function renderArtifacts(artifacts) {
  const root = document.getElementById('artifact-links');
  root.innerHTML = Object.entries(artifacts || {}).map(([key, path]) => `
    <a class="artifact-link" href="/artifact/${encodeArtifactPath(path)}" target="_blank" rel="noreferrer">
      <div>
        <strong>${escapeHtml(key)}</strong>
        <small>${escapeHtml(path)}</small>
      </div>
      <span>열기 ↗</span>
    </a>
  `).join('');
}

async function loadDashboard(runId) {
  status('데이터를 불러오는 중입니다…');
  try {
    const data = await fetchJson(`/api/dashboard?run_id=${encodeURIComponent(runId)}`);
    state.dashboard = data;
    state.currentRun = data.runId;
    renderRunSelect();
    renderOverview(data);
    renderCompareSection('portfolio-compare', 'portfolio-chip', data.portfolioCompare, `생성 ${data.generatedAt || '-'}`, '포트폴리오 비교 데이터가 없습니다.');
    renderCompareSection('single-asset-compare', 'single-asset-chip', data.singleAssetCompare, data.singleAssetTicker || '단일 종목 없음', '단일 종목 결과가 아직 없습니다.');
    renderAllocation('portfolio-allocation', data.portfolioBestDetail, '추천 포트폴리오 자산배분 데이터가 없습니다.');
    renderAllocation('single-allocation', data.singleAssetBestDetail, '단일 종목 추천 자산배분 데이터가 없습니다.');
    renderTopHedges(data.topHedges);
    renderRiskWatchlist(data.worstRiskAssets);
    renderSensitivitySection(data, data.singleAssetTicker || state.sensitivityTicker);
    renderNextActions(data.nextActions);
    renderArtifacts(data.artifacts);
    status(`Run ${data.runId} · 기준통화 ${data.meta.baseCurrency || 'KRW'} · ${data.generatedAt || 'snapshot'}`);
  } catch (error) {
    console.error(error);
    status(`대시보드를 불러오지 못했습니다: ${error.message}`, 'error');
  }
}

async function postJson(url, payload) {
  const response = await fetch(url, {
    method: 'POST',
    cache: 'no-store',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  const body = await response.json();
  if (!response.ok) {
    throw new Error(body.error || `Request failed: ${response.status}`);
  }
  return body;
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function waitForRunJob(jobId, { intervalMs = 1500, timeoutMs = 15 * 60 * 1000 } = {}) {
  const startedAt = Date.now();
  while (Date.now() - startedAt < timeoutMs) {
    const job = await fetchJson(`/api/run-status?job_id=${encodeURIComponent(jobId)}`);
    if (job.status === 'completed') {
      return job.result || job;
    }
    if (job.status === 'failed') {
      throw new Error(job.error || '분석 작업이 실패했습니다.');
    }
    await sleep(intervalMs);
  }
  throw new Error('분석 작업 대기 시간이 초과되었습니다.');
}

async function runAnalysis(payload, pendingMessage) {
  status(pendingMessage);
  setLoading(true, '분석 중…', pendingMessage);
  try {
    const job = await postJson('/api/run', payload);
    const result = job.jobId ? await waitForRunJob(job.jobId) : job;
    if (result.runId && !state.runs.includes(result.runId)) {
      state.runs.unshift(result.runId);
      state.runs = [...new Set(state.runs)];
    }
    state.currentRun = result.runId || state.currentRun;
    await loadDashboard(state.currentRun);
    status(`분석 완료 · snapshot ${state.currentRun}`);
    setLoading(true, '분석 완료!', '최신 결과를 화면에 반영했습니다.', { requireConfirm: true });
  } catch (error) {
    console.error(error);
    status(`분석 실행 실패: ${error.message}`, 'error');
    setLoading(true, '분석 실패', error.message, { requireConfirm: true, isError: true });
  }
}

async function bootstrap() {
  try {
    const [payload, assetPayload] = await Promise.all([fetchJson('/api/runs'), fetchJson('/api/assets')]);
    state.runs = payload.runs || [];
    state.currentRun = payload.latestRunId;
    state.assets = assetPayload.assets || [];
    renderAssetOptions();
    seedPortfolioRows();
    updateSingleAssetPreview();
    renderRunSelect();
    if (!state.currentRun) {
      status('표시할 분석 결과가 없습니다. 먼저 파이프라인을 실행해 주세요.', 'error');
      return;
    }
    await loadDashboard(state.currentRun);
  } catch (error) {
    console.error(error);
    status(`초기화 실패: ${error.message}`, 'error');
  } finally {
    setLoading(false);
  }
}

document.getElementById('refresh-button').addEventListener('click', async () => {
  await loadDashboard(state.currentRun || state.runs[0]);
});

document.getElementById('single-run-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const selectedAsset = resolveAssetOption(document.getElementById('single-asset-input').value);
  if (!selectedAsset) {
    status('지원 자산명을 정확히 선택해 주세요.', 'error');
    return;
  }
  await runAnalysis(
    {
      mode: 'single_asset',
      singleAsset: selectedAsset.ticker,
      baseAmountKrw: Number(document.getElementById('single-base-amount-input').value || 0),
      hedgeBudgetKrw: Number(document.getElementById('single-budget-input').value || 0),
      maxComboSize: Number(document.getElementById('single-combo-input').value || 1),
    },
    '단일 자산 분석을 실행하는 중입니다…',
  );
});

document.getElementById('portfolio-run-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const rawRows = collectPortfolioRows();
  const invalidRow = rawRows.find((row) => !resolveAssetOption(row.asset) || Number(row.amountKrw) <= 0);
  if (invalidRow) {
    status('포트폴리오의 각 행에 지원 자산명과 0보다 큰 보유 금액을 정확히 입력해 주세요.', 'error');
    return;
  }
  const rows = rawRows.map((row) => {
    const asset = resolveAssetOption(row.asset);
    return { asset: asset.ticker, amountKrw: row.amountKrw };
  });
  if (!rows.length) {
    status('포트폴리오 자산을 1개 이상 입력해 주세요.', 'error');
    return;
  }
  await runAnalysis(
    {
      mode: 'portfolio',
      portfolioRows: rows,
      hedgeBudgetKrw: Number(document.getElementById('portfolio-budget-input').value || 0),
      maxComboSize: Number(document.getElementById('portfolio-combo-input').value || 1),
    },
    '포트폴리오 분석을 실행하는 중입니다…',
  );
});

document.getElementById('single-asset-input').addEventListener('input', updateSingleAssetPreview);
document.getElementById('sensitivity-asset-input').addEventListener('change', () => {
  if (state.dashboard) renderSensitivitySection(state.dashboard, document.getElementById('sensitivity-asset-input').value);
});
document.getElementById('loading-confirm-button').addEventListener('click', () => {
  setLoading(false);
});
document.getElementById('add-portfolio-row').addEventListener('click', () => {
  document.getElementById('portfolio-rows').appendChild(createPortfolioRow());
  updatePortfolioSummary();
});

bootstrap();
