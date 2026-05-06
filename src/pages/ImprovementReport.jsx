import React, { useState, useEffect } from 'react';
import { Shield, Rocket, ChevronDown, ChevronUp, Download, RefreshCw, Briefcase, AlertCircle, ArrowRight } from 'lucide-react';
import { Button } from '../components/Button';
import { useNavigate } from 'react-router-dom';
import { usePortfolios } from '../context/PortfolioContext';
import './ImprovementReport.css';

// Simulate analysis data based on a portfolio's properties
const generateAnalysis = (portfolio) => {
  if (!portfolio) return null;

  // Use portfolio characteristics to seed pseudo-random but consistent results
  const seed = portfolio.assets.length * 17 + portfolio.totalValue * 0.000001;
  const riskFactor = portfolio.riskLevel === 'High' ? 1.3 : portfolio.riskLevel === 'Low' ? 0.7 : 1.0;

  const baseCvar = -(0.018 + (seed % 0.015)) * riskFactor;
  const baseMdd = -(0.14 + (seed % 0.08)) * riskFactor;
  const baseSharpe = (1.4 + (seed % 0.5)) / riskFactor;

  // Strategy impact multipliers
  let recMultipliers = { cvar: 0.82, mdd: 0.76, sharpe: 1.01 };
  let optMultipliers = { cvar: 0.76, mdd: 0.69, sharpe: 1.14 };

  if (portfolio.strategy === 'tail-risk') {
    recMultipliers = { cvar: 0.65, mdd: 0.60, sharpe: 0.95 }; // strong protection, less efficiency
    optMultipliers = { cvar: 0.55, mdd: 0.50, sharpe: 1.05 };
  } else if (portfolio.strategy === 'beta-neutral') {
    recMultipliers = { cvar: 0.50, mdd: 0.55, sharpe: 1.15 }; // very stable, medium efficiency
    optMultipliers = { cvar: 0.40, mdd: 0.45, sharpe: 1.25 };
  } else if (portfolio.strategy === 'defensive-overlay') {
    recMultipliers = { cvar: 0.90, mdd: 0.85, sharpe: 1.05 }; // light protection, cheap
    optMultipliers = { cvar: 0.85, mdd: 0.80, sharpe: 1.10 };
  } else if (portfolio.strategy === 'dynamic-hedge') {
    recMultipliers = { cvar: 0.70, mdd: 0.65, sharpe: 1.25 }; // high efficiency
    optMultipliers = { cvar: 0.60, mdd: 0.55, sharpe: 1.40 };
  }

  return {
    base: {
      cvar: parseFloat(baseCvar.toFixed(4)),
      mdd: parseFloat(baseMdd.toFixed(4)),
      sharpe: parseFloat(baseSharpe.toFixed(3)),
    },
    recommended: {
      cvar: parseFloat((baseCvar * recMultipliers.cvar).toFixed(4)),
      mdd: parseFloat((baseMdd * recMultipliers.mdd).toFixed(4)),
      sharpe: parseFloat((baseSharpe * recMultipliers.sharpe).toFixed(3)),
    },
    optimized: {
      cvar: parseFloat((baseCvar * optMultipliers.cvar).toFixed(4)),
      mdd: parseFloat((baseMdd * optMultipliers.mdd).toFixed(4)),
      sharpe: parseFloat((baseSharpe * optMultipliers.sharpe).toFixed(3)),
    },
  };
};

const calcImprove = (base, val) => {
  const pct = ((base - val) / Math.abs(base)) * 100;
  return pct;
};

