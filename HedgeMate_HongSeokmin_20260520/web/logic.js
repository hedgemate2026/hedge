const logicState = {
  scenario: null,
  hedge: null,
};

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
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

function encodeArtifactPath(path) {
  return encodeURI(String(path ?? '')).replaceAll('#', '%23').replaceAll('?', '%3F');
}

function setStatus(message, type = '') {
  const root = document.getElementById('logic-status-banner');
  root.innerHTML = message
    ? `<div class="status-message ${type === 'error' ? 'error' : ''}">${escapeHtml(message)}</div>`
    : '';
}

const statusLabels = [
  { label: 'Implemented', detail: 'Phase 4/6 산출물과 HedgeMate 계산 엔진', tone: 'positive' },
  { label: 'API-free', detail: 'Phase 5 fixture provider + schema validation', tone: 'info' },
  { label: 'Deferred', detail: 'Gemini API 실호출과 live news crawling', tone: 'warning' },
  { label: 'Needs Fix', detail: '최신성 정합성, DQ 정책, 루트 테스트 실행성', tone: 'neutral' },
];

const pipelineNodes = [
  {
    stage: '1. Market Prices / FX',
    status: 'Implemented',
    input: 'Yahoo/cache raw market data, FX, benchmark',
    logic: 'USD 자산을 KRW 기준으로 환산하고 공통 수익률 구간을 만든다.',
    output: 'KRW returns, DQ rows, feature rows',
    artifact: 'features_summary, dq_result',
    why: '모든 리스크 지표를 같은 통화 기준으로 비교하기 위한 바닥이다.',
  },
  {
    stage: '2. Phase 4 Structured Scenario',
    status: 'Implemented',
    input: 'SPY, QQQ, SOXX, TLT, UUP, KRW=X, EWY, FXI',
    logic: '가격 proxy를 factor로 압축해 장세별 structured_score를 계산한다.',
    output: 'scenario_state_daily, current_scenario_vector',
    artifact: 'scenario_state_daily, current_scenario_vector',
    why: '오늘 시장이 어떤 위험 국면인지 추천 이전에 먼저 정의한다.',
  },
  {
    stage: '3. Phase 5 Event Overlay',
    status: 'API-free',
    input: '뉴스/정책 fixture, 추후 Gemini JSON extraction',
    logic: 'event_type, region, direction, severity, evidence_span을 구조화한다.',
    output: 'event_overlay_article, event_overlay_daily',
    artifact: 'event_overlay_metadata, event_overlay_review',
    why: '비정형 이벤트는 장세 판단의 보조 증거로만 반영한다.',
  },
  {
    stage: '4. Phase 6 Final Market State',
    status: 'Implemented',
    input: 'Phase 4 structured score + Phase 5 event overlay',
    logic: '정형 점수 85%, 이벤트 오버레이 15%로 최종 장세를 병합한다.',
    output: 'final_score, final_confidence, final_display_state',
    artifact: 'final_market_state_daily, top_active_scenarios',
    why: 'HedgeMate가 소비할 최종 장세 벡터를 만든다.',
  },
  {
    stage: '5. Asset x Scenario Sensitivity',
    status: 'Implemented',
    input: '자산별 beta/corr/stress feature + scenario vector',
    logic: '각 자산이 시나리오에 취약한지, 방어적인지, 수혜인지 추정한다.',
    output: 'scenario_beta, direction, evidence_quality',
    artifact: 'asset_scenario_sensitivity',
    why: '추천 후보가 진짜 헷지인지 같은 방향 베팅인지 구분한다.',
  },
  {
    stage: '6. Portfolio Vulnerability',
    status: 'Implemented',
    input: '현재 포트폴리오 weights + 자산별 민감도',
    logic: 'active adverse scenario 기준 취약도와 후보 추가 후 delta를 계산한다.',
    output: 'scenario_vulnerability_delta, factor_concentration_penalty',
    artifact: 'portfolio_1to1_hedge, portfolio_multi_hedge',
    why: '후보가 포트폴리오의 위험 노출을 실제로 낮추는지 본다.',
  },
  {
    stage: '7. Recommendation Gate',
    status: 'Implemented',
    input: 'CVaR/MDD/Stress/Beta/Corr/DQ/candidate role',
    logic: '계산 가능성과 추천 가능성을 분리해 Gate를 통과시킨다.',
    output: 'PASS_RECOMMEND, REFERENCE_ONLY, FAIL_GATE',
    artifact: 'recommendation_status_qa',
    why: '좋아 보이는 비교안과 정식 추천안을 섞지 않는다.',
  },
  {
    stage: '8. Decision Output',
    status: 'Implemented',
    input: 'Gate result + explanation components',
    logic: '추천 사유를 정량 개선과 시나리오 취약도 관점으로 설명한다.',
    output: '추천안/참고안/실패 사유, report, dashboard',
    artifact: 'result_md, dashboard, logic map',
    why: '사용자가 숫자와 이유를 함께 보고 판단하도록 만든다.',
  },
];

