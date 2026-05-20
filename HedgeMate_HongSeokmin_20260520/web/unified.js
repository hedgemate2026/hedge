const STATUS_LABELS = Object.freeze({
  PASS_RECOMMEND: "정식 추천 가능",
  REFERENCE_ONLY: "참고용 후보",
  FAIL_GATE: "기준 미통과 · 추천 아님",
  INSUFFICIENT_DATA: "데이터 부족",
});

const ACTION_STATUS_LABELS = Object.freeze({
  FORMAL_ACTION: "정식 실행 추천",
  REVIEW_ACTION: "검토 액션",
  RESEARCH_ONLY: "리서치 전용",
  FAIL_ACTION: "탈락 액션",
  NO_ACTION: "유효 액션 없음",
});

const ACTION_TYPE_LABELS = Object.freeze({
  ADD_HEDGE: "ADD_HEDGE",
  TRIM_AND_HEDGE: "TRIM_AND_HEDGE",
  REPLACE_SLEEVE: "REPLACE_SLEEVE",
});

const BACKTEST_QUALITY_LABELS = Object.freeze({
  HIGH: "검증 강도 높음",
  MEDIUM: "검증 강도 보통 · 표본 제한",
  LOW: "검증 강도 낮음",
  MISSING: "백테스트 없음",
});

const SCENARIO_LABELS = Object.freeze({
  higher_for_longer_long_rate_shock: "장기금리 부담장",
  slowdown_recession_deflation_risk: "경기 둔화·디플레이션 위험",
  stagflation_reinflation_energy_shock: "물가·에너지 재상승장",
  usd_strength_krw_weakness: "달러 강세·원화 약세장",
  china_trade_fragmentation_shock: "중국·무역 분절화 충격",
  acute_global_stress_liquidity_crunch: "글로벌 유동성 스트레스",
  korea_tail_risk_regime: "한국 꼬리위험 국면",
  semiconductor_ai_cycle_shock: "AI·반도체 사이클 충격",
  korea_domestic_financial_stress: "한국 내수 금융스트레스장",
  geopolitical_escalation_supply_shock: "지정학·공급망 충격",
  soft_landing_goldilocks: "연착륙·골디락스",
});

const SCENARIO_DESCRIPTIONS = Object.freeze({
  higher_for_longer_long_rate_shock: "미국의 고금리 장기화로 인해 국채 금리가 급등하며 성장주와 부채가 많은 기업에 부담을 주는 국면입니다.",
  slowdown_recession_deflation_risk: "성장률이 둔화되고 인플레이션이 가라앉으면서 경기 침체 및 디플레이션 우려가 부각되는 국면입니다.",
  stagflation_reinflation_energy_shock: "경기 침체 속에 유가 등 에너지 가격이 급등하며 물가가 다시 상승하는 고통스러운 국면입니다.",
  usd_strength_krw_weakness: "미국 금리 인상이나 글로벌 안전자산 선호로 인해 달러가 강세를 보이고 원화 가치가 하락하는 국면입니다.",
  china_trade_fragmentation_shock: "중국의 경기 둔화와 미중 갈등 등 글로벌 공급망 분절화로 인해 한국 수출 기업들이 충격을 받는 국면입니다.",
  acute_global_stress_liquidity_crunch: "글로벌 금융 시장의 유동성이 급격히 축소되며 자산 가격이 동반 폭락하는 신용 경색 국면입니다.",
  korea_tail_risk_regime: "한국 시장에 특유한 지정학적 위험이나 가계부채 등 잠재적 위험이 폭발하는 국면입니다.",
  semiconductor_ai_cycle_shock: "글로벌 IT/반도체 및 AI 수요의 급격한 둔화나 과잉 공급으로 인해 한국 주력 산업이 타격을 입는 국면입니다.",
  korea_domestic_financial_stress: "금리 인상 부담으로 인해 국내 부동산 프로젝트파이낸싱(PF) 및 제2금융권 신용 위험이 부각되는 국면입니다.",
  geopolitical_escalation_supply_shock: "지정학적 갈등 격화로 원자재 공급에 차질이 생기고 인플레이션 압력이 가중되는 국면입니다.",
  soft_landing_goldilocks: "물가가 안정되면서도 완만한 성장을 이어가는 골디락스 국면으로, 위험자산에 우호적인 시장입니다."
});

const TERM_DEFINITIONS = [
  ["CVaR", "나쁜 날 평균손실", "손실이 큰 날들만 모아 봤을 때 평균적으로 얼마나 잃는지 보여주는 지표"],
  ["MDD", "최대 낙폭", "고점에서 저점까지 가장 크게 빠진 폭"],
  ["Beta", "시장 민감도", "시장이 움직일 때 이 자산이 얼마나 같이 움직이는지 보여주는 지표"],
  ["Downside beta", "하락장 민감도", "시장이 떨어지는 날에 이 자산이 얼마나 같이 떨어지는지 보여주는 지표"],
  ["Stress", "위기 구간", "시장이 크게 흔들린 기간에서의 성과나 손실"],
  ["Sharpe", "위험 대비 성과", "감수한 위험에 비해 수익이 얼마나 효율적이었는지 보는 지표"],
];

const JOB_STATUS_LABELS = Object.freeze({
  running: "분석 실행 중",
  completed: "분석 완료",
  failed: "분석 실패",
  skipped_latest: "갱신 생략",
});

const JOB_STAGE_LABELS = Object.freeze({
  queued: "대기 중",
  "running HedgeMate analysis": "포트폴리오 헷지 후보 계산 중",
  "running scenario backtest": "과거 stress 구간 백테스트 중",
  "applying backtest gate": "추천 게이트 적용 중",
  "updating active dashboard bundle": "대시보드 결과 갱신 중",
  completed: "완료",
  refreshing: "시장데이터 갱신 중",
  "running refresh pipeline": "시장데이터 갱신 중",
});

const dom = {};
let payload = null;
let portfolioPreview = null;
let jobPollTimer = null;
let assetOptions = [];
let autoPreviewTimer = null;
let previewRequestId = 0;
let scenarioSensitivities = [];

document.addEventListener("DOMContentLoaded", () => {
  cacheDom();
  dom.refreshButton.addEventListener("click", loadDashboard);
  dom.addPortfolioRowButton.addEventListener("click", () => addPortfolioRow());
  dom.samplePortfolioButton.addEventListener("click", loadSamplePortfolio);
  dom.refreshMarketButton.addEventListener("click", refreshMarketData);
  dom.runAnalysisButton.addEventListener("click", runPortfolioAnalysis);
  document.addEventListener("click", (event) => {
    dom.portfolioRows.querySelectorAll(".portfolio-input-row").forEach((row) => {
      if (!row.contains(event.target)) hideAssetSuggestions(row);
    });
  });
  loadAssetOptions();
  loadSamplePortfolio();
  loadDataFreshness();
  renderLoading();
  loadDashboard();
});

function cacheDom() {
  dom.refreshButton = document.getElementById("refresh-button");
  dom.banner = document.getElementById("status-banner");
  dom.conclusionTitle = document.getElementById("conclusion-title");
  dom.conclusionCopy = document.getElementById("conclusion-copy");
  dom.bundleMeta = document.getElementById("active-bundle-meta");
  dom.summaryCards = document.getElementById("summary-cards");
  dom.vulnerabilitySection = document.getElementById("vulnerability-section");
  dom.vulnerabilityTop3Container = document.getElementById("vulnerability-top3-container");
  dom.contributorsSection = document.getElementById("contributors-section");
  dom.contributorsContainer = document.getElementById("contributors-container");
  dom.actionsSection = document.getElementById("actions-section");
  dom.actionsContainer = document.getElementById("actions-container");
  dom.trustGrid = document.getElementById("trust-grid");
  dom.termGrid = document.getElementById("term-grid");
  dom.expertGrid = document.getElementById("expert-grid");
  dom.portfolioRows = document.getElementById("portfolio-input-rows");
  dom.addPortfolioRowButton = document.getElementById("add-portfolio-row-button");
  dom.samplePortfolioButton = document.getElementById("sample-portfolio-button");
  dom.refreshMarketButton = document.getElementById("refresh-market-button");
  dom.runAnalysisButton = document.getElementById("run-analysis-button");
  dom.hedgeBudgetInput = document.getElementById("hedge-budget-input");
  dom.freshnessPanel = document.getElementById("freshness-panel");
  dom.previewPanel = document.getElementById("portfolio-preview-panel");
  dom.jobStatusPanel = document.getElementById("job-status-panel");
}

async function loadAssetOptions() {
  try {
    const payload = await fetchJson("/api/assets");
    assetOptions = payload.assets || [];
  } catch (error) {
    assetOptions = [];
  }
}

function normalizeSearch(value) {
  return String(value || "").toLowerCase().replace(/[^0-9a-z가-힣&+.^-]+/g, "");
}

function filterAssetOptions(query) {
  const normalized = normalizeSearch(query);
  const popularTickers = new Set(["005930.KS", "TSLA", "AAPL", "GLD", "SHY", "SPY", "QQQ", "TLT"]);
  const rows = assetOptions.length ? assetOptions : [];
  if (!normalized) {
    return rows.filter((item) => popularTickers.has(item.ticker)).slice(0, 8);
  }
  return rows
    .map((item) => {
      const search = normalizeSearch(item.searchText || `${item.label} ${item.ticker}`);
      const label = normalizeSearch(item.label);
      const ticker = normalizeSearch(item.ticker);
      const score = label.startsWith(normalized) ? 0 : ticker.startsWith(normalized) ? 1 : search.includes(normalized) ? 2 : 99;
      return { item, score };
    })
    .filter((row) => row.score < 99)
    .sort((a, b) => a.score - b.score || a.item.label.localeCompare(b.item.label, "ko"))
    .slice(0, 8)
    .map((row) => row.item);
}

function renderAssetSuggestions(row) {
  const input = row.querySelector(".portfolio-asset");
  const list = row.querySelector(".asset-suggestion-list");
  const matches = filterAssetOptions(input.value);
  if (!matches.length) {
    list.hidden = true;
    input.setAttribute("aria-expanded", "false");
    return;
  }
  list.innerHTML = matches.map((item, index) => `
    <button class="asset-suggestion ${index === 0 ? "active" : ""}" type="button" role="option" data-ticker="${escapeHtml(item.ticker)}">
      <strong>${escapeHtml(item.displayLabel || `${item.label} (${item.ticker})`)}</strong>
      <span>${escapeHtml(item.assetClass || "")}${item.aliases?.length ? ` · ${escapeHtml(item.aliases.slice(0, 3).join(", "))}` : ""}</span>
    </button>
  `).join("");
  list.querySelectorAll(".asset-suggestion").forEach((button) => {
    button.addEventListener("mousedown", (event) => {
      event.preventDefault();
      selectAssetOption(row, button.dataset.ticker);
    });
  });
  list.hidden = false;
  input.setAttribute("aria-expanded", "true");
}

function hideAssetSuggestions(row) {
  const list = row.querySelector(".asset-suggestion-list");
  const input = row.querySelector(".portfolio-asset");
  list.hidden = true;
  input.setAttribute("aria-expanded", "false");
}

function selectAssetOption(row, ticker) {
  const option = assetOptions.find((item) => item.ticker === ticker);
  if (!option) return;
  const input = row.querySelector(".portfolio-asset");
  input.value = option.label;
  input.dataset.ticker = option.ticker;
  hideAssetSuggestions(row);
  scheduleAutoPreview();
}

function handleAssetKeydown(event, row) {
  const list = row.querySelector(".asset-suggestion-list");
  const buttons = Array.from(list.querySelectorAll(".asset-suggestion"));
  if (list.hidden || !buttons.length) return;
  const currentIndex = Math.max(0, buttons.findIndex((button) => button.classList.contains("active")));
  if (event.key === "ArrowDown" || event.key === "ArrowUp") {
    event.preventDefault();
    const nextIndex = event.key === "ArrowDown"
      ? Math.min(buttons.length - 1, currentIndex + 1)
      : Math.max(0, currentIndex - 1);
    buttons.forEach((button, index) => button.classList.toggle("active", index === nextIndex));
  }
  if (event.key === "Enter") {
    event.preventDefault();
    selectAssetOption(row, buttons[currentIndex].dataset.ticker);
  }
  if (event.key === "Escape") {
    hideAssetSuggestions(row);
  }
}

function addPortfolioRow(values = {}) {
  const row = document.createElement("div");
  row.className = "portfolio-input-row";
  row.innerHTML = `
    <label class="asset-field">
      <span>자산명 또는 ticker</span>
      <div class="asset-combobox">
        <input class="text-input portfolio-asset" value="${escapeHtml(values.asset || "")}" placeholder="삼성전자, Tesla, 금 ETF" autocomplete="off" role="combobox" aria-expanded="false" />
        <div class="asset-suggestion-list" role="listbox" hidden></div>
      </div>
    </label>
    <label>
      <span>보유 수량</span>
      <input class="text-input portfolio-quantity" inputmode="decimal" value="${escapeHtml(values.quantity || "")}" placeholder="예: 12" />
    </label>
    <label>
      <span>평가액(KRW)</span>
      <input class="text-input portfolio-amount" inputmode="decimal" value="${escapeHtml(values.amountKrw || "")}" placeholder="예: 1000000" />
    </label>
    <div class="market-price-cell" aria-live="polite">
      <span>계산된 평가액</span>
      <strong class="row-market-price">자산과 수량 또는 평가액 입력 후 표시</strong>
      <small class="row-market-meta"></small>
    </div>
    <button class="ghost-button compact-button remove-row-button" type="button">삭제</button>
  `;
  const assetInput = row.querySelector(".portfolio-asset");
  const quantityInput = row.querySelector(".portfolio-quantity");
  const amountInput = row.querySelector(".portfolio-amount");
  assetInput.addEventListener("input", () => {
    assetInput.dataset.ticker = "";
    renderAssetSuggestions(row);
    scheduleAutoPreview();
  });
  assetInput.addEventListener("focus", () => renderAssetSuggestions(row));
  assetInput.addEventListener("keydown", (event) => handleAssetKeydown(event, row));
  quantityInput.addEventListener("input", () => {
    scheduleAutoPreview();
  });
  amountInput.addEventListener("input", () => {
    scheduleAutoPreview();
  });
  row.querySelector(".remove-row-button").addEventListener("click", () => {
    row.remove();
    portfolioPreview = null;
    dom.runAnalysisButton.disabled = true;
    scheduleAutoPreview();
  });
  dom.portfolioRows.appendChild(row);
}

function loadSamplePortfolio() {
  dom.portfolioRows.innerHTML = "";
  [
    { asset: "005930.KS", quantity: "2" },
    { asset: "Apple", quantity: "2" },
    { asset: "Tesla", quantity: "1" },
    { asset: "GLD", quantity: "2" },
  ].forEach(addPortfolioRow);
  scheduleAutoPreview();
}

function collectPortfolioRows() {
  return Array.from(dom.portfolioRows.querySelectorAll(".portfolio-input-row")).map((row) => ({
    asset: row.querySelector(".portfolio-asset").dataset.ticker || row.querySelector(".portfolio-asset").value.trim(),
    quantity: row.querySelector(".portfolio-quantity").value.trim(),
    amountKrw: row.querySelector(".portfolio-amount").value.trim(),
  })).filter((row) => row.asset || row.quantity || row.amountKrw);
}

async function loadDataFreshness() {
  try {
    const freshness = await fetchJson("/api/data-freshness");
    renderFreshness(freshness);
  } catch (error) {
    dom.freshnessPanel.innerHTML = `<div class="empty-state"><strong>데이터 상태 확인 실패</strong><p>${escapeHtml(error.message)}</p></div>`;
  }
}

function renderFreshness(freshness) {
  const ok = freshness.status === "current";
  const reasons = freshness.reasons || [];
  const scenarioText = freshness.scenarioDataVersion
    ? ` · 시나리오 data_version ${escapeHtml(freshness.scenarioDataVersion)}`
    : "";
  const asOfText = freshness.scenarioVectorAsOfDate ? ` · 시장 공통 기준 ${escapeHtml(freshness.scenarioVectorAsOfDate)}` : "";
  dom.freshnessPanel.innerHTML = `
    <div class="freshness-card ${ok ? "ok" : "warning"}">
      <strong>${ok ? "가격·시나리오 데이터 최신" : "갱신 확인 필요"}</strong>
      <p>가격 data_version ${escapeHtml(freshness.dataVersion || "-")}${scenarioText}${asOfText} · manifest ${escapeHtml(freshness.freshnessStatus || "UNKNOWN")}</p>
      ${reasons.length ? `<ul>${reasons.slice(0, 4).map((reason) => `<li>${escapeHtml(reason)}</li>`).join("")}</ul>` : "<p>가격과 시나리오 기준일이 맞아 heavy refresh를 건너뛸 수 있습니다.</p>"}
    </div>
  `;
}

