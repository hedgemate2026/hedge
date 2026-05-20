const scenarioState = {
  runs: [],
  currentRun: null,
  dashboard: null,
};

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
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
    const body = await response.json().catch(() => ({}));
    throw new Error(body.error || `Request failed: ${response.status}`);
  }
  return response.json();
}

function formatValue(value, digits = 2) {
  if (value === null || value === undefined || value === '') return '-';
  const n = Number(value);
  if (Number.isNaN(n)) return String(value);
  return n.toFixed(digits);
}

function formatCount(value) {
  if (value === null || value === undefined || value === '') return '-';
  const n = Number(value);
  if (Number.isNaN(n)) return String(value);
  return Math.round(n).toLocaleString('ko-KR');
}

function chipClass(state) {
  const normalized = String(state || '').toUpperCase();
  if (['ACTIVE', 'STRONG', 'RISK_ON', 'PASS', 'OK'].includes(normalized)) return 'positive';
  if (['WATCH', 'STRESS', 'WARN', 'PROVISIONAL'].includes(normalized)) return 'warning';
  if (['OFF', 'NEUTRAL', 'INSUFFICIENT_HISTORY'].includes(normalized)) return 'neutral';
  return '';
}

function status(message, type = '') {
  const root = document.getElementById('scenario-status-banner');
  root.replaceChildren();
  if (!message) return;
  const node = document.createElement('div');
  node.className = `status-message ${type === 'error' ? 'error' : ''}`.trim();
  node.textContent = message;
  root.appendChild(node);
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

function renderRunSelect() {
  const select = document.getElementById('scenario-run-select');
  select.replaceChildren();
  scenarioState.runs.forEach((run) => {
    const option = document.createElement('option');
    option.value = run;
    option.textContent = run;
    select.appendChild(option);
  });
  if (scenarioState.currentRun) select.value = scenarioState.currentRun;
  select.onchange = async (event) => {
    scenarioState.currentRun = event.target.value;
    await loadScenarioDashboard(scenarioState.currentRun);
  };
}

function renderOverview(data) {
  const meta = data.meta || {};
  const active = data.topActiveScenarios || [];
  document.getElementById('scenario-overview-grid').innerHTML = [
    metricCard('시장국면 실행 결과', data.runId || '-', data.generatedAt || '생성 시각'),
    metricCard('기준일', data.asOfDate || '-', data.dataFreshnessNote || `데이터 최신 행 ${data.dataAsOfDate || '-'}`),
    metricCard('상위 시나리오', `${active.length}개`, 'ACTIVE / WATCH 후보'),
    metricCard('최종 행 수', formatCount(meta.finalRowCount), meta.pipelinePhase || '최종 병합 결과'),
    metricCard('이벤트 보조신호', formatCount(meta.overlayRowCount), '검토된 fixture 기반 이벤트 행 수'),
    metricCard('검증 케이스', `${formatCount(meta.validationOkCases)}/${formatCount(meta.validationCases)}`, 'OK / TOTAL'),
  ].join('');
}

function renderScoreMeter(score) {
  const width = Math.max(0, Math.min(100, Number(score) || 0));
  return `
    <div class="score-meter">
      <div class="score-meter-fill" style="width:${width}%"></div>
    </div>
  `;
}

function renderTopActiveScenarios(rows) {
  const root = document.getElementById('top-active-scenarios');
  if (!rows || !rows.length) {
    root.innerHTML = '<div class="empty-state">상위 활성 시나리오 데이터가 없습니다.</div>';
    return;
  }
  root.innerHTML = `
    <div class="scenario-stack">
      ${rows.map((row) => `
        <article class="scenario-result-card">
          <div class="scenario-result-head">
            <div>
              <h3>${escapeHtml(row.scenario_name_ko || row.scenario_name || row.scenario_code)}</h3>
              <p>${escapeHtml(row.scenario_name || row.scenario_code)} · ${escapeHtml(row.lens || '-')}</p>
            </div>
            <span class="metric-pill ${chipClass(row.final_display_state)}">${escapeHtml(row.final_display_state || '-')}</span>
          </div>
          <div class="scenario-score-row">
            <span>Score ${escapeHtml(formatValue(row.final_score, 2))}</span>
            <strong>Confidence ${escapeHtml(formatValue(row.final_confidence, 2))}</strong>
          </div>
          ${renderScoreMeter(row.final_score)}
        </article>
      `).join('')}
    </div>
  `;
}

function renderLensSummary(rows, stateCounts) {
  const root = document.getElementById('lens-summary');
  const lensRows = rows || [];
  root.innerHTML = `
    <div class="state-chip-row">
      ${(stateCounts || []).map((item) => `<span class="metric-pill ${chipClass(item.state)}">${escapeHtml(item.state)} ${escapeHtml(item.count)}</span>`).join('')}
    </div>
    <div class="scenario-stack">
      ${lensRows.length ? lensRows.map((row) => `
        <article class="scenario-result-card compact-card">
          <div class="scenario-result-head">
            <div>
              <h3>${escapeHtml(row.lens)}</h3>
              <p>${escapeHtml(row.topScenario || '대표 시나리오 없음')}</p>
            </div>
            <span class="section-chip">${escapeHtml(row.count)}개</span>
          </div>
          <div class="scenario-score-row">
            <span>Top score</span>
            <strong>${escapeHtml(formatValue(row.topScore, 2))}</strong>
          </div>
          ${renderScoreMeter(row.topScore)}
        </article>
      `).join('') : '<div class="empty-state">렌즈 요약 데이터가 없습니다.</div>'}
    </div>
  `;
}

function renderLeaderCards(targetId, rows, options = {}) {
  const root = document.getElementById(targetId);
  if (!root) return;
  if (!rows || !rows.length) {
    root.innerHTML = `<div class="empty-state">${escapeHtml(options.emptyText || '표시할 데이터가 없습니다.')}</div>`;
    return;
  }
  root.innerHTML = `
    <div class="scenario-stack">
      ${rows.map((row) => {
        const title = row.scenario_name_ko || row.nowcast_name_ko || row.scenario_name || row.nowcast_code || row.scenario_code;
        const state = row.display_state || row.status || row.final_display_state || row.raw_state;
        const interpretation = row.market_interpretation_ko || row.interpretation_ko || '';
        return `
          <article class="scenario-result-card compact-card">
            <div class="scenario-result-head">
              <div>
                <h3>${escapeHtml(title)}</h3>
                <p>${escapeHtml(row.lens || row.scenario_code || row.nowcast_code || '-')}</p>
              </div>
              <span class="metric-pill ${chipClass(state)}">${escapeHtml(state || '-')}</span>
            </div>
            <div class="scenario-score-row">
              <span>Score ${escapeHtml(formatValue(row.score, 2))}</span>
              <strong>Confidence ${escapeHtml(formatValue(row.confidence, 2))}</strong>
            </div>
            ${renderScoreMeter(row.score)}
            ${interpretation ? `<p class="scenario-card-copy">${escapeHtml(interpretation)}</p>` : ''}
          </article>
        `;
      }).join('')}
    </div>
  `;
}

function renderMarketStateTable(rows) {
  const root = document.getElementById('market-state-table');
  if (!rows || !rows.length) {
    root.innerHTML = '<div class="empty-state">기준일 시장상태 데이터가 없습니다.</div>';
    return;
  }
  root.innerHTML = `
    <div class="table-wrap">
      <table class="data-table scenario-data-table">
        <thead>
          <tr>
            <th>시나리오</th><th>관점</th><th>상태</th><th>점수</th><th>신뢰도</th><th>이벤트</th>
          </tr>
        </thead>
        <tbody>
          ${rows.map((row) => `
            <tr>
              <td><strong>${escapeHtml(row.scenario_name_ko || row.scenario_name || row.scenario_code)}</strong><div class="ticker-caption">${escapeHtml(row.scenario_code)}</div></td>
              <td>${escapeHtml(row.lens || '-')}</td>
              <td><span class="metric-pill ${chipClass(row.final_display_state)}">${escapeHtml(row.final_display_state || '-')}</span></td>
              <td>${escapeHtml(formatValue(row.final_score, 2))}</td>
              <td>${escapeHtml(formatValue(row.final_confidence, 2))}</td>
              <td>${escapeHtml(row.overlay_applied || 'N')} · ${escapeHtml(formatCount(row.event_count))}</td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
  `;
}

function renderBulletPanel(targetId, bullets, emptyText) {
  const root = document.getElementById(targetId);
  if (!root) return;
  root.replaceChildren();
  (bullets && bullets.length ? bullets : [emptyText]).forEach((item) => {
    const li = document.createElement('li');
    li.textContent = item;
    root.appendChild(li);
  });
}

function renderEventOverlay(payload) {
  const root = document.getElementById('event-overlay');
  const metadata = payload?.metadata || {};
  const rows = payload?.rows || [];
  root.innerHTML = `
    <div class="scenario-stat-strip">
      <span class="metric-pill">articles ${escapeHtml(formatCount(metadata.article_count))}</span>
      <span class="metric-pill">events ${escapeHtml(formatCount(rows.length))}</span>
    </div>
    <ul class="bullet-list scenario-bullet-panel">
      ${(payload?.reviewBullets?.length ? payload.reviewBullets : ['이벤트 오버레이 요약이 없습니다.']).map((item) => `<li>${escapeHtml(item)}</li>`).join('')}
    </ul>
  `;
}

function renderValidation(payload) {
  const root = document.getElementById('validation-review');
  const metadata = payload?.metadata || {};
  root.innerHTML = `
    <div class="scenario-stat-strip">
      <span class="metric-pill positive">OK ${escapeHtml(formatCount(metadata.ok_case_count))}</span>
      <span class="metric-pill warning">Total ${escapeHtml(formatCount(metadata.case_count))}</span>
      <span class="metric-pill neutral">Insufficient ${escapeHtml(formatCount(metadata.insufficient_history_case_count))}</span>
    </div>
    <ul class="bullet-list scenario-bullet-panel">
      ${(payload?.reviewBullets?.length ? payload.reviewBullets : ['히스토리 검증 요약이 없습니다.']).map((item) => `<li>${escapeHtml(item)}</li>`).join('')}
    </ul>
  `;
}

function renderArtifacts(artifacts) {
  const root = document.getElementById('scenario-artifacts');
  root.innerHTML = Object.entries(artifacts || {}).map(([key, path]) => `
    <a class="artifact-link" href="/artifact/${encodeArtifactPath(path)}" target="_blank" rel="noreferrer">
      <div>
        <strong>${escapeHtml(key)}</strong>
        <small>${escapeHtml(path)}</small>
      </div>
      <span>열기 ↗</span>
    </a>
  `).join('') || '<div class="empty-state">연결된 산출물이 없습니다.</div>';
}

function renderScenarioDashboard(data) {
  scenarioState.dashboard = data;
  scenarioState.currentRun = data.runId;
  scenarioState.runs = data.runs || scenarioState.runs;
  renderRunSelect();
  document.getElementById('scenario-date-chip').textContent = data.asOfDate || '-';
  renderOverview(data);
  renderTopActiveScenarios(data.topActiveScenarios);
  renderLensSummary(data.lensSummary, data.stateCounts);
  renderLeaderCards('scenario-vector-leaders', data.scenarioVectorLeaders, { emptyText: '시나리오 벡터 데이터가 없습니다.' });
  renderLeaderCards('nowcast-leaders', data.nowcastLeaders, { emptyText: '단기 보조신호 데이터가 없습니다.' });
  renderMarketStateTable(data.topMarketRows);
  renderEventOverlay(data.eventOverlay);
  renderValidation(data.validation);
  renderBulletPanel('scenario-summary', data.summaryBullets, '시장국면 진단 요약이 없습니다.');
  renderArtifacts(data.artifacts);
  const freshness = data.dataFreshnessNote ? ` · ${data.dataFreshnessNote}` : '';
  status(`시장국면 실행 ${data.runId} · 화면 기준일 ${data.asOfDate || '-'} · 데이터 기준일 ${data.dataAsOfDate || '-'} · 생성 ${data.generatedAt || '-'}${freshness}`);
}

async function loadScenarioDashboard(runId) {
  status('시장국면 진단 결과를 불러오는 중입니다...');
  try {
    const query = runId ? `?run_id=${encodeURIComponent(runId)}` : '';
    const data = await fetchJson(`/api/scenario-dashboard${query}`);
    renderScenarioDashboard(data);
  } catch (error) {
    console.error(error);
    status(`시장국면 진단 결과를 불러오지 못했습니다: ${error.message}`, 'error');
  }
}

async function bootstrap() {
  try {
    const payload = await fetchJson('/api/scenario-runs');
    scenarioState.runs = payload.runs || [];
    scenarioState.currentRun = payload.latestRunId;
    renderRunSelect();
    if (!scenarioState.currentRun) {
      status('표시할 시나리오 리서치 결과가 없습니다.', 'error');
      return;
    }
    await loadScenarioDashboard(scenarioState.currentRun);
  } catch (error) {
    console.error(error);
    status(`초기화 실패: ${error.message}`, 'error');
  }
}

document.getElementById('scenario-refresh-button').addEventListener('click', async () => {
  await loadScenarioDashboard(scenarioState.currentRun || scenarioState.runs[0]);
});

bootstrap();