const formulaCards = [
  {
    title: 'Phase 6 final market state',
    code: 'final_score = 0.85 * structured_score\n            + 0.15 * event_overlay_score',
    note: '비정형 뉴스는 장세를 단독 결정하지 않고 정형 장세 점수의 보조 근거로만 반영한다.',
  },
  {
    title: 'Hedge recommendation score',
    code: 'hedge_score = CVaR improvement\n            + MDD improvement\n            + Stress improvement\n            + Scenario vulnerability reduction\n            + Beta/Corr exposure reduction\n            + Factor concentration relief\n            + Liquidity / explainability',
    note: '수익률 최대화보다 손실 완화와 취약도 감소를 우선한다.',
  },
];

const gateSteps = [
  ['Calculable', '공통 수익률과 포트폴리오 지표 계산 가능'],
  ['Data Quality', 'DQ FAIL 제외, WARN은 신뢰도/참고안으로 관리'],
  ['Risk Improvement', 'CVaR, MDD, Stress, Beta/Corr 개선 확인'],
  ['Scenario Vulnerability', '현재 adverse scenario 취약도 감소 확인'],
  ['Candidate Role', 'hedge_candidate / conditional / diagnostic 분리'],
  ['Recommendation Status', 'PASS_RECOMMEND / REFERENCE_ONLY / FAIL_GATE'],
];

const artifactGroups = [
  {
    group: 'Phase 4',
    items: ['scenario_state_daily_<run_id>.csv', 'current_scenario_vector_<run_id>.csv/json'],
  },
  {
    group: 'Phase 5',
    items: ['event_overlay_article_<run_id>.csv', 'event_overlay_daily_<run_id>.csv', 'event_overlay_metadata_<run_id>.json'],
  },
  {
    group: 'Phase 6',
    items: ['final_market_state_daily_<run_id>.csv', 'top_active_scenarios_<run_id>.json'],
  },
  {
    group: 'HedgeMate',
    items: ['asset_scenario_sensitivity_<run_id>.csv', 'portfolio_1to1_hedge_<run_id>.csv', 'portfolio_multi_hedge_<run_id>.csv', 'recommendation_status_qa_<run_id>.md'],
  },
];

function toneClass(status) {
  if (status === 'Implemented') return 'positive';
  if (status === 'API-free') return 'info';
  if (status === 'Deferred') return 'warning';
  return 'neutral';
}

function renderStatusStrip() {
  document.getElementById('logic-status-strip').innerHTML = statusLabels.map((item) => `
    <article class="logic-status-card ${escapeHtml(item.tone)}">
      <strong>${escapeHtml(item.label)}</strong>
      <span>${escapeHtml(item.detail)}</span>
    </article>
  `).join('');
}

function renderPipeline() {
  document.getElementById('logic-pipeline').innerHTML = pipelineNodes.map((node) => `
    <article class="logic-node">
      <div class="logic-node-head">
        <h3>${escapeHtml(node.stage)}</h3>
        <span class="logic-chip ${toneClass(node.status)}">${escapeHtml(node.status)}</span>
      </div>
      <dl class="logic-dl">
        <dt>Input</dt><dd>${escapeHtml(node.input)}</dd>
        <dt>Logic</dt><dd>${escapeHtml(node.logic)}</dd>
        <dt>Output</dt><dd>${escapeHtml(node.output)}</dd>
        <dt>Artifact</dt><dd>${escapeHtml(node.artifact)}</dd>
      </dl>
      <p>${escapeHtml(node.why)}</p>
    </article>
  `).join('');
}

function renderFormulas() {
  document.getElementById('logic-formulas').innerHTML = formulaCards.map((item) => `
    <article class="logic-formula-card">
      <h3>${escapeHtml(item.title)}</h3>
      <pre><code>${escapeHtml(item.code)}</code></pre>
      <p>${escapeHtml(item.note)}</p>
    </article>
  `).join('');
}

function renderGate() {
  document.getElementById('logic-gate').innerHTML = gateSteps.map(([title, detail], index) => `
    <div class="logic-gate-step">
      <span>${index + 1}</span>
      <div>
        <strong>${escapeHtml(title)}</strong>
        <p>${escapeHtml(detail)}</p>
      </div>
    </div>
  `).join('');
}