function scheduleAutoPreview() {
  clearTimeout(autoPreviewTimer);
  previewRequestId += 1;
  portfolioPreview = null;
  const rows = collectPortfolioRows();
  if (!rows.length) {
    dom.runAnalysisButton.disabled = true;
    dom.runAnalysisButton.textContent = "포트폴리오 헷지 분석 실행";
    updateRowPriceDisplays([]);
    dom.previewPanel.innerHTML = emptyState("자산명과 보유 수량을 입력하면 가격과 평가액이 자동 계산됩니다.");
    return;
  }
  dom.runAnalysisButton.disabled = true;
  setRowPriceLoading();
  autoPreviewTimer = setTimeout(previewPortfolio, 400);
}

async function previewPortfolio() {
  const requestId = ++previewRequestId;
  const rows = collectPortfolioRows();
  if (!rows.length) return;
  dom.previewPanel.innerHTML = emptyState("가격, 환율, 평가액과 비중을 자동 계산하고 있습니다.");
  try {
    const preview = await postJson("/api/portfolio/preview", { portfolioRows: rows });
    if (requestId !== previewRequestId) return;
    portfolioPreview = preview;
    renderPortfolioPreview(portfolioPreview);
    dom.runAnalysisButton.disabled = !portfolioPreview.canRunAnalysis;
  } catch (error) {
    if (requestId !== previewRequestId) return;
    portfolioPreview = null;
    dom.runAnalysisButton.disabled = true;
    setRowPriceError(error.message);
    dom.previewPanel.innerHTML = `<div class="empty-state error"><strong>포트폴리오 계산 실패</strong><p>${escapeHtml(error.message)}</p></div>`;
  }
}

function previewAnalysisMode(preview) {
  const rows = preview?.rows || [];
  const analysisRows = (preview?.analysisRows || []).filter((row) => row.ticker && row.ticker !== "__CASH__");
  return rows.length === 1 && analysisRows.length === 1 ? "single_asset" : "portfolio";
}

function rowValuationSummary(row) {
  if (row.valuationBasis === "quantity") {
    return `${formatShares(row.quantity)}주 × ${formatKrw(row.unitPriceKrw)} = ${formatKrw(row.marketValueKrw)}`;
  }
  if (row.valuationBasis === "amount") {
    return `평가액 ${formatKrw(row.marketValueKrw)}`;
  }
  if (row.valuationBasis === "cash") {
    return `현금 ${formatKrw(row.marketValueKrw)}`;
  }
  return "-";
}

