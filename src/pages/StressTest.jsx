import React, { useState, useEffect } from 'react';
import { Zap, Briefcase, AlertTriangle, TrendingDown, Shield, ChevronDown, ChevronUp, Activity, Globe, Flame, Landmark, Bug, Wheat, ArrowRight } from 'lucide-react';
import { Button } from '../components/Button';
import { useNavigate } from 'react-router-dom';
import { usePortfolios } from '../context/PortfolioContext';
import './StressTest.css';

const SCENARIOS = [
  {
    id: 'war',
    name: '지정학적 전쟁',
    icon: <Flame size={20} />,
    desc: '대규모 군사 충돌 발생 시 글로벌 시장 충격 시뮬레이션',
    color: '#ef4444',
    bg: 'rgba(239,68,68,0.1)',
    example: '러시아-우크라이나 전쟁 (2022)',
    sectorImpact: {
      Technology: -18, Communication: -15, 'Consumer Cyclical': -22,
      Financial: -12, Energy: +24, Defense: +32,
    },
    marketDrop: -28,
    volatilitySpike: +180,
    recoveryMonths: 14,
    goldChange: +18,
    bondChange: +5,
    oilChange: +45,
  },
  {
    id: 'pandemic',
    name: '글로벌 팬데믹',
    icon: <Bug size={20} />,
    desc: '전염병 대유행으로 인한 경제활동 위축 시뮬레이션',
    color: '#8b5cf6',
    bg: 'rgba(139,92,246,0.1)',
    example: 'COVID-19 팬데믹 (2020)',
    sectorImpact: {
      Technology: -12, Communication: -8, 'Consumer Cyclical': -35,
      Financial: -28, Energy: -42, Healthcare: +15,
    },
    marketDrop: -34,
    volatilitySpike: +350,
    recoveryMonths: 8,
    goldChange: +12,
    bondChange: +8,
    oilChange: -65,
  },
  {
    id: 'financial_crisis',
    name: '금융 위기',
    icon: <Landmark size={20} />,
    desc: '대형 금융기관 연쇄 부도 및 신용경색 시뮬레이션',
    color: '#f59e0b',
    bg: 'rgba(245,158,11,0.1)',
    example: '글로벌 금융위기 (2008)',
    sectorImpact: {
      Technology: -38, Communication: -25, 'Consumer Cyclical': -42,
      Financial: -55, Energy: -32, 'Real Estate': -48,
    },
    marketDrop: -52,
    volatilitySpike: +420,
    recoveryMonths: 30,
    goldChange: +25,
    bondChange: +12,
    oilChange: -55,
  },
  {
    id: 'rate_shock',
    name: '급격한 금리 인상',
    icon: <Activity size={20} />,
    desc: '중앙은행 긴급 금리 인상(500bp+) 시나리오',
    color: '#06b6d4',
    bg: 'rgba(6,182,212,0.1)',
    example: '볼커 쇼크 (1980) / 2022 연준 긴축',
    sectorImpact: {
      Technology: -30, Communication: -20, 'Consumer Cyclical': -18,
      Financial: +5, Energy: -8, 'Real Estate': -35,
    },
    marketDrop: -25,
    volatilitySpike: +120,
    recoveryMonths: 18,
    goldChange: -8,
    bondChange: -15,
    oilChange: -12,
  },
  {
    id: 'commodity_crisis',
    name: '원자재 공급 충격',
    icon: <Wheat size={20} />,
    desc: '주요 원자재 공급망 붕괴로 인한 인플레이션 충격',
    color: '#10b981',
    bg: 'rgba(16,185,129,0.1)',
    example: '오일쇼크 (1973) / 공급망 위기 (2021)',
    sectorImpact: {
      Technology: -15, Communication: -10, 'Consumer Cyclical': -25,
      Financial: -12, Energy: +35, Agriculture: +28,
    },
    marketDrop: -18,
    volatilitySpike: +90,
    recoveryMonths: 12,
    goldChange: +22,
    bondChange: -5,
    oilChange: +80,
  },
  {
    id: 'cyber_attack',
    name: '대규모 사이버 공격',
    icon: <Globe size={20} />,
    desc: '글로벌 인프라 대상 사이버 공격으로 인한 시장 마비',
    color: '#ec4899',
    bg: 'rgba(236,72,153,0.1)',
    example: '가상 시나리오 — 글로벌 금융 인프라 해킹',
    sectorImpact: {
      Technology: -25, Communication: -30, 'Consumer Cyclical': -15,
      Financial: -35, Energy: -8, Cybersecurity: +40,
    },
    marketDrop: -22,
    volatilitySpike: +200,
    recoveryMonths: 6,
    goldChange: +15,
    bondChange: +10,
    oilChange: +8,
  },
];