function renderPhase5() {
  document.getElementById('logic-phase5').innerHTML = `
    <div class="logic-phase-grid">
      <div>
        <h3>지금 가능한 것</h3>
        <ul class="bullet-list">
          <li>fixture provider</li>
          <li>provider schema validation</li>
          <li>article / daily overlay 생성</li>
          <li>review queue와 metadata 추적</li>
        </ul>
      </div>
      <div>
        <h3>Gemini key 이후</h3>
        <ul class="bullet-list">
          <li>gemini_provider 실제 client 연결</li>
          <li>JSON schema 강제 prompt</li>
          <li>low confidence needs_review 처리</li>
          <li>live news source 연결</li>
        </ul>
      </div>
    </div>
  `;
}

function renderArtifacts() {
  document.getElementById('logic-artifacts').innerHTML = artifactGroups.map((group) => `
    <article class="logic-artifact-card">
      <h3>${escapeHtml(group.group)}</h3>
      <ul>
        ${group.items.map((item) => `<li><code>${escapeHtml(item)}</code></li>`).join('')}
      </ul>
    </article>
  `).join('');
}

function renderLiveStatus() {
  const scenario = logicState.scenario;
  const hedge = logicState.hedge;
  const eventMeta = scenario?.eventOverlay?.metadata || {};
  const topScenario = scenario?.topActiveScenarios?.[0];
  const dq = hedge?.dqSummary || {};
  const validation = hedge?.validationSummary || {};
  const links = [];
  const artifacts = {
    scenarioVector: scenario?.artifacts?.scenarioVector,
    eventOverlayMetadata: scenario?.artifacts?.eventOverlayMetadata,
    finalMarketState: scenario?.artifacts?.finalMarketState,
    portfolioMulti: hedge?.artifacts?.portfolioMulti,
  };
  Object.entries(artifacts).forEach(([label, path]) => {
    if (path) links.push(`<a href="/artifact/${encodeArtifactPath(path)}" target="_blank" rel="noreferrer">${escapeHtml(label)}</a>`);
  });

  document.getElementById('logic-live-status').innerHTML = `
    <div class="logic-live-grid">
      <div><span>Scenario Run</span><strong>${escapeHtml(scenario?.runId || '-')}</strong></div>
      <div><span>Top Scenario</span><strong>${escapeHtml(topScenario?.scenario_name_ko || topScenario?.scenario_code || '-')}</strong></div>
      <div><span>Phase 5 Provider</span><strong>${escapeHtml(eventMeta.provider || eventMeta.input_mode || '-')}</strong></div>
      <div><span>Event Rows</span><strong>${escapeHtml(eventMeta.daily_overlay_count ?? eventMeta.dailyOverlayCount ?? '-')}</strong></div>
      <div><span>Hedge Run</span><strong>${escapeHtml(hedge?.runId || '-')}</strong></div>
      <div><span>DQ</span><strong>PASS ${escapeHtml(dq.pass ?? 0)} / WARN ${escapeHtml(dq.warn ?? 0)} / FAIL ${escapeHtml(dq.fail ?? 0)}</strong></div>
      <div><span>Metric Tests</span><strong>PASS ${escapeHtml(validation.pass ?? 0)} / FAIL ${escapeHtml(validation.fail ?? 0)}</strong></div>
    </div>
    <div class="logic-live-links">${links.join('') || '<span>연결된 live artifact가 없습니다.</span>'}</div>
  `;
}

async function loadLiveData() {
  setStatus('Logic Map base model loaded. 최신 산출물 상태를 확인하는 중입니다...');
  try {
    const [scenarioRuns, hedgeRuns] = await Promise.all([
      fetchJson('/api/scenario-runs'),
      fetchJson('/api/runs'),
    ]);
    const jobs = [];
    if (scenarioRuns.latestRunId) jobs.push(fetchJson(`/api/scenario-dashboard?run_id=${encodeURIComponent(scenarioRuns.latestRunId)}`).then((data) => { logicState.scenario = data; }));
    if (hedgeRuns.latestRunId) jobs.push(fetchJson(`/api/dashboard?run_id=${encodeURIComponent(hedgeRuns.latestRunId)}`).then((data) => { logicState.hedge = data; }));
    await Promise.all(jobs);
    renderLiveStatus();
    setStatus('최신 로컬 산출물 상태를 반영했습니다.');
  } catch (error) {
    console.error(error);
    renderLiveStatus();
    setStatus(`Live artifact status unavailable: ${error.message}`, 'error');
  }
}

function bootstrap() {
  renderStatusStrip();
  renderPipeline();
  renderFormulas();
  renderGate();
  renderPhase5();
  renderArtifacts();
  renderLiveStatus();
  loadLiveData();
}

bootstrap();