function renderPortfolioPreview(preview) {
  const rows = preview.rows || [];
  const errors = preview.errors || [];
  const warnings = preview.warnings || [];
  const mode = previewAnalysisMode(preview);
  const modeLabel = mode === "single_asset" ? "단일자산 헷지 기준" : "포트폴리오 기준";
  dom.runAnalysisButton.textContent = mode === "single_asset" ? "단일자산 헷지 분석 실행" : "포트폴리오 분석 실행";
  updateRowPriceDisplays(rows);
  dom.previewPanel.innerHTML = `
    <article class="analysis-card wide">
      <div class="panel-title-row">
        <div>
          <h3>가격/환율 preview</h3>
          <p>총 평가액 ${formatKrw(preview.totalMarketValueKrw)} · ${modeLabel} · 분석 ${preview.canRunAnalysis ? "가능" : "불가"}</p>
        </div>
        <span class="pill">${escapeHtml(preview.dataVersion || "-")}</span>
      </div>
      ${errors.length ? `<div class="alert-list danger">${errors.map((item) => `<p>${escapeHtml(item)}</p>`).join("")}</div>` : ""}
      ${warnings.length ? `<div class="alert-list warning">${warnings.slice(0, 6).map((item) => `<p>${escapeHtml(item)}</p>`).join("")}</div>` : ""}
      <div class="table-wrap">
        <table class="data-table compact-table">
          <thead><tr><th>자산</th><th>입력 기준</th><th>1주 가격</th><th>환율</th><th>계산된 평가액</th><th>비중</th><th>상태</th></tr></thead>
          <tbody>
            ${rows.map((row) => `
              <tr class="${row.errors?.length ? "row-error" : ""}">
                <td><strong>${escapeHtml(row.displayLabel || row.displayName || row.input || "-")}</strong></td>
                <td>${escapeHtml(rowValuationSummary(row))}</td>
                <td>${formatPrice(row.latestPrice, row.currency)}<br><small>${escapeHtml(row.priceAsOf || "-")} · ${escapeHtml(row.dataMode || "-")}</small></td>
                <td>${row.currency === "KRW" ? "불필요" : formatNumber(row.fxRate)}<br><small>${escapeHtml(row.fxAsOf || "")}</small></td>
                <td>${formatKrw(row.marketValueKrw)}</td>
                <td>${formatPct(row.weightPct)}</td>
                <td>${row.errors?.length ? escapeHtml(row.errors.join("; ")) : "OK"}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      </div>
    </article>
  `;
}

function updateRowPriceDisplays(rows) {
  const inputRows = Array.from(dom.portfolioRows.querySelectorAll(".portfolio-input-row"));
  inputRows.forEach((row, index) => {
    const price = row.querySelector(".row-market-price");
    const meta = row.querySelector(".row-market-meta");
    const data = rows.find((item) => item.rowIndex === index);
    if (!data) {
      price.textContent = "자산과 수량 또는 평가액 입력 후 표시";
      meta.textContent = "";
      row.classList.remove("row-error");
      return;
    }
    if (Number.isFinite(Number(data.marketValueKrw))) {
      price.textContent = formatKrw(data.marketValueKrw);
      const source = data.dataMode === "cache" ? "로컬 캐시" : data.dataMode || "-";
      const quantityBasis = data.valuationBasis === "amount"
        ? "KRW 평가액 입력"
        : Number.isFinite(Number(data.quantity)) && Number.isFinite(Number(data.unitPriceKrw))
        ? `${formatShares(data.quantity)}주 × ${formatKrw(data.unitPriceKrw)} / 1주`
        : "";
      meta.textContent = [
        quantityBasis,
        data.displayLabel || data.displayName || data.resolvedTicker || "",
        data.priceAsOf || "-",
        source,
      ].filter(Boolean).join(" · ");
      row.classList.toggle("row-error", Boolean(data.errors?.length));
      return;
    }
    price.textContent = data.errors?.length ? "총 가격 확인 필요" : "총 가격 없음";
    meta.textContent = data.errors?.join("; ") || data.warnings?.join("; ") || "";
    row.classList.toggle("row-error", Boolean(data.errors?.length));
  });
}

function setRowPriceLoading() {
  Array.from(dom.portfolioRows.querySelectorAll(".portfolio-input-row")).forEach((row) => {
    const price = row.querySelector(".row-market-price");
    const meta = row.querySelector(".row-market-meta");
    const hasInput = Boolean(row.querySelector(".portfolio-asset").value.trim() || row.querySelector(".portfolio-quantity").value.trim() || row.querySelector(".portfolio-amount").value.trim());
    if (!hasInput) {
      price.textContent = "자산과 수량 또는 평가액 입력 후 표시";
      meta.textContent = "";
      row.classList.remove("row-error");
      return;
    }
    price.textContent = "총 가격 계산 중...";
    meta.textContent = "";
    row.classList.remove("row-error");
  });
}

function setRowPriceError(message) {
  Array.from(dom.portfolioRows.querySelectorAll(".portfolio-input-row")).forEach((row) => {
    const price = row.querySelector(".row-market-price");
    const meta = row.querySelector(".row-market-meta");
    const hasInput = Boolean(row.querySelector(".portfolio-asset").value.trim() || row.querySelector(".portfolio-quantity").value.trim() || row.querySelector(".portfolio-amount").value.trim());
    if (!hasInput) return;
    price.textContent = "총 가격 확인 실패";
    meta.textContent = message || "";
    row.classList.add("row-error");
  });
}

async function refreshMarketData() {
  setWorkflowBusy(true, "갱신 요청 중");
  try {
    const payload = { force: false };
    const rows = collectPortfolioRows();
    if (rows.length) {
      if (!portfolioPreview?.canRunAnalysis) {
        await previewPortfolio();
      }
      if (portfolioPreview?.canRunAnalysis) {
        payload.portfolioRows = rows;
        payload.hedgeBudgetKrw = dom.hedgeBudgetInput.value.trim();
      }
    }
    const job = await postJson("/api/refresh-market-data", payload);
    renderJobStatus(job);
    if (job.status === "skipped_latest") {
      await loadDataFreshness();
    } else {
      pollJob(job.jobId);
    }
  } catch (error) {
    dom.jobStatusPanel.innerHTML = `<div class="empty-state error"><strong>시장데이터 갱신 실패</strong><p>${escapeHtml(error.message)}</p></div>`;
  } finally {
    setWorkflowBusy(false);
  }
}

async function runPortfolioAnalysis() {
  if (!portfolioPreview?.canRunAnalysis) {
    await previewPortfolio();
    if (!portfolioPreview?.canRunAnalysis) return;
  }
  const mode = previewAnalysisMode(portfolioPreview);
  const analysisRows = (portfolioPreview.analysisRows || []).filter((row) => row.ticker && row.ticker !== "__CASH__");
  const requestPayload = mode === "single_asset"
    ? {
        mode: "single_asset",
        singleAsset: analysisRows[0].ticker,
        baseAmountKrw: portfolioPreview.totalMarketValueKrw,
        hedgeBudgetKrw: dom.hedgeBudgetInput.value.trim(),
        maxComboSize: 3,
      }
    : {
        mode: "portfolio",
        portfolioRows: collectPortfolioRows(),
        hedgeBudgetKrw: dom.hedgeBudgetInput.value.trim(),
        maxComboSize: 3,
      };
  setWorkflowBusy(true, "분석 실행 중");
  try {
    const job = await postJson("/api/run", requestPayload);
    renderJobStatus(job);
    pollJob(job.jobId);
  } catch (error) {
    dom.jobStatusPanel.innerHTML = `<div class="empty-state error"><strong>분석 실행 실패</strong><p>${escapeHtml(error.message)}</p></div>`;
  } finally {
    setWorkflowBusy(false);
  }
}

function pollJob(jobId) {
  if (!jobId) return;
  clearInterval(jobPollTimer);
  jobPollTimer = setInterval(async () => {
    try {
      const job = await fetchJson(`/api/run-status?job_id=${encodeURIComponent(jobId)}`);
      renderJobStatus(job);
      if (["completed", "failed", "skipped_latest"].includes(job.status)) {
        clearInterval(jobPollTimer);
        await loadDataFreshness();
        await loadDashboard();
      }
    } catch (error) {
      clearInterval(jobPollTimer);
      dom.jobStatusPanel.innerHTML = `<div class="empty-state error"><strong>job 상태 확인 실패</strong><p>${escapeHtml(error.message)}</p></div>`;
    }
  }, 1800);
}

function renderJobStatus(job) {
  const status = job.status || "unknown";
  const stage = job.stage || status;
  const title = JOB_STATUS_LABELS[status] || status;
  const stageLabel = JOB_STAGE_LABELS[stage] || stage;
  const message = jobStatusMessage(job, stageLabel);
  dom.jobStatusPanel.innerHTML = `
    <div class="job-status ${status}">
      <strong>${escapeHtml(title)}</strong>
      <p>${escapeHtml(message)}</p>
    </div>
  `;
}

function portfolioContextStatusMessage(job) {
  const context = job.result?.portfolioContext;
  if (!context) return "";
  if (context.applied) {
    const total = Number.isFinite(Number(context.totalMarketValueKrw)) ? `총 ${formatKrw(context.totalMarketValueKrw)}` : "총액 기록";
    const budget = Number.isFinite(Number(context.hedgeBudgetKrw)) ? `헷지 예산 ${formatKrw(context.hedgeBudgetKrw)}` : "퍼센트 예산";
    return ` 포트폴리오 금액 컨텍스트 적용: ${total}, ${budget}.`;
  }
  if (context.requested) {
    return ` 포트폴리오 금액 컨텍스트 생략: ${context.reason || "분석 기준에 맞지 않습니다"}.`;
  }
  return "";
}

function jobStatusMessage(job, stageLabel) {
  if (job.error) return job.error;
  if (job.status === "completed") {
    if (job.jobType === "market_data_refresh") {
      return `시장데이터와 활성 번들 갱신이 완료됐습니다.${portfolioContextStatusMessage(job)}`;
    }
    const runId = job.result?.runId || job.runId || "-";
    const backtestRunId = job.result?.backtestRunId;
    if (job.result?.productBundleUpdated) {
      return `대시보드가 ${runId}${backtestRunId ? ` / ${backtestRunId}` : ""} 결과로 갱신됐습니다.`;
    }
    return `계산 결과 ${runId} 생성 완료. 대시보드 공식 묶음은 변경되지 않았습니다.`;
  }
  if (job.status === "skipped_latest") {
    return job.result?.reason || "이미 최신 데이터라 heavy refresh를 건너뛰었습니다.";
  }
  const runId = job.result?.runId || job.runId;
  return `${stageLabel}${runId ? ` · ${runId}` : ""}`;
}

function setWorkflowBusy(isBusy, label = "") {
  dom.refreshMarketButton.disabled = isBusy;
  dom.addPortfolioRowButton.disabled = isBusy;
  dom.runAnalysisButton.disabled = isBusy || !portfolioPreview?.canRunAnalysis;
  if (isBusy && label) {
    dom.jobStatusPanel.innerHTML = `<div class="job-status running"><strong>${escapeHtml(label)}</strong><p>잠시 기다려 주세요.</p></div>`;
  }
}

async function loadDashboard() {
  setBusy(true);
  try {
    payload = await fetchJson("/api/product-dashboard");
    await loadScenarioSensitivities();
    renderDashboard();
  } catch (error) {
    renderError(error);
  } finally {
    setBusy(false);
  }
}

function renderLoading() {
  dom.banner.innerHTML = bannerHtml("loading", "active bundle을 확인하고 있습니다.");
  dom.summaryCards.innerHTML = Array.from({ length: 4 }, (_, index) => `
    <article class="status-card loading">
      <span class="status-label">요약 ${index + 1}</span>
      <strong>불러오는 중</strong>
      <p>산출물을 읽고 있습니다.</p>
    </article>
  `).join("");
  if (dom.vulnerabilityTop3Container) dom.vulnerabilityTop3Container.innerHTML = emptyState("시나리오 취약성을 계산하는 중입니다...");
  if (dom.contributorsContainer) dom.contributorsContainer.innerHTML = emptyState("보유자산별 기여도를 분석하는 중입니다...");
  if (dom.actionsContainer) dom.actionsContainer.innerHTML = emptyState("헷징 및 포지션 조절 액션을 산출하는 중입니다...");
  dom.trustGrid.innerHTML = emptyState("검증 상태를 불러오는 중입니다.");
  renderTerms();
}

function renderDashboard() {
  const manifest = payload.manifest || {};
  const bundle = payload.activeBundle || {};
  const hedge = payload.hedge || {};
  const scenario = payload.scenario || {};
  const formalDecision = payload.recommendationDecision || {};
  const actionDecision = payload.actionPlanDecision || {};
  const activeScenarios = activeScenarioLabels(scenario);
  const activeCodes = activeScenarioCodes(scenario);
  const best = pickBestAction();

  renderBanner(manifest, bundle);
  renderConclusion(best, activeScenarios, hedge, scenario, actionDecision);
  renderBundleMeta(bundle, manifest);
  renderSummaryCards(best, activeScenarios, hedge, scenario, actionDecision);

  // New Portfolio Vulnerability Analyzer views
  renderVulnerabilityAnalysis();
  renderVulnerabilityContributors();
  renderActionRecommendations(actionDecision);

  renderTrust(manifest, hedge, scenario, payload.backtest || {}, payload.eventOverlayStatus || {}, actionDecision, formalDecision);
  renderTerms();
  renderExpert(manifest, hedge, scenario, payload.backtest || {});
}

function renderBanner(manifest, bundle) {
  const dataFreshness = payload.dataFreshness || {};
  if (dataFreshness.status === "stale") {
    const reasonText = (dataFreshness.reasons || []).slice(0, 2).join(" · ") || "가격/시나리오 기준일을 다시 확인해야 합니다.";
    dom.banner.innerHTML = bannerHtml("warning", `갱신 확인 필요: ${reasonText}`);
    return;
  }
  const status = payload.freshnessStatus || manifest.freshness_status || bundle.freshness_status || "UNKNOWN";
  const reasons = payload.staleReasons || manifest.stale_reasons || [];
  if (status === "FRESH") {
    dom.banner.innerHTML = bannerHtml("ok", "현재 선택된 공식 실행 묶음 기준으로 시장국면, 추천, backtest 산출물이 연결되어 있습니다.");
    return;
  }
  const reasonText = reasons.length ? reasons.join(" · ") : "공식 실행 묶음 상태를 확인해야 합니다.";
  dom.banner.innerHTML = bannerHtml("warning", `${status}: ${reasonText}`);
}

function renderConclusionLegacy(best, activeScenarios, hedge, scenario, decision = {}) {
  const rows = allCandidateRows(hedge);
  const statusCounts = countStatuses(rows);
  const coverage = payload.backtest?.coverageSummary || {};
  const cashLagRows = Number(coverage.cashLagRows || 0);
  const evaluatedCases = Number(coverage.evaluatedCaseCount || 0);
  const subject = analysisSubjectText(hedge);
  if (decision.canExecuteRecommendations === false) {
    const reasonText = (decision.primaryReasons || []).slice(0, 3).join(" ");
    dom.conclusionTitle.textContent = decision.title || "현재 실행 추천 가능한 후보는 없습니다.";
    dom.conclusionCopy.textContent = `${subject} 기준입니다. ${decision.copy || "검증 조건이 부족해 추천을 보류합니다."}${reasonText ? ` ${reasonText}` : ""}`;
    return;
  }
  if (!statusCounts.PASS_RECOMMEND) {
    const riskText = activeScenarios.length ? activeScenarios.slice(0, 2).join("과 ") : "주요 adverse 시나리오";
    dom.conclusionTitle.textContent = "현재 검증 기준에서 정식 추천 가능한 후보는 없습니다.";
    if ((statusCounts.FAIL_GATE || 0) > 0 && !(statusCounts.REFERENCE_ONLY || 0)) {
      dom.conclusionCopy.textContent = `${subject}은 ${riskText}에 취약하지만, 표시 후보 전부가 과거 검증에서 위험 악화 또는 게이트 미통과로 분류되어 헷지 추천으로 제시하지 않습니다.`;
    } else {
      const cashText = cashLagRows > 0 ? ` 특히 ${cashLagRows}개 검증행에서 같은 금액을 현금으로 남기는 것보다 약했습니다.` : "";
      const caseText = evaluatedCases > 0 ? ` 직접 평가된 stress case는 ${evaluatedCases}개입니다.` : "";
      dom.conclusionCopy.textContent = `${subject}은 ${riskText}에 취약합니다. 참고용 후보는 있으나, backtest evidence가 부족하거나 현금화 기준 대비 헷지 초과효과가 부족해 정식 추천으로 분류하지 않았습니다.${cashText}${caseText} 아래 카드는 실행 추천이 아니라 후보 감사 목록입니다.`;
    }
    return;
  }
  const candidate = candidateName(best);
  const statusLabel = STATUS_LABELS[best?.recommendation_status] || best?.recommendation_status || "판정 대기";
  const cvar = formatPct(best?.cvar_improve_pct);
  const mdd = formatPct(best?.mdd_improve_pct);
  const riskText = activeScenarios.length ? activeScenarios.slice(0, 2).join("과 ") : "주요 adverse 시나리오";
  dom.conclusionTitle.textContent = `${subject}은 ${riskText}에 취약합니다.`;
  dom.conclusionCopy.textContent = `${candidate}는 CVaR · 나쁜 날 평균손실을 ${cvar}, MDD · 최대 낙폭을 ${mdd} 줄였고 과거 검증 기준상 ${statusLabel}로 분류됩니다.`;
}

function renderBundleMeta(bundle, manifest) {
  const items = [
    ["시장국면 실행", bundle.scenario_run || manifest.active_scenario_run],
    ["헷지 추천 실행", bundle.hedgemate_run || manifest.active_hedgemate_run],
    ["과거검증 실행", bundle.backtest_run || manifest.active_backtest_run],
    ["갱신 실행일", bundle.data_version || manifest.data_version],
    ["시장 공통 기준일", bundle.scenario_vector_as_of_date || manifest.scenario_vector_as_of_date],
    ["묶음 생성 시각", bundle.generated_at_utc || manifest.generated_at_utc],
    ["상태", bundle.freshness_status || manifest.freshness_status],
  ];
  dom.bundleMeta.innerHTML = items.map(([label, value]) => `
    <div>
      <dt>${escapeHtml(label)}</dt>
      <dd>${escapeHtml(value || "-")}</dd>
    </div>
  `).join("");
}

function renderSummaryCardsLegacy(best, activeScenarios, hedge, scenario, decision = {}) {
  const dq = hedge.dqSummary || {};
  const backtest = payload.backtest || {};
  const coverage = backtest.coverageSummary || {};
  const statusCounts = decision.statusCounts || countStatuses([...(hedge.portfolioOneToOne || []), ...(hedge.portfolioMulti || [])]);
  const cashLagText = coverage.cashLagRows ? ` · 현금화 미달 ${coverage.cashLagRows}건` : "";
  const decisionValue = decision.canExecuteRecommendations === false
    ? "실행 추천 불가"
    : `${statusCounts.PASS_RECOMMEND || 0}개 정식 추천`;
  const decisionCopy = decision.canExecuteRecommendations === false
    ? `${statusCounts.REFERENCE_ONLY || 0}개 참고 · ${statusCounts.FAIL_GATE || 0}개 미통과 · 후보는 감사 목록입니다.`
    : `${statusCounts.REFERENCE_ONLY || 0}개 참고 · ${statusCounts.FAIL_GATE || 0}개 기준 미통과${cashLagText}`;
  const portfolioRiskText = activeScenarios.length
    ? `${activeScenarios.slice(0, 3).join(", ")} 기준 취약도를 확인해야 합니다.`
    : "활성 adverse scenario 기준 취약도를 확인해야 합니다.";
  dom.summaryCards.innerHTML = [
    summaryCard("현재 시장국면", activeScenarios.slice(0, 3).join(", ") || "활성 시나리오 없음", `${scenario.dataAsOfDate || "-"} 시장 공통 기준 · 실행일 ${payload.activeBundle?.data_version || "-"}`),
    summaryCard("분석 기준/주요 위험", analysisBasisText(hedge), `${portfolioRiskText} · 취약도 변화 ${formatSigned(best?.scenario_vulnerability_delta)}`),
    summaryCard("추천 판정", decisionValue, decisionCopy),
    summaryCard("데이터/검증 상태", `DQ PASS ${dq.pass || 0} · WARN ${dq.warn || 0} · FAIL ${dq.fail || 0}`, backtestCoverageDetail(coverage, backtest)),
  ].join("");
}

function analysisSubjectText(hedge) {
  if (hedge?.singleAssetTicker) {
    return `${assetDisplayLabel(hedge.singleAssetTicker)} 100% 단일자산 기준`;
  }
  return "현재 포트폴리오";
}

function analysisBasisText(hedge) {
  if (hedge?.singleAssetTicker) {
    return `단일자산: ${assetDisplayLabel(hedge.singleAssetTicker)} 100%`;
  }
  return "입력 포트폴리오 기준";
}

function backtestCoverageDetail(coverage, backtest) {
  if (!coverage || !coverage.rowCount) {
    return "Backtest 결과 없음 · 정식 추천 불가";
  }
  const quality = BACKTEST_QUALITY_LABELS[coverage.qualityLevel] || coverage.qualityLevel || "검증 강도 미정";
  const avgDays = coverage.evaluationDays?.avg;
  const dayText = Number.isFinite(Number(avgDays)) ? `평균 ${Number(avgDays).toFixed(0)}거래일` : "평가일 미정";
  const priceGapText = coverage.priceGapCaseCount ? ` · 가격범위밖 ${coverage.priceGapCaseCount}개` : "";
  const noCommonPriceText = coverage.noCommonPriceCaseCount ? ` · 공통가격없음 ${coverage.noCommonPriceCaseCount}개` : "";
  const preInceptionText = coverage.priceCoverageBlockerType === "PRE_INCEPTION_ONLY" ? " · 상장전 이력 한계" : "";
  const cashLagText = coverage.cashLagRows ? ` · 현금화 대비 미달 ${coverage.cashLagRows}건` : "";
  const costBps = Number(coverage.transactionCostBps?.avg || 0) + Number(coverage.slippageBps?.avg || 0);
  const costText = costBps > 0 ? ` · 비용 ${costBps.toFixed(0)}bp 반영` : "";
  const bootstrapRows = Number(coverage.targetBootstrapRows || 0);
  const robustBootstrapRows = Number(coverage.targetBootstrapRobustRows || 0);
  const weakBootstrapRows = Number(coverage.targetBootstrapUncertainRows || 0) + Number(coverage.targetBootstrapWorseRows || 0);
  const bootstrapText = bootstrapRows
    ? ` · bootstrap 강건 ${robustBootstrapRows}/${bootstrapRows}${weakBootstrapRows ? ` · 약함 ${weakBootstrapRows}건` : ""}`
    : "";
  return `${quality} · stress case ${coverage.evaluatedCaseCount || 0}개 · ${dayText}${priceGapText}${noCommonPriceText}${preInceptionText}${cashLagText}${costText}${bootstrapText} · ${backtest.verdictCounts?.WORSENED || 0} 악화`;
}

function renderRecommendations(hedge, activeCodes = new Set(), decision = {}) { { /* deprecated */ }
  if (auditMode) {
    const groups = ["PASS_RECOMMEND", "REFERENCE_ONLY", "FAIL_GATE", "INSUFFICIENT_DATA"]
      .map((status) => {
        const groupRows = selectDiverseRows(
          allRows.filter((row) => row.recommendation_status === status),
          status === "REFERENCE_ONLY" ? 9 : 6,
        );
        if (!groupRows.length) return "";
        return `
          <section class="recommendation-group audit-group">
            <h3>${escapeHtml(auditGroupTitle(status))}</h3>
            <div class="recommendation-list">
              ${groupRows.map((row) => recommendationCard(row, { executionBlocked: true })).join("")}
            </div>
          </section>
        `;
      })
      .filter(Boolean)
      .join("");
    dom.recommendationBoard.innerHTML = `
      <section class="recommendation-group no-recommendation-audit">
        ${decisionAuditPanel(decision)}
      </section>
      ${groups}
    `;
    return;
  }
  const viableRows = allRows.filter((row) => ["PASS_RECOMMEND", "REFERENCE_ONLY"].includes(row.recommendation_status));
  if (!viableRows.length) {
    const failedRows = allRows.filter((row) => row.recommendation_status === "FAIL_GATE");
    dom.recommendationBoard.innerHTML = `
      <section class="recommendation-group no-recommendation-audit">
        <h3>현재 추천 없음</h3>
        <div class="failure-audit">
          <strong>표시 후보 ${failedRows.length}개가 모두 추천 게이트를 통과하지 못했습니다.</strong>
          <p>추천처럼 보이지 않도록 실패 후보는 탈락 근거 확인용으로만 제공합니다.</p>
          ${failureReasonSummary(failedRows)}
        </div>
        <details class="failed-candidate-details">
          <summary>상위 탈락 후보와 근거 보기</summary>
          <div class="recommendation-list">
            ${selectDiverseRows(failedRows, 8).map(recommendationCard).join("")}
          </div>
        </details>
      </section>
    `;
    return;
  }
  const groups = ["PASS_RECOMMEND", "REFERENCE_ONLY", "FAIL_GATE", "INSUFFICIENT_DATA"];
  dom.recommendationBoard.innerHTML = groups.map((status) => {
    const groupRows = selectDiverseRows(
      allRows.filter((row) => row.recommendation_status === status),
      status === "REFERENCE_ONLY" ? 9 : 6,
    );
    return `
      <section class="recommendation-group">
        <h3>${STATUS_LABELS[status] || status}</h3>
        <div class="recommendation-list">
          ${groupRows.length ? groupRows.map(recommendationCard).join("") : emptyState(groupEmptyText(status))}
        </div>
      </section>
    `;
  }).join("");
}

function cashBaselineAuditPanel(audit = {}) {
  const lagRows = Number(audit.lagCandidateRows || 0);
  if (!lagRows) return "";
  const stressRows = Number(audit.targetLagStressRows || 0);
  const avgStress = audit.avgCashNetStressDelta?.avg;
  const avgStressText = Number.isFinite(Number(avgStress)) ? formatSigned(avgStress) : "-";
  const rows = (audit.topRows || []).slice(0, 4);
  return `
    <div class="cash-baseline-audit">
      <div>
        <strong>현금화 기준 비교</strong>
        <p>${lagRows}개 후보 행, ${stressRows}개 대상 stress 행에서 같은 금액을 현금으로 남긴 기준을 넘지 못했습니다. 평균 stress 초과효과는 ${escapeHtml(avgStressText)}입니다.</p>
      </div>
      ${rows.length ? `
        <ul>
          ${rows.map((row) => `
            <li>
              <span>${escapeHtml(row.candidate_name || row.candidate_ticker || row.candidate_combo || "-")}</span>
              <b>${escapeHtml(formatSigned(row.target_avg_cash_net_stress_delta))}</b>
            </li>
          `).join("")}
        </ul>
      ` : ""}
    </div>
  `;
}

function bootstrapAuditPanel(audit = {}) {
  const blockedRows = Number(audit.notRobustCandidateRows || 0);
  if (!blockedRows) return "";
  const robust = Number(audit.targetBootstrapRobustRows || 0);
  const total = Number(audit.targetBootstrapRows || 0);
  const minP = audit.pImprove?.min;
  const minPText = Number.isFinite(Number(minP)) ? formatNumber(minP) : "-";
  const rows = (audit.topRows || []).slice(0, 4);
  return `
    <div class="bootstrap-audit">
      <div>
        <strong>Bootstrap 강건성</strong>
        <p>${blockedRows}개 후보 행이 bootstrap 강건성 기준을 넘지 못했습니다. 대상 stress robust 개선은 ${robust}/${total}이고, 최저 개선확률은 ${escapeHtml(minPText)}입니다.</p>
      </div>
      ${rows.length ? `
        <ul>
          ${rows.map((row) => `
            <li>
              <span>${escapeHtml(row.candidate_name || row.candidate_ticker || row.candidate_combo || "-")}</span>
              <b>${escapeHtml(`${formatNumber(row.target_bootstrap_min_p_improve)} min p · cash ${formatNumber(row.target_cash_bootstrap_min_p_improve)} p`)}</b>
            </li>
          `).join("")}
        </ul>
      ` : ""}
    </div>
  `;
}

function decisionAuditPanel(decision = {}) {
  const reasons = decision.primaryReasons || [];
  return `
    <div class="decision-audit ${escapeHtml(decision.severity || "warning")}">
      <div>
        <strong>${escapeHtml(decision.sectionTitle || decision.title || "추천 판정 확인 필요")}</strong>
        <p>${escapeHtml(decision.sectionCopy || decision.copy || "후보를 실행 권고로 보기 전에 검증 근거를 확인해야 합니다.")}</p>
      </div>
      ${reasons.length ? `<ul>${reasons.map((reason) => `<li>${escapeHtml(reason)}</li>`).join("")}</ul>` : ""}
      <dl class="decision-kpis">
        <div><dt>정식 추천</dt><dd>${escapeHtml(decision.formalRecommendationCount ?? 0)}개</dd></div>
        <div><dt>참고 후보</dt><dd>${escapeHtml(decision.referenceOnlyCount ?? 0)}개</dd></div>
        <div><dt>기준 미통과</dt><dd>${escapeHtml(decision.failGateCount ?? 0)}개</dd></div>
        <div><dt>현금 대비 미달</dt><dd>${escapeHtml(decision.cashLagRows ?? 0)}건</dd></div>
        <div><dt>평가 stress</dt><dd>${escapeHtml(decision.evaluatedStressCaseCount ?? 0)}개</dd></div>
      </dl>
      ${cashBaselineAuditPanel(decision.cashBaselineAudit)}
      ${bootstrapAuditPanel(decision.bootstrapAudit)}
    </div>
  `;
}

function auditGroupTitle(status) {
  if (status === "PASS_RECOMMEND") return "기준상 정식 후보 · 현재 실행 차단";
  if (status === "REFERENCE_ONLY") return "참고 후보 · 추천 아님";
  if (status === "FAIL_GATE") return "기준 미통과 · 제외";
  if (status === "INSUFFICIENT_DATA") return "데이터 부족 · 제외";
  return STATUS_LABELS[status] || status;
}

function failureReasonSummary(rows) {
  const counts = new Map();
  rows.forEach((row) => {
    const reason = splitPrimaryReason(row.gate_fail_reasons || row.backtest_reason || row.reference_reason || "사유 미기재");
    counts.set(reason, (counts.get(reason) || 0) + 1);
  });
  const items = Array.from(counts.entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5);
  if (!items.length) return "";
  return `
    <ul class="failure-reason-list">
      ${items.map(([reason, count]) => `<li><span>${escapeHtml(reason)}</span><strong>${count}개</strong></li>`).join("")}
    </ul>
  `;
}

function splitPrimaryReason(reason) {
  return String(reason || "사유 미기재").split(";").map((item) => item.trim()).filter(Boolean)[0] || "사유 미기재";
}

function allCandidateRows(hedge) {
  const singleAssetRows = [...(hedge.singleAssetOneToOne || []), ...(hedge.singleAssetMulti || [])]
    .filter((row) => row && (row.candidate_ticker || row.candidate_combo));
  const singleAssetRowsAreGated = singleAssetRows.some((row) => row.backtest_gate_status);
  const rows = hedge.singleAssetTicker && singleAssetRowsAreGated
    ? singleAssetRows
    : [...(hedge.portfolioOneToOne || []), ...(hedge.portfolioMulti || [])];
  return rows
    .filter((row) => row && (row.candidate_ticker || row.candidate_combo));
}

function groupEmptyText(status) {
  if (status === "PASS_RECOMMEND") {
    return "현재 검증 기준에서 정식 추천 가능한 후보는 없습니다.";
  }
  if (status === "REFERENCE_ONLY") {
    return "참고용 후보가 없습니다.";
  }
  if (status === "FAIL_GATE") {
    return "기준 미통과 후보가 없습니다.";
  }
  return "데이터 부족 후보가 없습니다.";
}

function recommendationCard(row, options = {}) {
  const name = candidateName(row);
  const status = row.recommendation_status || "UNKNOWN";
  const statusLabel = options.executionBlocked && status === "PASS_RECOMMEND"
    ? "기준상 추천 · 실행 차단"
    : STATUS_LABELS[status] || status;
  const fit = candidateFit(row);
  return `
    <article class="recommendation-card status-${escapeHtml(status.toLowerCase())}${options.executionBlocked ? " execution-blocked" : ""}">
      <div class="card-topline">
        <div>
          <span class="pill">${escapeHtml(statusLabel)}</span>
          <h4>${escapeHtml(name)}</h4>
        </div>
        <div class="allocation-badge" title="현재 포트폴리오 총 평가액 중 후보 자산으로 옮겨 담는 금액과 비중입니다.">
          <strong>${escapeHtml(hedgeBudgetLabel(row))}</strong>
          <small>${escapeHtml(hedgeBudgetMeaning(row))}</small>
        </div>
      </div>
      <p class="reason">${escapeHtml(scenarioRiskText(row))}</p>
      ${candidateAlertTags(row)}
      <dl class="metric-grid">
        ${metric("CVaR · 나쁜 날 평균손실", formatPct(row.cvar_improve_pct), "손실 큰 날 평균이 얼마나 줄었는지")}
        ${metric("MDD · 최대 낙폭", formatPct(row.mdd_improve_pct), "고점 대비 최대 하락폭이 얼마나 줄었는지")}
        ${metric("Sharpe · 위험 대비 성과", formatPct(row.sharpe_improve_pct), "위험 대비 성과 변화")}
        ${metric("Stress · 위기 구간", formatSigned(row.stress_improve), "위기 구간 평균 성과 변화")}
      </dl>
      <div class="evidence-line">
        <span>${escapeHtml(backtestEvidenceText(row))}</span>
        <span>${escapeHtml(candidateDecisionText(row))}</span>
        <span>시나리오 매핑: ${escapeHtml(fit)}</span>
      </div>
      ${executionPlanHtml(row)}
      ${decisionReasonsHtml(row)}
      ${executionBlockedNote(status, options)}
    </article>
  `;
}

function executionBlockedNote(status, options = {}) {
  if (!options.executionBlocked || status !== "PASS_RECOMMEND") return "";
  return `<p class="execution-note compact blocked">현재 데이터/검증 조건 때문에 기준상 추천 후보도 실행 권고로 표시하지 않습니다.</p>`;
}

function backtestEvidenceText(row) {
  const status = row?.backtest_gate_status || "검증 미완료";
  const targetEvaluated = intField(row, "backtest_target_evaluated_count");
  const targetImproved = intField(row, "backtest_target_improved_count");
  const targetWorsened = intField(row, "backtest_target_worsened_count");
  const targetInsufficient = intField(row, "backtest_target_insufficient_history_count");
  const targetBeatsCash = intField(row, "backtest_target_beats_cash_count");
  const targetLagsCash = intField(row, "backtest_target_lags_cash_count");
  const contextWorsened = intField(row, "backtest_context_worsened_count");
  const suffix = contextWorsened > 0 ? ` · 비대상 스트레스 악화 ${contextWorsened}건` : "";
  const cashUpside = targetBeatsCash > 0 && targetLagsCash <= 0 ? ` · 현금화 대비 우위 ${targetBeatsCash}건` : "";

  if (status === "VALIDATED") {
    const improvedText = targetImproved > 0 ? `${targetEvaluated}건 중 ${targetImproved}건 개선` : `${targetEvaluated}건 비악화`;
    return `Backtest: 대상 stress ${improvedText}${cashUpside}${suffix}`;
  }
  if (status === "PARTIAL_VALIDATION") {
    return `Backtest: 대상 stress 일부 검증 ${targetEvaluated}건 · 검증부족 ${targetInsufficient}건${suffix}`;
  }
  if (status === "VALIDATION_INSUFFICIENT") {
    return `Backtest: 대상 stress 검증 부족${targetInsufficient > 0 ? ` ${targetInsufficient}건` : ""}${suffix}`;
  }
  if (status === "VALIDATION_THIN") {
    return `Backtest: 대상 stress 직접 검증 ${targetEvaluated}건 · 표본 부족${cashUpside}${suffix}`;
  }
  if (status === "REFERENCE_ONLY_CASH_BASELINE") {
    return `Backtest: 같은 금액을 현금으로 남긴 기준보다 약함 ${targetLagsCash}건${suffix}`;
  }
  if (status === "FAIL_BACKTEST") {
    return `Backtest: 대상 stress 악화 ${targetWorsened}건${suffix}`;
  }
  if (status === "VALIDATION_MISSING") {
    return "Backtest: 후보와 일치하는 검증 결과 없음";
  }
  return `Backtest: ${status}${suffix}`;
}

function candidateDecisionText(row) {
  const status = row?.recommendation_status;
  if (status === "PASS_RECOMMEND") {
    return "판정: 백테스트와 게이트를 모두 통과한 정식 후보";
  }
  if (status === "REFERENCE_ONLY") {
    const gateStatus = row?.backtest_gate_status;
    const targetBeatsCash = intField(row, "backtest_target_beats_cash_count");
    const targetLagsCash = intField(row, "backtest_target_lags_cash_count");
    if (gateStatus === "VALIDATION_THIN" && targetBeatsCash > 0 && targetLagsCash <= 0) {
      return "판정: 현금화보다 나았지만 직접 검증 표본이 부족해 참고만";
    }
    if (gateStatus === "REFERENCE_ONLY_CASH_BASELINE") {
      return "판정: 원 포지션보다 위험은 줄 수 있으나 현금 보유보다 약해 참고만";
    }
    return "판정: 위험 완화 근거는 있으나 수익 훼손/검증 한계로 참고만";
  }
  if (status === "FAIL_GATE") {
    return "판정: 현재 기준에서는 추천 금지";
  }
  return "판정: 추가 검증 필요";
}

function candidateAlertTags(row) {
  const tags = [];
  const status = row?.recommendation_status || "";
  const gateStatus = row?.backtest_gate_status || "";
  const targetEvaluated = intField(row, "backtest_target_evaluated_count");
  const targetWorsened = intField(row, "backtest_target_worsened_count");
  const targetInsufficient = intField(row, "backtest_target_insufficient_history_count");
  const targetBeatsCash = intField(row, "backtest_target_beats_cash_count");
  const targetLagsCash = intField(row, "backtest_target_lags_cash_count");

  if (status !== "PASS_RECOMMEND") {
    tags.push({ tone: "warn", text: "정식 추천 아님" });
  }
  if (targetWorsened > 0 || status === "FAIL_GATE") {
    tags.push({ tone: "danger", text: targetWorsened > 0 ? `대상 stress 악화 ${targetWorsened}건` : "게이트 미통과" });
  }
  if (targetLagsCash > 0) {
    tags.push({ tone: "danger", text: `현금 보유보다 약함 ${targetLagsCash}건` });
  } else if (targetBeatsCash > 0) {
    tags.push({ tone: "ok", text: `현금 보유보다 우위 ${targetBeatsCash}건` });
  }
  if (gateStatus === "VALIDATION_THIN") {
    tags.push({ tone: "warn", text: `직접 검증 ${targetEvaluated}건뿐` });
  }
  if (gateStatus === "VALIDATION_INSUFFICIENT" || targetInsufficient > 0) {
    tags.push({ tone: "warn", text: "대상 검증 데이터 부족" });
  }
  if (!tags.length) {
    tags.push({ tone: "ok", text: "백테스트 게이트 통과" });
  }
  return `<div class="candidate-alerts">${tags.slice(0, 4).map((tag) => `<span class="candidate-alert ${escapeHtml(tag.tone)}">${escapeHtml(tag.text)}</span>`).join("")}</div>`;
}

function decisionReasonsHtml(row) {
  const reasons = decisionReasons(row);
  if (!reasons.length) {
    return `<p class="caution">판정 사유: 추가 주의 사유 없음</p>`;
  }
  return `
    <div class="decision-reasons">
      <strong>판정 사유</strong>
      <ul>
        ${reasons.map((reason) => `<li>${escapeHtml(reason)}</li>`).join("")}
      </ul>
    </div>
  `;
}

function decisionReasons(row) {
  const rawReasons = [
    row?.gate_fail_reasons,
    row?.reference_reason,
    row?.backtest_reason,
    row?.dq_warning_reasons,
  ];
  const seen = new Set();
  const reasons = [];
  rawReasons
    .flatMap(splitReasonParts)
    .map(localizeReason)
    .filter(Boolean)
    .forEach((reason) => {
      if (seen.has(reason)) return;
      seen.add(reason);
      reasons.push(reason);
    });
  if (reasons.some((reason) => reason.includes("과거 검증 데이터 부족"))) {
    return reasons.filter((reason) => reason !== "검증 부족").slice(0, 5);
  }
  return reasons.slice(0, 5);
}

function splitReasonParts(value) {
  return String(value || "")
    .split(";")
    .map((item) => item.trim())
    .filter(Boolean);
}

function localizeReason(reason) {
  const text = String(reason || "").trim();
  const nonTarget = text.match(/non-target scenarios worsened (\d+) times/i);
  if (nonTarget) return `비대상 스트레스 구간 ${nonTarget[1]}건에서 악화`;
  if (/annual return drag soft warning/i.test(text)) return "연환산 수익률 훼손 경고";
  if (/Sharpe soft warning/i.test(text)) return "위험 대비 성과 개선폭이 약함";
  if (/target-scenario historical validation has insufficient history/i.test(text)) return "대상 시나리오 과거 검증 데이터 부족";
  if (/target-scenario backtest has only/i.test(text)) return "대상 stress 직접 검증 표본 부족";
  if (/cash-only de-risking/i.test(text)) return "현금화 기준 대비 헷지 초과효과 부족";
  if (/target-scenario walk-forward backtest has evaluated non-worsened evidence/i.test(text)) return "대상 시나리오 백테스트에서는 비악화";
  if (/target-scenario backtest worsened risk metrics/i.test(text)) return "대상 시나리오 백테스트에서 위험지표 악화";
  if (/missing for candidate/i.test(text)) return "후보와 일치하는 백테스트 결과 없음";
  if (/검증 부족/.test(text)) return "검증 부족";
  if (/정식 추천 불가/.test(text)) return "정식 추천 불가";
  return text;
}

function intField(row, key) {
  const value = Number(row?.[key]);
  return Number.isFinite(value) ? value : 0;
}

function executionPlanHtml(row) {
  const plan = row.executionPlan || [];
  if (!plan.length) {
    return `<p class="execution-note">${escapeHtml(row.executionNote || "실제 매수 수량은 KRW 포트폴리오 금액 입력 후 계산됩니다.")}</p>`;
  }
  const note = row.executionNote ? `<p class="execution-note compact">${escapeHtml(row.executionNote)}</p>` : "";
  return `
    <div class="execution-plan">
      ${plan.slice(0, 3).map((item) => `
        <div>
          <strong>${escapeHtml(item.displayName || item.ticker)}</strong>
          <span>배정 ${formatKrw(item.targetAmountKrw)} · 현재가 ${escapeHtml(marketPriceText(item))}</span>
          <span>매수 가능 ${formatShares(item.wholeShareQuantity)}주 · 예상 사용 ${formatKrw(item.estimatedUsedKrw)} · 잔액 ${formatKrw(item.estimatedCashLeftKrw)}</span>
        </div>
      `).join("")}
    </div>
    ${note}
  `;
}

function marketPriceText(item) {
  const latest = Number(item.latestPrice);
  if (!Number.isFinite(latest)) return "-";
  const currency = item.currency || "";
  const localPrice = Number(item.fxRate) * latest;
  if (currency === "KRW" || !Number.isFinite(localPrice)) {
    return formatPrice(latest, currency || "KRW");
  }
  return `${formatPrice(latest, currency)} / 약 ${formatKrw(localPrice)}`;
}

function selectDiverseRows(rows, limit) {
  const selected = [];
  const used = new Set();
  const byBucket = new Map();
  rows.forEach((row) => {
    const bucket = row.candidate_bucket || row.candidate_bucket_combo || "unknown";
    if (!byBucket.has(bucket)) byBucket.set(bucket, []);
    byBucket.get(bucket).push(row);
  });
  Array.from(byBucket.values()).forEach((bucketRows) => {
    const best = bucketRows[0];
    if (best) {
      selected.push(best);
      used.add(candidateName(best));
    }
  });
  rows.forEach((row) => {
    if (selected.length >= limit) return;
    const name = candidateName(row);
    if (!used.has(name)) {
      selected.push(row);
      used.add(name);
    }
  });
  return selected.slice(0, limit);
}

function candidateFit(row) {
  const raw = row.active_adverse_scenarios || row.risk_bucket_match || "";
  if (!raw || raw === "core_hedge") {
    return `${row.candidate_bucket || row.candidate_bucket_combo || "기본 방어자산"} · 핵심 헷지 후보`;
  }
  return raw
    .split("|")
    .filter(Boolean)
    .map((code) => SCENARIO_LABELS[code] || code)
    .join(", ");
}

function hedgeBudgetLabel(row) {
  const budgetKrw = Number(row.hedge_budget_krw);
  const investedKrw = Number(row.hedge_invested_krw);
  if (Number.isFinite(budgetKrw) && budgetKrw > 0) {
    if (Number.isFinite(investedKrw) && investedKrw > 0) {
      return `투입 예정 ${formatKrw(investedKrw)}`;
    }
    return `배정 예산 ${formatKrw(budgetKrw)}`;
  }
  const pct = row.hedge_weight_pct || row.hedge_budget_pct;
  return `재배분 비중 ${formatPct(pct)}`;
}

function hedgeBudgetMeaning(row) {
  const pct = row.hedge_weight_pct || row.hedge_budget_pct;
  const budgetKrw = Number(row.hedge_budget_krw);
  const cashLeft = Number(row.hedge_cash_left_krw);
  const parts = [];
  if (pct) parts.push(`총 평가액 대비 ${formatPct(pct)}`);
  if (Number.isFinite(budgetKrw) && budgetKrw > 0) parts.push(`예산 ${formatKrw(budgetKrw)}`);
  if (Number.isFinite(cashLeft) && cashLeft > 0) parts.push(`미사용 현금 ${formatKrw(cashLeft)}`);
  if (parts.length) {
    return parts.join(" · ");
  }
  return "포트폴리오 평가액 입력 후 금액 산출";
}

function renderWhy(best, scenario) { { /* deprecated */ }
  const metrics = [
    ["CVaR · 나쁜 날 평균손실", best?.base_cvar_95, best?.proposed_cvar_95, true],
    ["MDD · 최대 낙폭", best?.base_mdd, best?.proposed_mdd, true],
    ["Beta · 시장 민감도", best?.base_beta_sp500_krw, best?.proposed_beta_sp500_krw, false],
    ["Downside beta · 하락장 민감도", best?.base_downside_beta_sp500_krw, best?.proposed_downside_beta_sp500_krw, false],
    ["Sharpe · 위험 대비 성과", best?.base_sharpe_krw_proxy, best?.proposed_sharpe_krw_proxy, false],
  ];
  dom.whyGrid.innerHTML = `
    <article class="analysis-card wide">
      <h3>${escapeHtml(candidateName(best))} 전후 비교</h3>
      ${metrics.map(([label, before, after, lossMetric]) => beforeAfterBar(label, before, after, lossMetric)).join("")}
    </article>
    <article class="analysis-card">
      <h3>줄어든 시나리오 위험</h3>
      <p>${escapeHtml(scenarioRiskText(best))}</p>
      <dl class="metric-grid compact">
        ${metric("기존 취약도", formatNumber(best?.base_scenario_vulnerability), `${titlePrefix} 적용 전 시나리오 취약도`)}
        ${metric(`${titlePrefix} 적용 후 취약도`, formatNumber(best?.proposed_scenario_vulnerability), `${titlePrefix} 적용 후 시나리오 취약도`)}
        ${metric("취약도 변화", formatSigned(best?.scenario_vulnerability_delta), "음수이면 취약도가 줄었다는 뜻")}
      </dl>
    </article>
    <article class="analysis-card">
      <h3>활성 시장국면</h3>
      <ul class="plain-list">
        ${(scenario.topActiveScenarios || []).slice(0, 5).map((row) => `<li>${escapeHtml(scenarioLabel(row))} · ${escapeHtml(row.final_display_state || row.display_state || "")}</li>`).join("") || "<li>활성 시나리오 없음</li>"}
      </ul>
    </article>
  `;
}

function renderTrustLegacy(manifest, hedge, scenario, backtest, eventStatus, decision = {}) {
  const dq = hedge.dqSummary || {};
  const coverage = backtest.coverageSummary || {};
  const statusCounts = decision.statusCounts || countStatuses(allCandidateRows(hedge));
  const freshness = payload.dataFreshness || {};
  const insufficient = backtest.verdictCounts?.INSUFFICIENT_HISTORY || 0;
  const quality = BACKTEST_QUALITY_LABELS[coverage.qualityLevel] || coverage.qualityLevel || "검증 강도 미정";
  const warningText = coverage.warnings?.length
    ? coverage.warnings.slice(0, 2).join(" ")
    : `INSUFFICIENT_HISTORY ${insufficient}건은 성공으로 계산하지 않습니다.`;
  const marketBasisText = `가격 data_version ${freshness.dataVersion || payload.activeBundle?.data_version || "-"} · 시나리오 data_version ${freshness.scenarioDataVersion || "-"} · 공통 기준 ${freshness.scenarioVectorAsOfDate || payload.activeBundle?.scenario_vector_as_of_date || "-"}`;
  const eventMode = eventStatus.mode || "상태 미정";
  const tradeUsage = eventStatus.trade_gate_usage || eventStatus.recommendation_usage || "사용 범위 미정";
  const liveStatus = eventStatus.live_gemini_extraction || "실시간 추출 상태 미정";
  const bootstrapRows = Number(coverage.targetBootstrapRows || 0);
  const robustBootstrapRows = Number(coverage.targetBootstrapRobustRows || 0);
  const weakBootstrapRows = Number(coverage.targetBootstrapUncertainRows || 0) + Number(coverage.targetBootstrapWorseRows || 0);
  const bootstrapText = bootstrapRows
    ? ` Bootstrap 강건 ${robustBootstrapRows}/${bootstrapRows}; 불확실/악화 ${weakBootstrapRows}건.`
    : "";
  dom.trustGrid.innerHTML = [
    trustCard("데이터 품질", `PASS ${dq.pass || 0} · WARN ${dq.warn || 0} · FAIL ${dq.fail || 0}`, "DQ FAIL이 있으면 정식 추천 신뢰도가 낮아집니다."),
    trustCard("시장 데이터 기준", scenario.dataAsOfDate || "-", marketBasisText),
    trustCard("Backtest", `${quality} · stress case ${coverage.evaluatedCaseCount || 0}개`, `${warningText} 비용/슬리피지 가정이 있는 경우 비용 조정 수익률로 판정합니다.${bootstrapText}`),
    trustCard("이벤트 오버레이", eventMode, `${tradeUsage} · ${liveStatus}`),
    trustCard("추천 게이트", `${statusCounts.PASS_RECOMMEND || 0} 정식 · ${statusCounts.REFERENCE_ONLY || 0} 참고`, decision.canExecuteRecommendations === false ? `${decision.title || "실행 추천 불가"} 후보 카드는 감사 목록입니다.` : `${coverage.cashLagRows || 0}개 검증행이 현금 보유 기준보다 약합니다.`),
  ].join("");
}

function renderTerms() {
  dom.termGrid.innerHTML = TERM_DEFINITIONS.map(([term, easy, description]) => `
    <article class="term-card">
      <h3>${escapeHtml(term)} · ${escapeHtml(easy)} <span class="tooltip" title="${escapeHtml(description)}">?</span></h3>
      <p>${escapeHtml(description)}</p>
    </article>
  `).join("");
}

function renderExpert(manifest, hedge, scenario, backtest) {
  const artifacts = { ...(scenario.artifacts || {}), ...(hedge.artifacts || {}) };
  const manifestArtifacts = manifest.artifacts || {};
  Object.entries(manifestArtifacts).forEach(([key, value]) => { artifacts[key] = value; });
  const actionArtifacts = payload.actionPlanArtifacts || {};
  Object.entries(actionArtifacts).forEach(([key, value]) => {
    const artifactPath = value?.path || value;
    if (artifactPath) artifacts[key] = artifactPath;
  });
  dom.expertGrid.innerHTML = `
    <article class="analysis-card">
      <h3>Run Bundle</h3>
      <pre>${escapeHtml(JSON.stringify(payload.activeBundle || {}, null, 2))}</pre>
    </article>
    <article class="analysis-card">
      <h3>Backtest Counts</h3>
      <pre>${escapeHtml(JSON.stringify(backtest.verdictCounts || {}, null, 2))}</pre>
    </article>
    <article class="analysis-card">
      <h3>Backtest Coverage</h3>
      <pre>${escapeHtml(JSON.stringify(backtest.coverageSummary || {}, null, 2))}</pre>
    </article>
    ${formalGateAuditPanel(backtest)}
    <article class="analysis-card wide">
      <h3>산출물 링크</h3>
      <div class="artifact-list">
        ${Object.entries(artifacts).filter(([, value]) => value).map(([key, value]) => artifactLink(key, value)).join("")}
      </div>
    </article>
  `;
}

function artifactLink(key, value) {
  const rel = String(value || "");
  const href = rel.startsWith("http") ? rel : `/artifact/${encodeURIComponent(rel).replace(/%2F/g, "/")}`;
  return `<a href="${escapeHtml(href)}" target="_blank" rel="noreferrer">${escapeHtml(key)}</a>`;
}

function formalGateAuditPanel(backtest) {
  const audit = backtest?.formalGateAuditSummary || {};
  const rows = (audit.topRows || []).slice(0, 6);
  const blockerCounts = audit.blockerCounts || {};
  const blockerText = Object.entries(blockerCounts)
    .slice(0, 6)
    .map(([key, value]) => `${key}: ${value}`)
    .join(" · ");
  if (!rows.length) {
    return `
      <article class="analysis-card wide">
        <h3>Formal Gate Near-misses</h3>
        <p class="expert-muted">No formal gate audit rows are available for the active bundle.</p>
      </article>
    `;
  }
  return `
    <article class="analysis-card wide">
      <h3>Formal Gate Near-misses</h3>
      <p class="expert-muted">${escapeHtml(audit.rowCount || rows.length)} candidates audited. ${escapeHtml(blockerText || "No blocker counts available.")}</p>
      <div class="table-wrap">
        <table class="data-table expert-audit-table">
          <thead>
            <tr>
              <th>Candidate</th>
              <th>Status</th>
              <th>Readiness</th>
              <th>Cash Stress</th>
              <th>Bootstrap</th>
              <th>Liquidity</th>
              <th>Blockers</th>
            </tr>
          </thead>
          <tbody>
            ${rows.map((row) => `
              <tr>
                <td>${escapeHtml(row.candidate_name || "-")}</td>
                <td>${escapeHtml(row.recommendation_status || "-")}</td>
                <td>${formatNumber(row.formal_readiness_score)}</td>
                <td>${formatSigned(row.target_avg_cash_net_stress_delta)}</td>
                <td>${escapeHtml(`${formatNumber(row.target_bootstrap_min_p_improve)} min p · ${formatNumber(row.target_bootstrap_robust_count)}/${formatNumber(row.target_bootstrap_count)} robust`)}</td>
                <td>${escapeHtml(row.liquidity_capacity_status || "-")}</td>
                <td>${escapeHtml(shortBlockerText(row.formal_gate_blockers))}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      </div>
    </article>
  `;
}

function shortBlockerText(value) {
  const parts = String(value || "")
    .split("|")
    .map((item) => item.trim())
    .filter(Boolean);
  if (!parts.length) return "-";
  const visible = parts.slice(0, 4).join(", ");
  return parts.length > 4 ? `${visible}, +${parts.length - 4}` : visible;
}

function pickBestCandidate(hedge, activeCodes = new Set()) {
  const rows = allCandidateRows(hedge)
    .filter((row) => row.recommendation_status)
    .sort((a, b) => compareCandidateRows(a, b, activeCodes));
  return rows[0] || hedge.portfolioBestDetail || {};
}

function statusRank(row) {
  return { PASS_RECOMMEND: 0, REFERENCE_ONLY: 1, FAIL_GATE: 2, INSUFFICIENT_DATA: 3 }[row.recommendation_status] ?? 9;
}

function referenceQualityRank(row) {
  if (row?.recommendation_status !== "REFERENCE_ONLY") return 0;
  const gateStatus = row?.backtest_gate_status || "";
  const targetEvaluated = intField(row, "backtest_target_evaluated_count");
  const targetBeatsCash = intField(row, "backtest_target_beats_cash_count");
  const targetLagsCash = intField(row, "backtest_target_lags_cash_count");
  if (gateStatus === "VALIDATION_THIN" && targetBeatsCash > 0 && targetLagsCash <= 0) return 0;
  if (gateStatus === "VALIDATED" || gateStatus === "PARTIAL_VALIDATION") return 1;
  if (gateStatus === "VALIDATION_THIN" && targetEvaluated > 0) return 2;
  if (gateStatus === "REFERENCE_ONLY_BACKTEST") return 3;
  if (gateStatus === "REFERENCE_ONLY_CASH_BASELINE") return 4;
  if (gateStatus === "VALIDATION_INSUFFICIENT") return 5;
  if (gateStatus === "VALIDATION_MISSING") return 6;
  return 7;
}

function compareCandidateRows(a, b, activeCodes = new Set()) {
  return statusRank(a) - statusRank(b)
    || referenceQualityRank(a) - referenceQualityRank(b)
    || scenarioMatchScore(b, activeCodes) - scenarioMatchScore(a, activeCodes)
    || intField(a, "backtest_target_lags_cash_count") - intField(b, "backtest_target_lags_cash_count")
    || intField(b, "backtest_target_beats_cash_count") - intField(a, "backtest_target_beats_cash_count")
    || intField(b, "backtest_target_evaluated_count") - intField(a, "backtest_target_evaluated_count")
    || numeric(b.final_score) - numeric(a.final_score)
    || candidateName(a).localeCompare(candidateName(b), "ko");
}

function activeScenarioCodes(scenario) {
  return new Set((scenario?.topActiveScenarios || [])
    .filter((row) => !["OFF", "PROVISIONAL"].includes(row.final_display_state || row.display_state))
    .map((row) => row.scenario_code || row.code)
    .filter(Boolean));
}

function scenarioMatchScore(row, activeCodes = new Set()) {
  if (!activeCodes || !activeCodes.size) return 0;
  const matchedCodes = splitScenarioCodes(row?.active_adverse_scenarios || row?.risk_bucket_match || "");
  return matchedCodes.filter((code) => activeCodes.has(code)).length;
}

function splitScenarioCodes(value) {
  return String(value || "")
    .split("|")
    .map((item) => item.trim())
    .filter(Boolean);
}

function activeScenarioLabels(scenario) {
  return (scenario.topActiveScenarios || [])
    .filter((row) => !["OFF", "PROVISIONAL"].includes(row.final_display_state || row.display_state))
    .map(scenarioLabel)
    .filter(Boolean);
}

function scenarioLabel(row) {
  const code = row.scenario_code || row.code;
  return row.scenario_name_ko || SCENARIO_LABELS[code] || code || "";
}

function scenarioRiskText(row) {
  const rawFit = row?.active_adverse_scenarios || row?.risk_bucket_match || "";
  if (rawFit && rawFit !== "core_hedge") {
    return `${candidateFit(row)}에 대응하는 후보입니다. 전체 포트폴리오 위험지표와 Backtest 판정을 함께 확인하세요.`;
  }
  if (rawFit === "core_hedge") {
    return "특정 활성 시나리오 전용 후보가 아니라 방어 성격의 핵심 헷지 후보입니다. 과거검증이 부족하면 정식 추천으로 보지 않습니다.";
  }
  const text = row?.scenario_reason_ko || row?.recommendation_reason || "";
  if (text) return text;
  return "활성 adverse scenario의 포트폴리오 취약도를 줄이는 후보입니다.";
}

function candidateName(row) {
  if (row?.displayLabel) return row.displayLabel;
  if (row?.candidate_combo) return humanizeAssetCombo(row.candidate_combo);
  if (row?.candidate_ticker) return assetDisplayLabel(row.candidate_ticker);
  if (row?.candidate_label) return humanizeAssetCombo(row.candidate_label);
  return "후보 없음";
}

function assetDisplayLabel(ticker) {
  const option = assetOptions.find((item) => item.ticker === ticker);
  if (option) return option.displayLabel || `${option.label} (${option.ticker})`;
  const fallback = {
    GLD: "금 ETF (GLD)",
    IAU: "금 ETF (IAU)",
    SHY: "단기 미국국채 ETF (SHY)",
    IEF: "중기 미국국채 ETF (IEF)",
    TLT: "장기 미국국채 ETF (TLT)",
    TSLA: "Tesla (TSLA)",
    AAPL: "Apple (AAPL)",
    "005930.KS": "삼성전자 (005930.KS)",
  };
  return fallback[ticker] || ticker || "-";
}

function humanizeAssetCombo(label) {
  return String(label || "")
    .split(" + ")
    .map((part) => assetDisplayLabel(part.trim()))
    .filter(Boolean)
    .join(" + ");
}

function beforeAfterBar(label, before, after, lossMetric) {
  const beforeNum = Math.abs(numeric(before));
  const afterNum = Math.abs(numeric(after));
  const max = Math.max(beforeNum, afterNum, 0.0001);
  const beforePct = Math.min(100, (beforeNum / max) * 100);
  const afterPct = Math.min(100, (afterNum / max) * 100);
  const improved = lossMetric ? afterNum <= beforeNum : numeric(after) >= numeric(before);
  return `
    <div class="bar-compare">
      <div class="bar-head">
        <strong>${escapeHtml(label)}</strong>
        <span>${improved ? "개선" : "주의"}</span>
      </div>
      <div class="bar-row"><span>Before</span><progress class="bar-progress" value="${escapeHtml(beforePct.toFixed(2))}" max="100"></progress><b>${formatNumber(before)}</b></div>
      <div class="bar-row after"><span>After</span><progress class="bar-progress" value="${escapeHtml(afterPct.toFixed(2))}" max="100"></progress><b>${formatNumber(after)}</b></div>
    </div>
  `;
}

function summaryCard(label, value, copy) {
  return `<article class="status-card"><span class="status-label">${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong><p>${escapeHtml(copy)}</p></article>`;
}

function trustCard(title, value, copy) {
  return `<article class="trust-card"><span>${escapeHtml(title)}</span><strong>${escapeHtml(value)}</strong><p>${escapeHtml(copy)}</p></article>`;
}

function metric(label, value, title) {
  return `<div title="${escapeHtml(title)}"><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value)}</dd></div>`;
}

function bannerHtml(kind, text) {
  const title = kind === "ok" ? "공식 실행 묶음 정상" : kind === "warning" ? "확인 필요" : "불러오는 중";
  return `<div class="status-message ${kind}"><strong>${title}</strong><span>${escapeHtml(text)}</span></div>`;
}

function renderError(error) {
  dom.banner.innerHTML = bannerHtml("warning", error.message || "대시보드 데이터를 불러오지 못했습니다.");
  dom.conclusionTitle.textContent = "공식 실행 묶음이 준비되지 않았습니다.";
  dom.conclusionCopy.textContent = "최신 산출물로 임시 표시를 시도합니다. HedgeMate/outputs/latest_manifest.json 생성 여부를 확인하세요.";
}

function emptyState(text) {
  return `<div class="empty-state">${escapeHtml(text)}</div>`;
}

async function fetchJson(url) {
  const response = await fetch(url);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.error || `${url} 요청 실패`);
  }
  return data;
}