// Simulate portfolio impact based on scenario
const simulateImpact = (portfolio, scenario) => {
  if (!portfolio || !scenario) return null;

  let portfolioImpact = 0;
  const assetResults = portfolio.assets.map(asset => {
    // Find matching sector impact or use average
    const sectorKeys = Object.keys(scenario.sectorImpact);
    let impact = scenario.marketDrop; // default fallback

    // Check if any sector matches the asset (using ticker DB knowledge)
    const techTickers = ['AAPL', 'NVDA', 'MSFT', 'GOOGL', 'META', 'SAMSUNG'];
    const financialTickers = ['JPM', 'V', 'BRK.B'];
    const cyclicalTickers = ['TSLA', 'AMZN', 'KIA'];

    if (techTickers.includes(asset.ticker)) {
      impact = scenario.sectorImpact.Technology || scenario.marketDrop;
    } else if (financialTickers.includes(asset.ticker)) {
      impact = scenario.sectorImpact.Financial || scenario.marketDrop;
    } else if (cyclicalTickers.includes(asset.ticker)) {
      impact = scenario.sectorImpact['Consumer Cyclical'] || scenario.marketDrop;
    }

    // Add some variance per asset
    const variance = ((asset.ticker.charCodeAt(0) % 10) - 5) * 0.8;
    const finalImpact = impact + variance;

    const lossAmount = asset.qty * asset.cost * (finalImpact / 100);
    portfolioImpact += lossAmount;

    return {
      ...asset,
      impact: parseFloat(finalImpact.toFixed(1)),
      lossAmount: Math.round(lossAmount),
      afterValue: Math.round(asset.qty * asset.cost * (1 + finalImpact / 100)),
    };
  });

  const totalBefore = portfolio.totalValue;
  const totalAfter = totalBefore + portfolioImpact;
  const totalImpactPct = ((portfolioImpact / totalBefore) * 100).toFixed(2);

  return {
    assetResults,
    totalBefore,
    totalAfter: Math.round(totalAfter),
    totalLoss: Math.round(portfolioImpact),
    totalImpactPct: parseFloat(totalImpactPct),
    estimatedRecovery: scenario.recoveryMonths,
    maxDrawdown: scenario.marketDrop,
    volatilitySpike: scenario.volatilitySpike,
    hedgeAssets: {
      gold: scenario.goldChange,
      bond: scenario.bondChange,
      oil: scenario.oilChange,
    },
  };
};