export const ImprovementReport = () => {
  const navigate = useNavigate();
  const { portfolios } = usePortfolios();

  const [selectedPortfolioId, setSelectedPortfolioId] = useState(null);
  const [selectedMetric, setSelectedMetric] = useState('cvar');
  const [animateBars, setAnimateBars] = useState(false);
  const [expandedCard, setExpandedCard] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(new Date().toLocaleString('ko-KR'));

  const selectedPortfolio = portfolios.find(p => p.id === selectedPortfolioId);
  const portfolioData = generateAnalysis(selectedPortfolio);

  // Auto-select first portfolio if none selected
  useEffect(() => {
    if (!selectedPortfolioId && portfolios.length > 0) {
      setSelectedPortfolioId(portfolios[0].id);
    }
  }, [portfolios, selectedPortfolioId]);

  useEffect(() => {
    setAnimateBars(false);
    const timer = setTimeout(() => setAnimateBars(true), 300);
    return () => clearTimeout(timer);
  }, [selectedPortfolioId]);

  const handleRefresh = () => {
    setAnimateBars(false);
    setLastUpdated(new Date().toLocaleString('ko-KR'));
    setTimeout(() => setAnimateBars(true), 300);
  };

  const handlePortfolioChange = (id) => {
    setSelectedPortfolioId(id);
    setExpandedCard(null);
    setLastUpdated(new Date().toLocaleString('ko-KR'));
  };

  const metricLabels = { cvar: 'CVaR', mdd: 'MDD', sharpe: 'Sharpe' };

  const getBarWidth = (type) => {
    if (!portfolioData) return 0;
    const val = Math.abs(portfolioData[type][selectedMetric]);
    const base = Math.abs(portfolioData.base[selectedMetric]);
    if (selectedMetric === 'sharpe') {
      return (val / 2.5) * 100;
    }
    return (val / (base * 1.1)) * 100;
  };

  const getImproveText = (type) => {
    if (!portfolioData) return '';
    const baseVal = portfolioData.base[selectedMetric];
    const val = portfolioData[type][selectedMetric];
    if (type === 'base') return '0.00% 개선';
    const pct = calcImprove(baseVal, val);
    const abs = Math.abs(pct).toFixed(2);
    if (selectedMetric === 'sharpe') {
      const spct = (((val - baseVal) / Math.abs(baseVal)) * 100).toFixed(2);
      return `${parseFloat(spct) >= 0 ? '↑' : '↓'} ${Math.abs(spct)}% 개선`;
    }
    return `${pct >= 0 ? '↑' : '↓'} ${abs}% 개선`;
  };

  const handleDownload = () => {
    if (!portfolioData) return;
    const csvContent = [
      '제안유형,CVaR,MDD,Sharpe',
      `기존,${portfolioData.base.cvar},${portfolioData.base.mdd},${portfolioData.base.sharpe}`,
      `제안(1:1),${portfolioData.recommended.cvar},${portfolioData.recommended.mdd},${portfolioData.recommended.sharpe}`,
      `제안(다자산),${portfolioData.optimized.cvar},${portfolioData.optimized.mdd},${portfolioData.optimized.sharpe}`,
    ].join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `hedgemate_report_${selectedPortfolio?.name || 'unknown'}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // ─── No portfolios state ───
  if (portfolios.length === 0) {
    return (
      <div className="report-page">
        <div className="empty-report">
          <div className="empty-report-icon">
            <Briefcase size={48} />
          </div>
          <h2 className="mt-4">분석할 포트폴리오가 없습니다</h2>
          <p className="text-secondary text-sm mt-2" style={{maxWidth: '400px', lineHeight: 1.6}}>
            먼저 포트폴리오를 등록해야 분석 리포트를 확인할 수 있습니다.<br />
            포트폴리오를 등록하고 HedgeMate의 분석을 시작하세요.
          </p>
          <Button variant="primary" className="mt-6" onClick={() => navigate('/register')}>
            포트폴리오 등록하기 <ArrowRight size={14} />
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="report-page">
      {/* Flow Breadcrumb */}
      <div className="flow-breadcrumb mb-6">
        <span className="flow-crumb" onClick={() => navigate('/register')} style={{cursor:'pointer'}}>
          <span className="crumb-step">1</span> 포트폴리오 등록
        </span>
        <span className="flow-arrow">→</span>
        <span className="flow-crumb" onClick={() => navigate('/portfolios')} style={{cursor:'pointer'}}>
          <span className="crumb-step">2</span> 내 포트폴리오
        </span>
        <span className="flow-arrow">→</span>
        <span className="flow-crumb active">
          <span className="crumb-step">3</span> 분석 리포트
        </span>
      </div>

      {/* ─── Portfolio Selector ─── */}
      <div className="portfolio-selector mb-6">
        <div className="selector-header">
          <div className="flex items-center gap-2">
            <div className="selector-icon"><Briefcase size={16} /></div>
            <div>
              <div className="text-xs text-secondary font-semibold" style={{letterSpacing: '0.05em'}}>분석 대상 포트폴리오</div>
              <div className="text-sm font-semibold mt-1">
                {selectedPortfolio ? selectedPortfolio.name : '포트폴리오를 선택하세요'}
              </div>
            </div>
          </div>
          {selectedPortfolio && (
            <div className="flex items-center gap-4">
              {selectedPortfolio.strategy && (
                <div className="flex flex-col items-end mr-4">
                  <span className="text-[0.65rem] text-secondary font-semibold uppercase tracking-wider">적용된 전략</span>
                  <span className="text-xs text-accent-light font-semibold">{selectedPortfolio.strategyName}</span>
                </div>
              )}
              <div className="selector-meta">
                <span className="selector-tag">{selectedPortfolio.purpose}</span>
                <span className="selector-tag">{selectedPortfolio.assets.length}종목</span>
                <span className="selector-tag accent">₩{selectedPortfolio.totalValue.toLocaleString()}</span>
              </div>
            </div>
          )}
        </div>

        <div className="selector-list">
          {portfolios.map(p => (
            <button
              key={p.id}
              className={`selector-item ${selectedPortfolioId === p.id ? 'active' : ''}`}
              onClick={() => handlePortfolioChange(p.id)}
            >
              <div className="selector-item-info">
                <span className="font-semibold text-sm flex items-center gap-2">
                  {p.name}
                  {p.strategy && <span className="badge-purple" style={{padding: '1px 4px', fontSize: '10px'}}>{p.strategyName}</span>}
                </span>
                <span className="text-xs text-secondary">{p.purpose} · {p.assets.length}종목</span>
              </div>
              <div className="selector-item-right">
                <span className="text-xs font-semibold">₩{p.totalValue.toLocaleString()}</span>
                {p.status === 'new' && <span className="new-dot"></span>}
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* ─── Header ─── */}
      <div className="report-header flex justify-between items-start">
        <div>
          <span className="text-secondary text-xs font-semibold tracking-wider flex items-center gap-2">
            <Shield size={12} className="text-accent-light" />
            PORTFOLIO OPTIMIZATION
          </span>
          <h1 className="mt-2 mb-1">포트폴리오 개선 효과</h1>
          <p className="text-secondary text-xs">마지막 업데이트: {lastUpdated}</p>
        </div>
        <div className="flex gap-3">
          <Button variant="secondary" onClick={handleRefresh}><RefreshCw size={14}/> 새로고침</Button>
          <Button variant="secondary" onClick={handleDownload}><Download size={14}/> CSV 다운로드</Button>
        </div>
      </div>

      {/* Metric Toggle Tabs */}
      <div className="metric-tabs flex gap-2 mt-6">
        {['cvar', 'mdd', 'sharpe'].map(m => (
          <button
            key={m}
            className={`metric-tab ${selectedMetric === m ? 'active' : ''}`}
            onClick={() => setSelectedMetric(m)}
          >
            {metricLabels[m]}
          </button>
        ))}
      </div>

      {portfolioData && (
        <>
          {/* Metric Cards Row */}
          <div className="metric-cards flex gap-4 mt-6">
            {/* Base */}
            <div className={`metric-card clickable ${expandedCard === 'base' ? 'expanded' : ''}`} onClick={() => setExpandedCard(expandedCard === 'base' ? null : 'base')}>
              <div className="flex justify-between items-center mb-6">
                <h3 className="font-semibold text-secondary">기존 포트폴리오</h3>
                <span className="badge-dark">BASE</span>
              </div>
              <div className="metric-row">
                <span>CVaR</span>
                <div className="text-right">
                  <div className="font-semibold text-lg">{portfolioData.base.cvar}</div>
                  <div className="text-xs text-secondary">0.00% 개선</div>
                </div>
              </div>
              <div className="metric-row mt-4">
                <span>MDD</span>
                <div className="text-right">
                  <div className="font-semibold text-lg">{portfolioData.base.mdd}</div>
                  <div className="text-xs text-secondary">0.00% 개선</div>
                </div>
              </div>
              <div className="metric-row mt-4">
                <span>Sharpe</span>
                <div className="text-right">
                  <div className="font-semibold text-lg">{portfolioData.base.sharpe}</div>
                  <div className="text-xs text-secondary">0.00% 개선</div>
                </div>
              </div>
              {expandedCard === 'base' && selectedPortfolio && (
                <div className="detail-panel mt-4">
                  <div className="text-xs text-secondary mb-2">구성 종목</div>
                  <div className="text-sm">
                    {selectedPortfolio.assets.map(a => `${a.ticker} (${a.weight}%)`).join(', ')}
                  </div>
                  <div className="text-xs text-secondary mt-3 mb-2">총 투자금액</div>
                  <div className="text-sm">₩{selectedPortfolio.totalValue.toLocaleString()}</div>
                </div>
              )}
              <div className="expand-indicator mt-2">
                {expandedCard === 'base' ? <ChevronUp size={14}/> : <ChevronDown size={14}/>}
              </div>
            </div>

            {/* Recommended */}
            <div className={`metric-card clickable ${expandedCard === 'recommended' ? 'expanded' : ''}`} onClick={() => setExpandedCard(expandedCard === 'recommended' ? null : 'recommended')}>
              <div className="flex justify-between items-center mb-6">
                <h3 className="font-semibold text-primary">제안(1:1) - 단기국채 ETF</h3>
                <span className="badge-purple">RECOMMENDED</span>
              </div>
              <div className="metric-row">
                <span>CVaR</span>
                <div className="text-right">
                  <div className="font-semibold text-lg text-accent-light">{portfolioData.recommended.cvar}</div>
                  <div className="text-xs text-accent-light">↑ {Math.abs(calcImprove(portfolioData.base.cvar, portfolioData.recommended.cvar)).toFixed(2)}% 개선</div>
                </div>
              </div>
              <div className="metric-row mt-4">
                <span>MDD</span>
                <div className="text-right">
                  <div className="font-semibold text-lg text-accent-light">{portfolioData.recommended.mdd}</div>
                  <div className="text-xs text-accent-light">↑ {Math.abs(calcImprove(portfolioData.base.mdd, portfolioData.recommended.mdd)).toFixed(2)}% 개선</div>
                </div>
              </div>
              <div className="metric-row mt-4">
                <span>Sharpe</span>
                <div className="text-right">
                  <div className="font-semibold text-lg">{portfolioData.recommended.sharpe}</div>
                  <div className="text-xs text-accent-light">↑ {(((portfolioData.recommended.sharpe - portfolioData.base.sharpe) / Math.abs(portfolioData.base.sharpe)) * 100).toFixed(2)}% 개선</div>
                </div>
              </div>
              {expandedCard === 'recommended' && (
                <div className="detail-panel mt-4">
                  <div className="text-xs text-secondary mb-2">헷지 자산</div>
                  <div className="text-sm">SHY (단기국채 ETF) 50% 비중</div>
                  <div className="text-xs text-secondary mt-3 mb-2">예상 MDD 감소</div>
                  <div className="text-sm text-accent-light">{Math.abs(calcImprove(portfolioData.base.mdd, portfolioData.recommended.mdd)).toFixed(2)}%</div>
                </div>
              )}
              <div className="expand-indicator mt-2">
                {expandedCard === 'recommended' ? <ChevronUp size={14}/> : <ChevronDown size={14}/>}
              </div>
            </div>

            {/* Optimized */}
            <div className={`metric-card highlight clickable ${expandedCard === 'optimized' ? 'expanded' : ''}`} onClick={() => setExpandedCard(expandedCard === 'optimized' ? null : 'optimized')}>
              <div className="flex justify-between items-center mb-6">
                <h3 className="font-semibold text-primary">제안(다자산) - 금 ETF(IAU) + 단기국채 ETF</h3>
                <span className="badge-blue">OPTIMIZED</span>
              </div>
              <div className="metric-row">
                <span>CVaR</span>
                <div className="text-right">
                  <div className="font-semibold text-lg text-blue">{portfolioData.optimized.cvar}</div>
                  <div className="text-xs text-blue">↑ {Math.abs(calcImprove(portfolioData.base.cvar, portfolioData.optimized.cvar)).toFixed(2)}% 개선</div>
                </div>
              </div>
              <div className="metric-row mt-4">
                <span>MDD</span>
                <div className="text-right">
                  <div className="font-semibold text-lg text-blue">{portfolioData.optimized.mdd}</div>
                  <div className="text-xs text-blue">↑ {Math.abs(calcImprove(portfolioData.base.mdd, portfolioData.optimized.mdd)).toFixed(2)}% 개선</div>
                </div>
              </div>
              <div className="metric-row mt-4">
                <span>Sharpe</span>
                <div className="text-right">
                  <div className="font-semibold text-lg text-blue">{portfolioData.optimized.sharpe}</div>
                  <div className="text-xs text-blue">↑ {(((portfolioData.optimized.sharpe - portfolioData.base.sharpe) / Math.abs(portfolioData.base.sharpe)) * 100).toFixed(2)}% 개선</div>
                </div>
              </div>
              {expandedCard === 'optimized' && (
                <div className="detail-panel mt-4">
                  <div className="text-xs text-secondary mb-2">헷지 자산</div>
                  <div className="text-sm">IAU (금 ETF) 25% + SHY (단기국채) 25%</div>
                  <div className="text-xs text-secondary mt-3 mb-2">최적 비중</div>
                  <div className="text-sm text-blue">원자산 50% · 금 25% · 국채 25%</div>
                </div>
              )}
              <div className="expand-indicator mt-2">
                {expandedCard === 'optimized' ? <ChevronUp size={14}/> : <ChevronDown size={14}/>}
              </div>
            </div>
          </div>

          {/* CVaR Comparison Chart */}
          <div className="chart-card mt-6">
            <div className="flex justify-between items-center mb-6">
              <div>
                <h3 className="font-semibold">{metricLabels[selectedMetric]} 비교</h3>
                <p className="text-xs text-secondary mt-1">리스크 관리 효율성 비교 (낮을수록 우수)</p>
              </div>
              <div className="flex gap-4 text-xs text-secondary">
                <span className="flex items-center gap-1"><span className="dot dot-dark"></span> 기존</span>
                <span className="flex items-center gap-1"><span className="dot dot-purple"></span> 제안(1:1)</span>
                <span className="flex items-center gap-1"><span className="dot dot-blue"></span> 제안(다자산)</span>
              </div>
            </div>

            <div className="bar-row">
              <div className="flex justify-between text-xs text-secondary mb-2">
                <span>기존 포트폴리오</span>
                <span>{portfolioData.base[selectedMetric]}</span>
              </div>
              <div className="bar-container"><div className="bar bar-dark" style={{width: animateBars ? `${getBarWidth('base')}%` : '0%'}}></div></div>
            </div>

            <div className="bar-row mt-6">
              <div className="flex justify-between text-xs text-accent-light mb-2">
                <span>제안(1:1) - 단기국채 ETF</span>
                <span>{portfolioData.recommended[selectedMetric]} ({getImproveText('recommended')})</span>
              </div>
              <div className="bar-container"><div className="bar bar-purple" style={{width: animateBars ? `${getBarWidth('recommended')}%` : '0%'}}></div></div>
            </div>

            <div className="bar-row mt-6">
              <div className="flex justify-between text-xs text-blue mb-2">
                <span>제안(다자산) - 금 ETF(IAU) + 단기국채 ETF</span>
                <span>{portfolioData.optimized[selectedMetric]} ({getImproveText('optimized')})</span>
              </div>
              <div className="bar-container"><div className="bar bar-blue" style={{width: animateBars ? `${getBarWidth('optimized')}%` : '0%'}}></div></div>
            </div>
          </div>

          {/* Bottom info section */}
          <div className="info-cards flex gap-4 mt-6">
            <div className="info-card flex gap-4 items-center">
              <div className="icon-box purple-bg"><Shield size={20} className="text-accent-light"/></div>
              <div>
                <h4 className="font-semibold text-sm">리스크 방어력 강화</h4>
                <p className="text-xs text-secondary mt-1">다자산 배분 전략을 통해 시장 변동성(CVaR)을 최대 {Math.abs(calcImprove(portfolioData.base.cvar, portfolioData.optimized.cvar)).toFixed(2)}% 낮추었으며, 최악의 하락 폭(MDD)을 {Math.abs(calcImprove(portfolioData.base.mdd, portfolioData.optimized.mdd)).toFixed(2)}% 개선했습니다.</p>
              </div>
            </div>
            <div className="info-card flex gap-4 items-center">
              <div className="icon-box blue-bg"><Rocket size={20} className="text-blue"/></div>
              <div>
                <h4 className="font-semibold text-sm">투자 효율성 증대</h4>
                <p className="text-xs text-secondary mt-1">단순 리스크 감소를 넘어 샤프 지수(Sharpe)를 {(((portfolioData.optimized.sharpe - portfolioData.base.sharpe) / Math.abs(portfolioData.base.sharpe)) * 100).toFixed(2)}% 향상시켜, 위험 대비 수익률을 최적화한 결과를 도출했습니다.</p>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
};