async function postJson(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload || {}),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.error || `${url} 요청 실패`);
  }
  return data;
}

function setBusy(isBusy) {
  dom.refreshButton.disabled = isBusy;
  dom.refreshButton.textContent = isBusy ? "불러오는 중" : "새로고침";
}

function countStatuses(rows) {
  return rows.reduce((acc, row) => {
    const key = row.recommendation_status || "UNKNOWN";
    acc[key] = (acc[key] || 0) + 1;
    return acc;
  }, {});
}

function numeric(value) {
  const number = Number(value);
  return Number.isFinite(number) ? number : 0;
}

function formatPct(value) {
  const number = numeric(value);
  if (!Number.isFinite(number)) return "-";
  return `${number.toFixed(1)}%`;
}

function formatSigned(value) {
  const number = numeric(value);
  return `${number >= 0 ? "+" : ""}${number.toFixed(4)}`;
}

function formatNumber(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "-";
  if (Math.abs(number) < 1) return number.toFixed(4);
  return number.toFixed(2);
}

function formatShares(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "-";
  return number.toLocaleString("ko-KR", { maximumFractionDigits: 4 });
}

function formatKrw(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "-";
  return `${Math.round(number).toLocaleString("ko-KR")}원`;
}

function formatPrice(value, currency) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "-";
  if (currency === "KRW") return `${Math.round(number).toLocaleString("ko-KR")}원`;
  return `${number.toLocaleString("en-US", { maximumFractionDigits: 2 })} ${currency || ""}`.trim();
}

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}