export const StressTest = () => {
  const navigate = useNavigate();
  const { portfolios } = usePortfolios();

  const [selectedPortfolioId, setSelectedPortfolioId] = useState(null);
  const [selectedScenario, setSelectedScenario] = useState(null);
  const [simulationResult, setSimulationResult] = useState(null);
  const [isSimulating, setIsSimulating] = useState(false);
  const [showDetails, setShowDetails] = useState(false);

  const selectedPortfolio = portfolios.find(p => p.id === selectedPortfolioId);

  useEffect(() => {
    if (!selectedPortfolioId && portfolios.length > 0) {
      setSelectedPortfolioId(portfolios[0].id);
    }
  }, [portfolios, selectedPortfolioId]);

  const runSimulation = () => {
    if (!selectedPortfolio || !selectedScenario) return;

    setIsSimulating(true);
    setSimulationResult(null);
    setShowDetails(false);

    // Fake loading for realism
    setTimeout(() => {
      const result = simulateImpact(selectedPortfolio, selectedScenario);
      setSimulationResult(result);
      setIsSimulating(false);
    }, 1500);
  };

  // No portfolios
  if (portfolios.length === 0) {
    return (
      <div className="stress-test-page">
        <div className="empty-report">
          <div className="empty-report-icon"><Briefcase size={48} /></div>
          <h2 className="mt-4">시뮬레이션할 포트폴리오가 없습니다</h2>
          <p className="text-secondary text-sm mt-2">먼저 포트폴리오를 등록해주세요.</p>
          <Button variant="primary" className="mt-6" onClick={() => navigate('/register')}>
            포트폴리오 등록하기 <ArrowRight size={14} />
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="stress-test-page">
      {/* Header */}
      <div className="stress-header mb-6">
        <span className="text-secondary text-xs font-semibold tracking-wider flex items-center gap-2">
          <Zap size={12} className="text-warning" />
          STRESS TEST SIMULATION
        </span>
        <h1 className="mt-2 mb-1">위기 시나리오 시뮬레이션</h1>
        <p className="text-secondary text-sm" style={{maxWidth: '600px', lineHeight: 1.6}}>
          다양한 거시경제 위기 시나리오에서 포트폴리오가 받을 영향을 사전에 분석하고, 방어 전략을 수립하세요.
        </p>
      </div>

      {/* Step 1: Select Portfolio */}
      <div className="sim-step mb-6">
        <div className="step-label">
          <span className="step-num">1</span>
          분석 대상 포트폴리오 선택
        </div>
        <div className="portfolio-chips">
          {portfolios.map(p => (
            <button
              key={p.id}
              className={`portfolio-chip ${selectedPortfolioId === p.id ? 'active' : ''}`}
              onClick={() => {
                setSelectedPortfolioId(p.id);
                setSimulationResult(null);
              }}
            >
              <Briefcase size={14} />
              <div className="chip-info">
                <span className="chip-name">{p.name}</span>
                <span className="chip-meta">{p.assets.length}종목 · ₩{p.totalValue.toLocaleString()}</span>
              </div>
              {p.status === 'new' && <span className="chip-new">NEW</span>}
            </button>
          ))}
        </div>
      </div>

      {/* Step 2: Select Scenario */}
      <div className="sim-step mb-6">
        <div className="step-label">
          <span className="step-num">2</span>
          위기 시나리오 선택
        </div>
        <div className="scenario-grid">
          {SCENARIOS.map(s => (
            <button
              key={s.id}
              className={`scenario-card ${selectedScenario?.id === s.id ? 'active' : ''}`}
              onClick={() => {
                setSelectedScenario(s);
                setSimulationResult(null);
              }}
              style={{ '--scenario-color': s.color, '--scenario-bg': s.bg }}
            >
              <div className="scenario-icon" style={{ background: s.bg, color: s.color }}>
                {s.icon}
              </div>
              <div className="scenario-info">
                <div className="scenario-name">{s.name}</div>
                <div className="scenario-desc">{s.desc}</div>
                <div className="scenario-example">{s.example}</div>
              </div>
              <div className="scenario-severity">
                <div className="severity-label">시장 충격</div>
                <div className="severity-value" style={{ color: s.color }}>{s.marketDrop}%</div>
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Step 3: Run Simulation */}
      <div className="sim-step mb-8">
        <div className="step-label">
          <span className="step-num">3</span>
          시뮬레이션 실행
        </div>
        <div className="sim-run-bar">
          <div className="sim-run-info">
            <span className="text-sm">
              {selectedPortfolio ? (
                <><strong>{selectedPortfolio.name}</strong> 에</>
              ) : '포트폴리오를 선택하세요'}
              {selectedScenario ? (
                <> <strong style={{color: selectedScenario.color}}>{selectedScenario.name}</strong> 시나리오 적용</>
              ) : ' — 시나리오를 선택하세요'}
            </span>
          </div>
          <Button
            variant="primary"
            onClick={runSimulation}
            disabled={!selectedPortfolio || !selectedScenario || isSimulating}
            style={{ minWidth: '160px' }}
          >
            {isSimulating ? (
              <><span className="spinner"></span> 분석 중...</>
            ) : (
              <><Zap size={14} /> 시뮬레이션 실행</>
            )}
          </Button>
        </div>
      </div>

      {/* Simulation Results */}
      {simulationResult && selectedScenario && (
        <div className="sim-results" style={{ '--scenario-color': selectedScenario.color }}>
          <div className="results-header">
            <div className="flex items-center gap-3">
              <div className="result-scenario-icon" style={{ background: selectedScenario.bg, color: selectedScenario.color }}>
                {selectedScenario.icon}
              </div>
              <div>
                <h2 className="font-semibold">{selectedScenario.name} 시뮬레이션 결과</h2>
                <p className="text-xs text-secondary mt-1">"{selectedPortfolio.name}" 기준 분석</p>
              </div>
            </div>
            <div className="result-impact-badge" style={{ color: selectedScenario.color, background: selectedScenario.bg }}>
              <TrendingDown size={14} />
              예상 손실 {simulationResult.totalImpactPct}%
            </div>
          </div>

          {/* Impact Summary Cards */}
          <div className="impact-grid mt-6">
            <div className="impact-card loss-card">
              <div className="impact-label">예상 총 손실</div>
              <div className="impact-value loss">₩{Math.abs(simulationResult.totalLoss).toLocaleString()}</div>
              <div className="impact-sublabel">{simulationResult.totalImpactPct}% 하락</div>
            </div>
            <div className="impact-card">
              <div className="impact-label">포트폴리오 잔여가치</div>
              <div className="impact-value">₩{simulationResult.totalAfter.toLocaleString()}</div>
              <div className="impact-sublabel">₩{simulationResult.totalBefore.toLocaleString()} → ₩{simulationResult.totalAfter.toLocaleString()}</div>
            </div>
            <div className="impact-card">
              <div className="impact-label">예상 회복 기간</div>
              <div className="impact-value">{simulationResult.estimatedRecovery}개월</div>
              <div className="impact-sublabel">역사적 평균 기준</div>
            </div>
            <div className="impact-card">
              <div className="impact-label">변동성 증가</div>
              <div className="impact-value warning">+{simulationResult.volatilitySpike}%</div>
              <div className="impact-sublabel">VIX 스파이크 예상</div>
            </div>
          </div>

          {/* Per-Asset Impact */}
          <div className="asset-impact-section mt-6">
            <div className="section-header" onClick={() => setShowDetails(!showDetails)} style={{cursor:'pointer'}}>
              <h3 className="font-semibold flex items-center gap-2">
                <AlertTriangle size={16} />
                종목별 영향 분석
              </h3>
              {showDetails ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
            </div>

            {showDetails && (
              <div className="asset-impact-table mt-4">
                <div className="impact-table-header">
                  <span>종목</span>
                  <span>현재 가치</span>
                  <span>예상 변동</span>
                  <span>예상 손실</span>
                  <span className="text-right">잔여 가치</span>
                </div>
                {simulationResult.assetResults.map(a => (
                  <div key={a.ticker} className="impact-table-row">
                    <div className="asset-name-cell">
                      <span className="font-semibold">{a.ticker}</span>
                      <span className="text-xs text-secondary">{a.name}</span>
                    </div>
                    <span className="text-sm">₩{(a.qty * a.cost).toLocaleString()}</span>
                    <span className={`text-sm font-semibold ${a.impact >= 0 ? 'text-green' : 'text-loss'}`}>
                      {a.impact >= 0 ? '+' : ''}{a.impact}%
                    </span>
                    <span className={`text-sm ${a.lossAmount >= 0 ? 'text-green' : 'text-loss'}`}>
                      {a.lossAmount >= 0 ? '+' : ''}₩{Math.abs(a.lossAmount).toLocaleString()}
                    </span>
                    <span className="text-sm text-right">₩{a.afterValue.toLocaleString()}</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Impact Bar Visualization */}
          <div className="impact-bars-section mt-6">
            <h3 className="font-semibold mb-4">종목별 영향도</h3>
            {simulationResult.assetResults.map(a => (
              <div key={a.ticker} className="impact-bar-row">
                <div className="impact-bar-label">
                  <span className="font-semibold text-sm">{a.ticker}</span>
                  <span className={`text-xs font-semibold ${a.impact >= 0 ? 'text-green' : 'text-loss'}`}>
                    {a.impact >= 0 ? '+' : ''}{a.impact}%
                  </span>
                </div>
                <div className="impact-bar-track">
                  <div
                    className={`impact-bar-fill ${a.impact >= 0 ? 'positive' : 'negative'}`}
                    style={{ width: `${Math.min(Math.abs(a.impact), 60)}%` }}
                  ></div>
                </div>
              </div>
            ))}
          </div>

          {/* Hedge Recommendation */}
          <div className="hedge-rec-section mt-6">
            <h3 className="font-semibold flex items-center gap-2 mb-4">
              <Shield size={16} className="text-accent-light" />
              방어 자산 예상 수익률
            </h3>
            <div className="hedge-cards">
              <div className="hedge-card">
                <div className="hedge-asset-name">🥇 금 (Gold)</div>
                <div className={`hedge-value ${simulationResult.hedgeAssets.gold >= 0 ? 'positive' : 'negative'}`}>
                  {simulationResult.hedgeAssets.gold >= 0 ? '+' : ''}{simulationResult.hedgeAssets.gold}%
                </div>
                <div className="text-xs text-secondary mt-1">안전자산 수요 증가</div>
              </div>
              <div className="hedge-card">
                <div className="hedge-asset-name">📊 국채 (Bond)</div>
                <div className={`hedge-value ${simulationResult.hedgeAssets.bond >= 0 ? 'positive' : 'negative'}`}>
                  {simulationResult.hedgeAssets.bond >= 0 ? '+' : ''}{simulationResult.hedgeAssets.bond}%
                </div>
                <div className="text-xs text-secondary mt-1">금리 방향에 따른 변동</div>
              </div>
              <div className="hedge-card">
                <div className="hedge-asset-name">🛢️ 원유 (Oil)</div>
                <div className={`hedge-value ${simulationResult.hedgeAssets.oil >= 0 ? 'positive' : 'negative'}`}>
                  {simulationResult.hedgeAssets.oil >= 0 ? '+' : ''}{simulationResult.hedgeAssets.oil}%
                </div>
                <div className="text-xs text-secondary mt-1">공급/수요 충격에 따른 변동</div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