/*******************************************************************************
 * Portfolio Vulnerability Analyzer - New Functions
 ******************************************************************************/

async function loadScenarioSensitivities() {
  try {
    const path = payload.manifest?.artifacts?.assetScenarioSensitivity;
    if (!path) {
      scenarioSensitivities = [];
      return;
    }
    const url = `/artifact/${encodeURIComponent(path).replace(/%2F/g, "/")}`;
    const csvText = await fetch(url).then(r => {
      if (!r.ok) throw new Error(`HTTP error ${r.status}`);
      return r.text();
    });
    scenarioSensitivities = parseCsv(csvText);
    console.log("Successfully loaded scenario sensitivities:", scenarioSensitivities.length);
  } catch (error) {
    console.error("Failed to load scenario sensitivities:", error);
    scenarioSensitivities = [];
  }
}

function parseCsv(text) {
  if (!text) return [];
  const lines = text.split(/\r?\n/);
  if (lines.length < 2) return [];
  const headers = lines[0].split(",").map(h => h.trim().replace(/^["']|["']$/g, ""));
  const rows = [];
  for (let i = 1; i < lines.length; i++) {
    const line = lines[i].trim();
    if (!line) continue;
    
    const cells = [];
    let currentCell = "";
    let insideQuotes = false;
    for (let j = 0; j < line.length; j++) {
      const char = line[j];
      if (char === '"') {
        insideQuotes = !insideQuotes;
      } else if (char === ',' && !insideQuotes) {
        cells.push(currentCell.trim().replace(/^["']|["']$/g, ""));
        currentCell = "";
      } else {
        currentCell += char;
      }
    }
    cells.push(currentCell.trim().replace(/^["']|["']$/g, ""));
    
    if (cells.length > 0) {
      const row = {};
      headers.forEach((header, index) => {
        row[header] = cells[index] !== undefined ? cells[index] : "";
      });
      rows.push(row);
    }
  }
  return rows;
}

function getAssetScenarioBeta(ticker, scenarioCode) {
  const row = scenarioSensitivities.find(
    r => r.ticker === ticker && r.scenario_code === scenarioCode
  );
  if (!row) return 0;
  const beta = parseFloat(row.scenario_beta);
  return Number.isFinite(beta) ? beta : 0;
}

function getAssetScenarioSensitivity(ticker, scenarioCode) {
  return scenarioSensitivities.find(
    r => r.ticker === ticker && r.scenario_code === scenarioCode
  );
}

function renderVulnerabilityAnalysisLegacy(hedge, scenario) {
  const activeRows = (scenario.topActiveScenarios || [])
    .filter((row) => !["OFF", "PROVISIONAL"].includes(row.final_display_state || row.display_state));
  
  if (!activeRows.length) {
    dom.vulnerabilityTop3Container.innerHTML = emptyState("현재 시장 기준 활성화된 위기 시나리오가 없습니다.");
    return;
  }

  const baseWeights = hedge.basePortfolioWeights || [];
  const nonCashWeights = baseWeights.filter(w => w.ticker !== "__CASH__");
  const totalNonCashWeight = nonCashWeights.reduce((sum, w) => sum + (w.weightPct || 0), 0);

  const scenarioVulnerabilities = activeRows.map(row => {
    const code = row.scenario_code || row.code;
    const nameKo = row.scenario_name_ko || SCENARIO_LABELS[code] || code || "";
    
    let vs = 0.0;
    const causative = [];
    const offset = [];

    nonCashWeights.forEach(w => {
      const sens = getAssetScenarioSensitivity(w.ticker, code);
      if (sens) {
        const beta = parseFloat(sens.scenario_beta) || 0.0;
        const normalizedWeight = totalNonCashWeight > 0 ? (w.weightPct / totalNonCashWeight) : 0;
        if (beta > 0) {
          vs += normalizedWeight * beta;
          causative.push({
            ticker: w.ticker,
            weight: w.weightPct,
            beta: beta,
            contribution: normalizedWeight * beta
          });
        } else if (beta < 0) {
          offset.push({
            ticker: w.ticker,
            beta: beta
          });
        }
      }
    });

    causative.sort((a, b) => b.contribution - a.contribution);
    offset.sort((a, b) => a.beta - b.beta);

    return {
      code,
      nameKo,
      score: vs,
      description: SCENARIO_DESCRIPTIONS[code] || "설명이 등록되지 않은 시나리오국면입니다.",
      causative,
      offset
    };
  });

  scenarioVulnerabilities.sort((a, b) => b.score - a.score);
  const top3 = scenarioVulnerabilities.slice(0, 3);

  dom.vulnerabilityTop3Container.innerHTML = top3.map((sv, idx) => {
    const causativeHtml = sv.causative.slice(0, 3).map(c => `
      <li class="causative-item">
        <strong class="ticker-link">${escapeHtml(c.ticker)}</strong> (비중 ${formatPct(c.weight)} · 기여 ${c.contribution.toFixed(3)})
        <span class="beta-badge risk-badge">beta ${c.beta.toFixed(2)}</span>
      </li>
    `).join("") || `<li class="causative-item muted-text">해당 없음</li>`;

    const offsetHtml = sv.offset.slice(0, 3).map(o => `
      <li class="offset-item">
        <strong class="ticker-link">${escapeHtml(o.ticker)}</strong>
        <span class="beta-badge safe-badge">beta ${o.beta.toFixed(2)}</span>
      </li>
    `).join("") || `<li class="offset-item muted-text">해당 없음</li>`;

    return `
      <div class="vulnerability-card glass-card">
        <div class="vulnerability-card-header">
          <div class="vulnerability-rank">#${idx + 1}</div>
          <div class="vulnerability-title-group">
            <h4>${escapeHtml(sv.nameKo)}</h4>
            <span class="vulnerability-code-label">${escapeHtml(sv.code)}</span>
          </div>
          <div class="vulnerability-score-badge">
            취약 점수: <strong>${sv.score.toFixed(3)}</strong>
          </div>
        </div>
        <p class="vulnerability-desc">${escapeHtml(sv.description)}</p>
        
        <div class="vulnerability-analysis-group">
          <div class="causative-box">
            <h5>주요 위험 유발 보유자산</h5>
            <ul>${causativeHtml}</ul>
          </div>
          <div class="offset-box">
            <h5>위험 완화 보유자산 (Offset)</h5>
            <ul>${offsetHtml}</ul>
          </div>
        </div>
      </div>
    `;
  }).join("");
}

function renderVulnerabilityContributorsLegacy(hedge, scenario) {
  const activeRows = (scenario.topActiveScenarios || [])
    .filter((row) => !["OFF", "PROVISIONAL"].includes(row.final_display_state || row.display_state));

  if (!activeRows.length) {
    dom.contributorsContainer.innerHTML = emptyState("분석할 활성 시나리오가 없습니다.");
    return;
  }

  const baseWeights = hedge.basePortfolioWeights || [];
  const nonCashWeights = baseWeights.filter(w => w.ticker !== "__CASH__");
  const totalNonCashWeight = nonCashWeights.reduce((sum, w) => sum + (w.weightPct || 0), 0);

  let topScenarioCode = null;
  let highestScore = -1;
  let topScenarioName = "";

  activeRows.forEach(row => {
    const code = row.scenario_code || row.code;
    let vs = 0.0;
    nonCashWeights.forEach(w => {
      const beta = getAssetScenarioBeta(w.ticker, code);
      if (beta > 0) {
        vs += (w.weightPct / totalNonCashWeight) * beta;
      }
    });
    if (vs > highestScore) {
      highestScore = vs;
      topScenarioCode = code;
      topScenarioName = row.scenario_name_ko || SCENARIO_LABELS[code] || code || "";
    }
  });

  if (!topScenarioCode) {
    dom.contributorsContainer.innerHTML = emptyState("보유자산 기여도를 분석할 수 없습니다.");
    return;
  }

  const rowsData = nonCashWeights.map(w => {
    const sens = getAssetScenarioSensitivity(w.ticker, topScenarioCode);
    const beta = sens ? parseFloat(sens.scenario_beta) || 0.0 : 0.0;
    const normalizedWeight = totalNonCashWeight > 0 ? (w.weightPct / totalNonCashWeight) : 0;
    const contribution = beta > 0 ? normalizedWeight * beta : 0.0;
    const notes = sens ? sens.notes || "" : "";
    const assetClass = sens ? sens.asset_class || "" : "";
    const assetName = sens ? sens.asset_name || w.ticker : w.ticker;

    return {
      ticker: w.ticker,
      name: assetName,
      class: assetClass,
      weight: w.weightPct,
      beta: beta,
      contribution: contribution,
      notes: notes
    };
  });

  rowsData.sort((a, b) => b.contribution - a.contribution || b.weight - a.weight);

  dom.contributorsContainer.innerHTML = `
    <div class="contributors-card glass-card">
      <div class="contributors-card-header">
        <h4>최대 위험 국면 [${escapeHtml(topScenarioName)}] 상세 분석</h4>
        <p>각 보유자산의 비중 대비 취약도 기여도를 봅니다. 위험 기여도가 비중보다 크게 높으면 해당 자산이 핵심 위험 요인입니다.</p>
      </div>
      <div class="table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th>자산 (Ticker)</th>
              <th>자산군</th>
              <th>보유 비중</th>
              <th>시나리오 민감도 (Beta)</th>
              <th>위험 기여도</th>
              <th>정량 분석 및 전문가 코멘트</th>
            </tr>
          </thead>
          <tbody>
            ${rowsData.map(r => {
              const contribPct = highestScore > 0 ? (r.contribution / highestScore) * 100 : 0;
              const barWidth = Math.min(Math.max(contribPct, 0), 100).toFixed(0);
              const highlightClass = r.contribution > 0.05 ? "high-risk" : "";
              return `
                <tr class="${highlightClass}">
                  <td>
                    <strong>${escapeHtml(r.name)}</strong><br>
                    <small class="muted-text">${escapeHtml(r.ticker)}</small>
                  </td>
                  <td><span class="asset-class-badge">${escapeHtml(r.class)}</span></td>
                  <td>${formatPct(r.weight)}</td>
                  <td>
                    <span class="beta-badge ${r.beta > 0 ? "risk-badge" : "safe-badge"}">
                      ${r.beta.toFixed(3)}
                    </span>
                  </td>
                  <td>
                    <div class="contrib-cell">
                      <strong>${r.contribution.toFixed(3)}</strong>
                      <div class="contrib-bar-wrap">
                        <div class="contrib-bar-fill" style="width: ${barWidth}%"></div>
                      </div>
                      <small class="muted-text">${barWidth}% 기여</small>
                    </div>
                  </td>
                  <td class="expert-comment-cell">
                    ${escapeHtml(r.notes || "해당 국면의 특정 민감도 특이사항 없음.")}
                  </td>
                </tr>
              `;
            }).join("")}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

function getTopCausativeAsset(hedge, scenario) {
  const activeRows = (scenario.topActiveScenarios || [])
    .filter((row) => !["OFF", "PROVISIONAL"].includes(row.final_display_state || row.display_state));
  if (!activeRows.length) return null;

  const baseWeights = hedge.basePortfolioWeights || [];
  const nonCashWeights = baseWeights.filter(w => w.ticker !== "__CASH__");
  const totalNonCashWeight = nonCashWeights.reduce((sum, w) => sum + (w.weightPct || 0), 0);

  let topScenarioCode = null;
  let highestScore = -1;

  activeRows.forEach(row => {
    const code = row.scenario_code || row.code;
    let vs = 0.0;
    nonCashWeights.forEach(w => {
      const beta = getAssetScenarioBeta(w.ticker, code);
      if (beta > 0) {
        vs += (w.weightPct / totalNonCashWeight) * beta;
      }
    });
    if (vs > highestScore) {
      highestScore = vs;
      topScenarioCode = code;
    }
  });

  if (!topScenarioCode) return null;

  let topAsset = null;
  let maxContribution = -1;

  nonCashWeights.forEach(w => {
    const sens = getAssetScenarioSensitivity(w.ticker, topScenarioCode);
    const beta = sens ? parseFloat(sens.scenario_beta) || 0.0 : 0.0;
    const normalizedWeight = totalNonCashWeight > 0 ? (w.weightPct / totalNonCashWeight) : 0;
    const contribution = beta > 0 ? normalizedWeight * beta : 0.0;
    if (contribution > maxContribution) {
      maxContribution = contribution;
      topAsset = {
        ticker: w.ticker,
        weight: w.weightPct,
        beta: beta,
        scenarioCode: topScenarioCode,
        portfolioVulnerability: highestScore
      };
    }
  });

  return topAsset;
}

function renderActionRecommendationsLegacy(hedge, activeCodes, decision) {
  const allRows = [];
  
  const formalActions = allRows.filter(r => r.recommendation_status === "PASS_RECOMMEND");
  const reviewActions = allRows.filter(r => ["REFERENCE_ONLY", "INSUFFICIENT_DATA"].includes(r.recommendation_status));
  const failActions = allRows.filter(r => r.recommendation_status === "FAIL_GATE");

  const topCausative = getTopCausativeAsset(hedge, payload.scenario || {});
  const topCausativeAsset = topCausative ? topCausative.ticker : "보유자산";
  const topCausativeWeight = topCausative ? topCausative.weight : 10.0;
  const topCausativeBeta = topCausative ? topCausative.beta : 1.0;
  const highestScore = topCausative ? topCausative.portfolioVulnerability : 0.0;
  const scenarioCode = topCausative ? topCausative.scenarioCode : "";

  let formalHtml = "";
  if (formalActions.length > 0) {
    formalHtml = `
      <div class="action-status-group">
        <h3>공식 실행 추천 (FORMAL_ACTION)</h3>
        <p class="status-group-desc">엄격한 백테스트 게이트 및 정식 승인 기준을 통과한 실행 권장 헷지 포지션입니다.</p>
        <div class="candidate-actions-list">
          ${formalActions.map(row => renderCandidateActionGroup(row, true, topCausativeAsset, topCausativeWeight, topCausativeBeta, highestScore, scenarioCode)).join("")}
        </div>
      </div>
    `;
  } else {
    formalHtml = `
      <div class="no-formal-recommendations-banner">
        <div class="banner-icon">⚠️</div>
        <div class="banner-text">
          <h4>현재 엄격 검증 기준 하에 실행 추천 가능한 정식 헷지 포지션이 없습니다.</h4>
          <p>엄격한 백테스트 게이트 및 현금화 대비 통계 신뢰도 기준을 통과한 후보가 없으나, 시나리오 취약도를 완화할 수 있는 시뮬레이션 및 검토 후보는 제공됩니다. 아래의 검토 액션을 확인하십시오.</p>
        </div>
      </div>
    `;
  }

  let reviewHtml = "";
  if (reviewActions.length > 0) {
    reviewHtml = `
      <div class="action-status-group">
        <h3>검토 및 시뮬레이션 후보 (REVIEW_ACTION)</h3>
        <p class="status-group-desc">위험 완화 근거는 우수하나 데이터 부족 또는 엄격 기준 일부 미달로 참고용으로 제시된 헷지 포지션입니다.</p>
        <div class="candidate-actions-list">
          ${reviewActions.map(row => renderCandidateActionGroup(row, false, topCausativeAsset, topCausativeWeight, topCausativeBeta, highestScore, scenarioCode)).join("")}
        </div>
      </div>
    `;
  } else {
    reviewHtml = `
      <div class="action-status-group">
        <h3>검토 및 시뮬레이션 후보 (REVIEW_ACTION)</h3>
        <div class="empty-state">검토 가능한 헷지 포지션이 없습니다.</div>
      </div>
    `;
  }

  let failHtml = "";
  if (failActions.length > 0) {
    failHtml = `
      <details class="failed-actions-audit-panel">
        <summary>제외/탈락된 후보 및 백테스트 게이트 불합격 근거 (${failActions.length}개 후보)</summary>
        <div class="failed-actions-content">
          <table class="data-table">
            <thead>
              <tr>
                <th>후보 자산</th>
                <th>게이트 상태</th>
                <th>주요 탈락 원인</th>
                <th>현금 대비 백테스트 결과</th>
                <th>성과 지표</th>
              </tr>
            </thead>
            <tbody>
              ${failActions.map(row => `
                <tr>
                  <td><strong>${escapeHtml(candidateName(row))}</strong></td>
                  <td><span class="candidate-alert danger">FAIL_GATE</span></td>
                  <td class="expert-comment-cell">${escapeHtml(splitPrimaryReason(row.gate_fail_reasons || row.backtest_reason || "기준 미통과"))}</td>
                  <td>${escapeHtml(backtestEvidenceText(row))}</td>
                  <td>
                    CVaR: ${formatPct(row.cvar_improve_pct)} · 
                    MDD: ${formatPct(row.mdd_improve_pct)} · 
                    Sharpe: ${formatPct(row.sharpe_improve_pct)}
                  </td>
                </tr>
              `).join("")}
            </tbody>
          </table>
        </div>
      </details>
    `;
  }

  dom.actionsContainer.innerHTML = `
    ${formalHtml}
    ${reviewHtml}
    ${failHtml}
  `;
}

function renderCandidateActionGroup(row, isFormal, topCausativeAsset, topCausativeWeight, topCausativeBeta, highestScore, scenarioCode) {
  const candidateNameStr = candidateName(row);
  return "";

  return `
    <div class="candidate-actions-group glass-card">
      <div class="candidate-actions-header">
        <div class="candidate-meta">
          <span class="action-type-badge ${isFormal ? 'formal' : 'review'}">
            ${isFormal ? '공식 실행 추천안' : '검토 액션 · 시뮬레이션 후보'}
          </span>
          <h4>${escapeHtml(candidateNameStr)}</h4>
          <span class="candidate-notes">${escapeHtml(candidateFit(row))}</span>
        </div>
        <div class="candidate-overall-stats">
          <span>CVaR 개선: <strong>${formatPct(row.cvar_improve_pct)}</strong></span>
          <span>MDD 개선: <strong>${formatPct(row.mdd_improve_pct)}</strong></span>
        </div>
      </div>
      
      <div class="action-cards-grid">
        <!-- ADD_HEDGE CARD -->
        <div class="action-card add-hedge">
          <div class="action-card-badge">ADD HEDGE (비중 추가)</div>
          <p class="action-card-desc">기존 포트폴리오를 유지한 상태에서 헷지 예산(10% 현금 예산)만큼 <strong>${escapeHtml(candidateNameStr)}</strong>를 신규 매수합니다.</p>
          <div class="action-weight-change">
            <div class="weight-item"><span>현금 (Cash)</span><strong>10% ➔ 0%</strong></div>
            <div class="weight-item"><span>${escapeHtml(candidateNameStr)}</span><strong>0% ➔ 10%</strong></div>
          </div>
          <div class="action-metrics-change">
            <dl>
              <div><dt>CVaR</dt><dd>${formatPct(row.base_cvar_95)} ➔ ${formatPct(row.proposed_cvar_95)}</dd></div>
              <div><dt>MDD</dt><dd>${formatPct(row.base_mdd)} ➔ ${formatPct(row.proposed_mdd)}</dd></div>
              <div><dt>Stress 수익률</dt><dd>${formatSigned(row.base_stress_avg_ret_krw)} ➔ ${formatSigned(row.proposed_stress_avg_ret_krw)}</dd></div>
            </dl>
          </div>
          <div class="action-card-footer">
            <span>Sharpe: ${formatNumber(row.base_sharpe_krw_proxy)} ➔ ${formatNumber(row.proposed_sharpe_krw_proxy)}</span>
          </div>
        </div>

        <!-- TRIM_AND_HEDGE CARD -->
        <div class="action-card trim-and-hedge">
          <div class="action-card-badge warning">TRIM & HEDGE (비중 축소 후 헤지)</div>
          <p class="action-card-desc">취약 요인인 <strong>${escapeHtml(topCausativeAsset)}</strong> 비중을 5% 줄이고, 그 자금으로 <strong>${escapeHtml(candidateNameStr)}</strong>를 5% 매수합니다.</p>
          <div class="action-weight-change">
            <div class="weight-item"><span>${escapeHtml(topCausativeAsset)}</span><strong>${topCausativeWeight.toFixed(1)}% ➔ ${(topCausativeWeight - 5).toFixed(1)}%</strong></div>
            <div class="weight-item"><span>${escapeHtml(candidateNameStr)}</span><strong>0% ➔ 5%</strong></div>
          </div>
          <div class="action-metrics-change">
            <dl>
              <div><dt>Vulnerability</dt><dd>-</dd></div>
              <div><dt>CVaR</dt><dd>-</dd></div>
              <div><dt>MDD</dt><dd>-</dd></div>
            </dl>
          </div>
          <div class="action-card-footer">
            <span>보유비중 조정을 통한 취약점 직접 개선</span>
          </div>
        </div>

        <!-- REPLACE_SLEEVE CARD -->
        <div class="action-card replace-sleeve">
          <div class="action-card-badge danger">REPLACE SLEEVE (슬리브 교체)</div>
          <p class="action-card-desc">취약 요인인 <strong>${escapeHtml(topCausativeAsset)}</strong>를 전량 매도하고, 동일 비중만큼 <strong>${escapeHtml(candidateNameStr)}</strong>로 교체합니다.</p>
          <div class="action-weight-change">
            <div class="weight-item"><span>${escapeHtml(topCausativeAsset)}</span><strong>${topCausativeWeight.toFixed(1)}% ➔ 0%</strong></div>
            <div class="weight-item"><span>${escapeHtml(candidateNameStr)}</span><strong>0% ➔ ${topCausativeWeight.toFixed(1)}%</strong></div>
          </div>
          <div class="action-metrics-change">
            <dl>
              <div><dt>Vulnerability</dt><dd>-</dd></div>
              <div><dt>CVaR</dt><dd>-</dd></div>
              <div><dt>MDD</dt><dd>-</dd></div>
            </dl>
          </div>
          <div class="action-card-footer">
            <span>가장 적극적인 취약성 위험 제거 액션</span>
          </div>
        </div>
      </div>

      <details class="candidate-compliance-details">
        <summary>백테스트 검증 및 게이트 심사 통과 현황</summary>
        <div class="compliance-details-content">
          <p>${escapeHtml(backtestEvidenceText(row))}</p>
          <p>${escapeHtml(candidateDecisionText(row))}</p>
          ${candidateAlertTags(row)}
          ${decisionReasonsHtml(row)}
        </div>
      </details>
    </div>
  `;
}

function selectedActionRows() {
  return Array.isArray(payload?.hedgeActionPlan) ? payload.hedgeActionPlan : [];
}

function actionCandidateRows() {
  return Array.isArray(payload?.hedgeActionCandidates) ? payload.hedgeActionCandidates : [];
}

function vulnerabilitySummaryData() {
  const summary = payload?.portfolioVulnerabilitySummary || {};
  return summary.data || summary || {};
}

function vulnerabilitySleeves() {
  const data = vulnerabilitySummaryData();
  const rows = Array.isArray(data.risk_sleeves)
    ? data.risk_sleeves
    : Array.isArray(data.top_vulnerabilities)
      ? data.top_vulnerabilities
      : [];
  return rows
    .slice()
    .sort((a, b) => numeric(b.net_vulnerability) - numeric(a.net_vulnerability));
}

function vulnerabilityAttributionRows() {
  return Array.isArray(payload?.portfolioVulnerabilityAttribution)
    ? payload.portfolioVulnerabilityAttribution
    : [];
}

function actionStatus(row) {
  return String(row?.action_status || row?.actionStatus || row?.status || "NO_ACTION")
    .trim()
    .toUpperCase()
    .replace(/[-\s]+/g, "_");
}

function actionType(row) {
  return String(row?.action_type || row?.actionType || "NO_ACTION")
    .trim()
    .toUpperCase()
    .replace(/[-\s]+/g, "_");
}

function actionStatusCounts(rows = selectedActionRows()) {
  return rows.reduce((acc, row) => {
    const key = actionStatus(row);
    acc[key] = (acc[key] || 0) + 1;
    return acc;
  }, {});
}

function actionStatusRank(row) {
  return {
    FORMAL_ACTION: 0,
    REVIEW_ACTION: 1,
    RESEARCH_ONLY: 2,
    FAIL_ACTION: 3,
    NO_ACTION: 4,
  }[actionStatus(row)] ?? 9;
}

function pickBestAction() {
  return selectedActionRows()
    .slice()
    .sort((a, b) => actionStatusRank(a) - actionStatusRank(b)
      || numeric(a.vulnerability_delta) - numeric(b.vulnerability_delta)
      || numeric(b.vulnerability_improve_pct) - numeric(a.vulnerability_improve_pct)
      || String(a.action_id || "").localeCompare(String(b.action_id || ""), "ko"))
    [0] || null;
}

function actionLabel(row) {
  const candidate = row?.candidate_label || splitList(row?.candidate_tickers).join(" + ");
  return candidate || row?.action_id || "Action";
}

function splitList(value) {
  if (Array.isArray(value)) return value.map((item) => String(item).trim()).filter(Boolean);
  return String(value || "")
    .split(/[|,]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function parseWeights(value) {
  if (!value) return {};
  if (typeof value === "object") return value;
  try {
    const parsed = JSON.parse(value);
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : {};
  } catch {
    return {};
  }
}

function changedWeightRows(row, limit = 6) {
  const before = parseWeights(row?.before_weights_json || row?.beforeWeightsJson || row?.before_weights);
  const after = parseWeights(row?.after_weights_json || row?.afterWeightsJson || row?.after_weights);
  if (!Object.keys(before).length && !Object.keys(after).length) {
    const aliasRows = [];
    const source = row?.source_asset || splitList(row?.source_tickers)[0];
    const hedge = row?.hedge_asset || splitList(row?.candidate_tickers)[0];
    if (source) {
      aliasRows.push({
        ticker: source,
        before: numeric(row.source_current_weight_pct ?? row.current_weight),
        after: numeric(row.source_proposed_weight_pct ?? row.proposed_weight),
        delta: numeric(row.source_proposed_weight_pct ?? row.proposed_weight) - numeric(row.source_current_weight_pct ?? row.current_weight),
      });
    }
    if (hedge && hedge !== source) {
      aliasRows.push({
        ticker: hedge,
        before: numeric(row.hedge_current_weight_pct),
        after: numeric(row.hedge_proposed_weight_pct),
        delta: numeric(row.hedge_proposed_weight_pct) - numeric(row.hedge_current_weight_pct),
      });
    }
    return aliasRows.filter((item) => Number.isFinite(item.before) || Number.isFinite(item.after)).slice(0, limit);
  }
  const tickers = Array.from(new Set([...Object.keys(before), ...Object.keys(after)]));
  return tickers
    .map((ticker) => ({
      ticker,
      before: numeric(before[ticker]),
      after: numeric(after[ticker]),
      delta: numeric(after[ticker]) - numeric(before[ticker]),
    }))
    .filter((item) => Math.abs(item.delta) > 0.0001 || item.after > 0)
    .sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta) || a.ticker.localeCompare(b.ticker, "ko"))
    .slice(0, limit);
}

function formatHumanPct(value, options = {}) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "-";
  const scaled = options.ratio || Math.abs(number) <= 1 ? number * 100 : number;
  const sign = options.signed && scaled > 0 ? "+" : "";
  return `${sign}${scaled.toFixed(options.digits ?? 1)}%`;
}

function formatDeltaValue(value, digits = 4) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "-";
  return `${number >= 0 ? "+" : ""}${number.toFixed(digits)}`;
}

function sleeveLabel(row) {
  return row?.risk_sleeve_label_ko || row?.risk_sleeve_label || row?.risk_sleeve || "-";
}

function sleeveAttributionRows(sleeveCode) {
  return vulnerabilityAttributionRows()
    .filter((row) => row.risk_sleeve === sleeveCode)
    .sort((a, b) => numeric(b.vulnerability_contribution) - numeric(a.vulnerability_contribution));
}

function holdingContributionLine(holding, sleeveCode) {
  const ticker = holding?.ticker || "-";
  const attr = sleeveAttributionRows(sleeveCode).find((row) => row.ticker === ticker) || {};
  const weightValue = attr.current_weight_pct ?? attr.weight_pct;
  const contributionPct = attr.contribution_pct_of_sleeve ?? attr.sleeve_contribution_pct;
  const weight = Number.isFinite(Number(weightValue)) ? `보유 ${formatHumanPct(weightValue, { digits: 1 })}` : "보유비중 -";
  const share = Number.isFinite(Number(contributionPct))
    ? `취약성 기여 ${formatHumanPct(contributionPct, { digits: 1 })}`
    : `기여 ${formatNumber(holding?.contribution)}`;
  return `<li class="causative-item"><strong class="ticker-link">${escapeHtml(ticker)}</strong><span>${escapeHtml(`${weight} · ${share}`)}</span></li>`;
}

function renderConclusion(best, activeScenarios, hedge, scenario, decision = {}) {
  const actionRows = selectedActionRows();
  const counts = decision.statusCounts || actionStatusCounts(actionRows);
  const topSleeve = vulnerabilitySleeves()[0] || {};
  const subject = analysisSubjectText(hedge);
  const topRisk = sleeveLabel(topSleeve);
  const formalCount = Number(decision.formalActionCount ?? counts.FORMAL_ACTION ?? 0);
  const reviewCount = Number(decision.reviewActionCount ?? counts.REVIEW_ACTION ?? 0);

  if (!actionRows.length) {
    dom.conclusionTitle.textContent = "정식 실행 추천 없음";
    dom.conclusionCopy.textContent = decision.whyNoFormalRecommendationKo || `${subject} 기준으로 취약성은 진단했지만, 현재 payload.hedgeActionPlan에 표시할 bounded action이 없습니다. 후보를 억지로 추천하지 않고 NO_ACTION 상태로 다룹니다.`;
    return;
  }

  if (!formalCount) {
    dom.conclusionTitle.textContent = "정식 실행 추천 없음";
    const reason = decision.whyNoFormalRecommendationKo || `${reviewCount}개의 REVIEW_ACTION은 리스크 완화 시뮬레이션일 뿐이며, 기존 formal recommendation gate를 통과한 실행 추천으로 표시하지 않습니다.`;
    dom.conclusionCopy.textContent = `${subject}의 가장 큰 취약성은 ${topRisk}입니다. ${reason}`;
    return;
  }

  dom.conclusionTitle.textContent = `${topRisk} 취약성 대응 액션`;
  dom.conclusionCopy.textContent = `${actionLabel(best)} 액션이 FORMAL_ACTION으로 분류되었습니다. 표시되는 before/after와 성과 지표는 프론트 추정치가 아니라 백엔드 hedgeActionPlan row의 값입니다.`;
}

function renderSummaryCards(best, activeScenarios, hedge, scenario, decision = {}) {
  const dq = hedge.dqSummary || {};
  const backtest = payload.backtest || {};
  const coverage = backtest.coverageSummary || {};
  const actionRows = selectedActionRows();
  const counts = decision.statusCounts || actionStatusCounts(actionRows);
  const sleeves = vulnerabilitySleeves();
  const summary = vulnerabilitySummaryData();
  const topSleeve = sleeves[0] || {};
  const formalCount = Number(decision.formalActionCount ?? counts.FORMAL_ACTION ?? 0);
  const reviewCount = Number(decision.reviewActionCount ?? counts.REVIEW_ACTION ?? 0);
  const failCount = Number((actionStatusCounts(actionCandidateRows()).FAIL_ACTION || 0) + (counts.FAIL_ACTION || 0));
  const decisionValue = formalCount > 0 ? `${formalCount}개 FORMAL_ACTION` : "정식 실행 추천 없음";
  const runText = payload.activeBundle?.hedgemate_run || payload.manifest?.active_hedgemate_run || "-";
  const freshness = payload.activeBundle?.freshness_status || payload.freshnessStatus || "-";

  dom.summaryCards.innerHTML = [
    summaryCard("Top 취약성", sleeveLabel(topSleeve), `취약성 점수 ${formatNumber(topSleeve.net_vulnerability)} · 전체 ${formatNumber(summary.portfolio_total_vulnerability)}`),
    summaryCard("원인 보유자산", (topSleeve.source_holdings || []).slice(0, 3).map((row) => row.ticker).join(", ") || "-", "portfolioVulnerabilitySummary의 source_holdings 기준입니다."),
    summaryCard("액션 판정", decisionValue, `REVIEW_ACTION ${reviewCount}개 · FAIL_ACTION 감사 ${failCount}개 · selected plan ${actionRows.length}개`),
    summaryCard("Run / 검증", `${freshness} · ${runText}`, `DQ PASS ${dq.pass || 0} · WARN ${dq.warn || 0} · FAIL ${dq.fail || 0} · ${backtestCoverageDetail(coverage, backtest)}`),
  ].join("");
}

function renderVulnerabilityAnalysis() {
  const sleeves = vulnerabilitySleeves().slice(0, 3);
  if (!sleeves.length) {
    dom.vulnerabilityTop3Container.innerHTML = emptyState("portfolioVulnerabilitySummary에 표시할 취약성 요약이 없습니다.");
    return;
  }

  dom.vulnerabilityTop3Container.innerHTML = sleeves.map((sleeve, index) => {
    const sourceHtml = (sleeve.source_holdings || [])
      .slice(0, 4)
      .map((holding) => holdingContributionLine(holding, sleeve.risk_sleeve))
      .join("") || `<li class="causative-item muted-text">주요 원인 보유자산 없음</li>`;
    const offsetHtml = (sleeve.offset_holdings || [])
      .slice(0, 4)
      .map((holding) => holdingContributionLine(holding, sleeve.risk_sleeve))
      .join("") || `<li class="offset-item muted-text">offset 보유자산 없음</li>`;
    const scenarios = (sleeve.scenario_codes || [])
      .map((code) => SCENARIO_LABELS[code] || code)
      .join(", ");
    const sources = (sleeve.source_holdings || []).slice(0, 3).map((row) => row.ticker).join(", ");
    const offsets = (sleeve.offset_holdings || []).slice(0, 3).map((row) => row.ticker).join(", ");
    const plain = `${sources || "일부 보유자산"} 비중과 민감도가 이 취약성을 키웁니다.${offsets ? ` ${offsets}는 일부 상쇄 역할을 합니다.` : " 현재 포트폴리오 안의 상쇄 자산은 제한적입니다."}`;

    return `
      <article class="vulnerability-card glass-card">
        <div class="vulnerability-card-header">
          <div class="vulnerability-rank">#${index + 1}</div>
          <div class="vulnerability-title-group">
            <h4>${escapeHtml(sleeveLabel(sleeve))}</h4>
            <span class="vulnerability-code-label">${escapeHtml(sleeve.risk_sleeve || "-")}</span>
          </div>
          <div class="vulnerability-score-badge">
            취약성 점수
            <strong>${escapeHtml(formatNumber(sleeve.net_vulnerability))}</strong>
          </div>
        </div>
        <p class="vulnerability-desc">${escapeHtml(plain)} ${scenarios ? `관련 시나리오: ${scenarios}` : ""}</p>
        <div class="vulnerability-analysis-group">
          <div class="causative-box">
            <h5>주요 원인 보유자산</h5>
            <ul>${sourceHtml}</ul>
          </div>
          <div class="offset-box">
            <h5>Offset 보유자산</h5>
            <ul>${offsetHtml}</ul>
          </div>
        </div>
      </article>
    `;
  }).join("");
}

function renderVulnerabilityContributors() {
  const rows = vulnerabilityAttributionRows();
  const sleeveCodes = new Set(vulnerabilitySleeves().slice(0, 3).map((row) => row.risk_sleeve).filter(Boolean));
  const visibleRows = rows
    .filter((row) => !sleeveCodes.size || sleeveCodes.has(row.risk_sleeve))
    .filter((row) => row.source_or_offset !== "neutral")
    .sort((a, b) => numeric(b.vulnerability_contribution) - numeric(a.vulnerability_contribution))
    .slice(0, 18);

  if (!visibleRows.length) {
    dom.contributorsContainer.innerHTML = emptyState("portfolioVulnerabilityAttribution에 표시할 보유자산 기여도 row가 없습니다.");
    return;
  }

  dom.contributorsContainer.innerHTML = `
    <div class="contributors-card glass-card">
      <div class="contributors-card-header">
        <h4>취약성을 만든 보유자산</h4>
        <p>보유비중과 취약성 기여도를 함께 보여줍니다. 이 표는 portfolioVulnerabilityAttribution row를 그대로 사용합니다.</p>
      </div>
      <div class="table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th>Risk sleeve</th>
              <th>보유자산</th>
              <th>보유비중</th>
              <th>취약성 기여</th>
              <th>Sleeve 내 비중</th>
              <th>역할</th>
              <th>Evidence</th>
            </tr>
          </thead>
          <tbody>
            ${visibleRows.map((row) => `
              <tr class="${numeric(row.contribution_pct_of_sleeve ?? row.sleeve_contribution_pct) >= 20 ? "high-risk" : ""}">
                <td>${escapeHtml(sleeveLabel(row))}<br><small class="muted-text">${escapeHtml(row.risk_sleeve || "-")}</small></td>
                <td><strong>${escapeHtml(row.asset_ticker || row.ticker || "-")}</strong><br><small class="muted-text">${escapeHtml(row.asset_name || row.asset_class || "")}</small></td>
                <td>${escapeHtml(formatHumanPct(row.current_weight_pct ?? row.weight_pct, { digits: 1 }))}</td>
                <td>
                  <div class="contrib-cell">
                    <strong>${escapeHtml(formatNumber(row.weighted_contribution ?? row.vulnerability_contribution))}</strong>
                    <small class="muted-text">${escapeHtml(formatHumanPct(row.contribution_pct_of_total ?? row.portfolio_contribution_pct, { digits: 1 }))} of portfolio</small>
                  </div>
                </td>
                <td>${escapeHtml(formatHumanPct(row.contribution_pct_of_sleeve ?? row.sleeve_contribution_pct, { digits: 1 }))}</td>
                <td><span class="asset-class-badge">${escapeHtml(row.source_or_offset || "-")}</span></td>
                <td>${escapeHtml(row.evidence_quality || "-")}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

function renderActionRecommendations(decision = {}) {
  const planRows = selectedActionRows();
  const candidateRows = actionCandidateRows();
  const counts = decision.statusCounts || actionStatusCounts(planRows);
  const formalRows = planRows.filter((row) => actionStatus(row) === "FORMAL_ACTION");
  const reviewRows = planRows.filter((row) => actionStatus(row) === "REVIEW_ACTION");
  const researchRows = planRows.filter((row) => actionStatus(row) === "RESEARCH_ONLY");
  const noActionRows = planRows.filter((row) => actionStatus(row) === "NO_ACTION");
  const failedRows = candidateRows.filter((row) => actionStatus(row) === "FAIL_ACTION")
    .concat(planRows.filter((row) => actionStatus(row) === "FAIL_ACTION"));

  const formalReasons = Array.isArray(decision.formalActionBlockersKo) && decision.formalActionBlockersKo.length
    ? decision.formalActionBlockersKo
    : (decision.whyNoFormalRecommendationKo ? [decision.whyNoFormalRecommendationKo] : ["기존 formal recommendation gate를 통과한 FORMAL_ACTION이 없습니다."]);
  const upgradeItems = Array.isArray(decision.formalActionUpgradeRequirements) ? decision.formalActionUpgradeRequirements : [];
  const noFormalBanner = formalRows.length ? "" : `
    <div class="no-formal-recommendations-banner">
      <div class="banner-icon">!</div>
      <div class="banner-text">
        <h4>정식 실행 추천 없음</h4>
        <p>${escapeHtml(formalReasons[0])}</p>
        ${formalReasons.length > 1 ? `<ul>${formalReasons.slice(1, 4).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>` : ""}
        ${upgradeItems.length ? `<p class="small-note">정식 추천으로 올라가려면: ${escapeHtml(upgradeItems.slice(0, 3).join(" · "))}</p>` : ""}
      </div>
    </div>
  `;

  const groups = [
    actionGroupHtml("FORMAL_ACTION", "정식 실행 추천", "엄격 gate를 통과한 실행 가능 액션입니다.", formalRows),
    actionGroupHtml("REVIEW_ACTION", "검토 액션", "리스크는 낮추지만 정식 추천 기준은 미달한 시뮬레이션 후보입니다.", reviewRows),
    actionGroupHtml("RESEARCH_ONLY", "리서치 전용", "인버스/레버리지/옵션/변동성 상품처럼 실행 추천과 분리된 연구용 row입니다.", researchRows),
    actionGroupHtml("NO_ACTION", "유효 액션 없음", "해당 취약성에 대해 bounded action을 만들 수 없다는 백엔드 판정입니다.", noActionRows),
  ].filter(Boolean).join("");

  const planEmpty = planRows.length ? "" : emptyState("payload.hedgeActionPlan에 selected action row가 없습니다. 후보 리스트를 대신 추천처럼 표시하지 않습니다.");

  dom.actionsContainer.innerHTML = `
    ${noFormalBanner}
    ${planEmpty}
    ${groups}
    ${actionTypeCoverageHtml(decision)}
    ${failedActionAuditHtml(failedRows, counts)}
  `;
}

function actionTypeCoverageHtml(decision = {}) {
  const coverage = decision.actionTypeCoverage || payload.hedgeActionPlanMeta?.action_type_coverage || {};
  const keys = ["ADD_HEDGE", "TRIM_AND_HEDGE", "REPLACE_SLEEVE", "NO_ACTION"];
  if (!keys.some((key) => coverage[key])) return "";
  return `
    <details class="failed-actions-audit-panel action-coverage-panel" open>
      <summary>왜 특정 액션 타입이 선택되지 않았나</summary>
      <div class="action-coverage-grid">
        ${keys.map((key) => {
          const row = coverage[key] || {};
          const state = Number(row.selected_count || 0) > 0 ? "선택됨" : Number(row.count || row.candidate_count || 0) > 0 ? "후보만 있음" : "후보 없음";
          const reason = row.absence_reason_ko || row.reason_ko || "설명 없음";
          return `
            <div class="coverage-chip">
              <strong>${escapeHtml(key)}</strong>
              <span>${escapeHtml(state)} · 후보 ${escapeHtml(row.count ?? row.candidate_count ?? 0)} · 선택 ${escapeHtml(row.selected_count ?? 0)}</span>
              <p>${escapeHtml(reason)}</p>
            </div>
          `;
        }).join("")}
      </div>
    </details>
  `;
}

function actionGroupHtml(status, title, description, rows) {
  if (!rows.length) return "";
  const sortedRows = rows
    .slice()
    .sort((a, b) => numeric(a.vulnerability_delta) - numeric(b.vulnerability_delta)
      || numeric(b.vulnerability_improve_pct) - numeric(a.vulnerability_improve_pct));
  return `
    <section class="action-status-group">
      <h3>${escapeHtml(title)} <span class="asset-class-badge">${escapeHtml(status)}</span></h3>
      <p class="status-group-desc">${escapeHtml(description)}</p>
      <div class="action-cards-grid">
        ${sortedRows.map((row) => actionPlanCard(row)).join("")}
      </div>
    </section>
  `;
}

function actionPlanCard(row) {
  const status = actionStatus(row);
  const type = actionType(row);
  const statusClass = status === "FORMAL_ACTION" ? "formal" : status === "REVIEW_ACTION" ? "review" : "danger";
  const typeClass = type === "TRIM_AND_HEDGE" ? "trim-and-hedge" : type === "REPLACE_SLEEVE" ? "replace-sleeve" : "add-hedge";
  const sourceTickers = splitList(row.source_tickers).join(", ") || "-";
  const offsetTickers = splitList(row.offset_tickers).join(", ") || "-";
  const candidateTickers = splitList(row.candidate_tickers).join(" + ") || actionLabel(row);
  const selectionText = row.selection_reason_ko || row.status_reason_ko || "";
  const rejectedText = row.rejected_reason_ko || "";
  const expectedEffect = row.expected_effect || "";
  const weights = changedWeightRows(row);
  const weightHtml = weights.length
    ? weights.map((item) => `
      <div class="weight-item">
        <span>${escapeHtml(item.ticker)}</span>
        <strong>${escapeHtml(`${formatHumanPct(item.before, { digits: 1 })} -> ${formatHumanPct(item.after, { digits: 1 })}`)}</strong>
      </div>
    `).join("")
    : `<div class="weight-item"><span>Before/After</span><strong>백엔드 row에 weight JSON 없음</strong></div>`;

  return `
    <article class="action-card ${escapeHtml(typeClass)}">
      <div class="action-card-badge ${escapeHtml(statusClass === "danger" ? "danger" : statusClass === "review" ? "warning" : "")}">
        ${escapeHtml(ACTION_TYPE_LABELS[type] || type)} · ${escapeHtml(ACTION_STATUS_LABELS[status] || status)}
      </div>
      <h4>${escapeHtml(actionLabel(row))}</h4>
      <p class="action-card-desc">${escapeHtml(row.plain_korean_reason || row.action_reason_ko || `${sourceTickers} 취약성에 대해 ${candidateTickers}를 사용하는 백엔드 action row입니다.`)}</p>
      ${selectionText ? `<p class="action-card-desc action-reason">${escapeHtml(selectionText)}</p>` : ""}
      <div class="action-weight-change">
        ${weightHtml}
      </div>
      <div class="action-metrics-change">
        <dl>
          <div><dt>취약성</dt><dd>${escapeHtml(`${formatNumber(row.before_sleeve_vulnerability)} -> ${formatNumber(row.after_sleeve_vulnerability)} (${formatDeltaValue(row.vulnerability_delta)})`)}</dd></div>
          <div><dt>CVaR · 극단 나쁜 장 평균손실</dt><dd>${escapeHtml(`${formatHumanPct(row.base_cvar_95, { ratio: true })} -> ${formatHumanPct(row.proposed_cvar_95, { ratio: true })}`)}</dd></div>
          <div><dt>MDD · 최대하락폭</dt><dd>${escapeHtml(`${formatHumanPct(row.base_mdd, { ratio: true })} -> ${formatHumanPct(row.proposed_mdd, { ratio: true })}`)}</dd></div>
          <div><dt>Beta · 시장 민감도</dt><dd>${escapeHtml(`${formatNumber(row.base_beta_sp500_krw)} -> ${formatNumber(row.proposed_beta_sp500_krw)}`)}</dd></div>
          <div><dt>Stress · 충격 구간</dt><dd>${escapeHtml(`${formatHumanPct(row.base_stress_avg_ret_krw, { ratio: true })} -> ${formatHumanPct(row.proposed_stress_avg_ret_krw, { ratio: true })}`)}</dd></div>
          <div><dt>Sharpe · 위험 대비 효율</dt><dd>${escapeHtml(`${formatNumber(row.base_sharpe_krw_proxy)} -> ${formatNumber(row.proposed_sharpe_krw_proxy)}`)}</dd></div>
        </dl>
      </div>
      ${expectedEffect ? `<p class="action-card-desc expected-effect">${escapeHtml(expectedEffect)}</p>` : ""}
      <div class="action-card-footer">
        <span>${escapeHtml(sleeveLabel(row))}</span>
        <span> · 원인 ${escapeHtml(sourceTickers)}</span>
        <span> · 후보 ${escapeHtml(candidateTickers)}</span>
        ${offsetTickers !== "-" ? `<span> · offset ${escapeHtml(offsetTickers)}</span>` : ""}
      </div>
      <details class="candidate-compliance-details">
        <summary>백엔드 action row 세부 근거</summary>
        <div class="compliance-details-content">
          <p>formal gate source: ${escapeHtml(row.formal_gate_source || row.linked_recommendation_status || "-")}</p>
          <p>constraint: ${escapeHtml(row.constraint_status || "-")} ${escapeHtml(row.constraint_reasons || "")}</p>
          <p>metric source: ${escapeHtml(row.metric_source || "-")} ${escapeHtml(row.metric_coverage_reason || "")}</p>
          ${rejectedText ? `<p>정식 추천 제외/제한: ${escapeHtml(rejectedText)}</p>` : ""}
        </div>
      </details>
    </article>
  `;
}

function failedActionAuditHtml(failedRows, counts = {}) {
  if (!failedRows.length) return "";
  const rows = failedRows.slice(0, 30);
  return `
    <details class="failed-actions-audit-panel">
      <summary>FAIL_ACTION 감사/탈락 근거 (${failedRows.length}개 후보)</summary>
      <div class="failed-actions-content">
        <div class="table-wrap">
          <table class="data-table">
            <thead>
              <tr>
                <th>Action</th>
                <th>Risk sleeve</th>
                <th>Type</th>
                <th>Candidate</th>
                <th>Constraint</th>
                <th>Reason</th>
              </tr>
            </thead>
            <tbody>
              ${rows.map((row) => `
                <tr>
                  <td>${escapeHtml(row.action_id || "-")}</td>
                  <td>${escapeHtml(sleeveLabel(row))}</td>
                  <td>${escapeHtml(actionType(row))}</td>
                  <td>${escapeHtml(actionLabel(row))}</td>
                  <td>${escapeHtml(row.constraint_status || "-")}</td>
                  <td class="expert-comment-cell">${escapeHtml(row.constraint_reasons || row.action_reason_ko || row.plain_korean_reason || "-")}</td>
                </tr>
              `).join("")}
            </tbody>
          </table>
        </div>
      </div>
    </details>
  `;
}

function renderTrust(manifest, hedge, scenario, backtest, eventStatus, actionDecision = {}, formalDecision = {}) {
  const dq = hedge.dqSummary || {};
  const coverage = backtest.coverageSummary || {};
  const actionRows = selectedActionRows();
  const actionCounts = actionDecision.statusCounts || actionStatusCounts(actionRows);
  const formalCounts = formalDecision.statusCounts || {};
  const freshness = payload.dataFreshness || {};
  const quality = BACKTEST_QUALITY_LABELS[coverage.qualityLevel] || coverage.qualityLevel || "검증 강도 미정";
  const marketBasisText = `price ${freshness.dataVersion || payload.activeBundle?.data_version || "-"} · scenario ${freshness.scenarioDataVersion || "-"} · as-of ${freshness.scenarioVectorAsOfDate || payload.activeBundle?.scenario_vector_as_of_date || "-"}`;
  const eventMode = eventStatus.mode || "event overlay status unknown";
  const liveStatus = eventStatus.live_gemini_extraction || "live extraction unknown";

  dom.trustGrid.innerHTML = [
    trustCard("데이터 품질", `PASS ${dq.pass || 0} · WARN ${dq.warn || 0} · FAIL ${dq.fail || 0}`, "DQ FAIL이 있으면 정식 실행 추천은 보수적으로 차단합니다."),
    trustCard("시장 데이터 기준", scenario.dataAsOfDate || "-", marketBasisText),
    trustCard("Backtest", `${quality} · stress ${coverage.evaluatedCaseCount || 0}개`, backtestCoverageDetail(coverage, backtest)),
    trustCard("이벤트 오버레이", eventMode, liveStatus),
    trustCard("Action plan", `FORMAL ${actionCounts.FORMAL_ACTION || 0} · REVIEW ${actionCounts.REVIEW_ACTION || 0}`, `count basis: ${actionDecision.countBasis || "hedgeActionPlan"} · old formal gate PASS ${formalCounts.PASS_RECOMMEND || formalDecision.formalRecommendationCount || 0}`),
  ].join("");
}
