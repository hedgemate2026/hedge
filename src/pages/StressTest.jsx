import React, { useState, useEffect, useCallback } from 'react';
import { Zap, Briefcase, AlertTriangle, TrendingDown, TrendingUp, Shield, ChevronDown, ChevronUp, Activity, Globe, Flame, Landmark, Bug, Wheat, ArrowRight } from 'lucide-react';
import { Button } from '../components/Button';
import { useNavigate } from 'react-router-dom';
import { usePortfolios } from '../context/PortfolioContext';
import { getTickerHistory } from '../services/yahooFinance';
import { runMacroScenarioSimulation } from '../services/simulation';
import './StressTest.css';

const QUICK_SCENARIOS = [
  { id: 'default', name: '기본', rate: 0, fx: 0, oil: 0, icon: <Activity size={16}/> },
  { id: 'rate', name: '금리 급등 (+200bp)', rate: 200, fx: 0, oil: 0, icon: <TrendingUp size={16}/> },
  { id: 'fx', name: '원화 약세 (+20%)', rate: 0, fx: 20, oil: 0, icon: <Globe size={16}/> },
  { id: 'oil', name: '유가 급등 (+60%)', rate: 0, fx: 0, oil: 60, icon: <Flame size={16}/> },
  { id: 'shock', name: '복합 충격', rate: 150, fx: 15, oil: 40, icon: <Zap size={16}/> },
  { id: 'deflation', name: '디플레이션', rate: -100, fx: -5, oil: -30, icon: <Landmark size={16}/> },
];

export const StressTest = () => {
  const navigate = useNavigate();
  const { portfolios } = usePortfolios();

  const [selectedPortfolioId, setSelectedPortfolioId] = useState(null);
  const [rateShock, setRateShock] = useState(0);
  const [fxShock, setFxShock] = useState(0);
  const [oilShock, setOilShock] = useState(0);
  const [activeScenario, setActiveScenario] = useState('default');
  
  const [simulationResult, setSimulationResult] = useState(null);
  const [isSimulating, setIsSimulating] = useState(false);
  const [errorInfo, setErrorInfo] = useState(null);

  const selectedPortfolio = portfolios.find(p => p.id === selectedPortfolioId);

  useEffect(() => {
    if (!selectedPortfolioId && portfolios.length > 0) {
      setSelectedPortfolioId(portfolios[0].id);
    }
  }, [portfolios, selectedPortfolioId]);

  // Real-time simulation logic
  const runSimulation = useCallback(async (shocks) => {
    if (!selectedPortfolio) return;

    setIsSimulating(true);
    try {
      const assetHistories = await Promise.all(
        selectedPortfolio.assets.map(a => getTickerHistory(a.ticker))
      );
      const macroProxies = ['^IRX', 'KRW=X', 'CL=F'];
      const macroHistories = await Promise.all(macroProxies.map(p => getTickerHistory(p)));

      const validAssets = assetHistories.filter(h => h && h.returns.length > 0);
      const failedAssets = selectedPortfolio.assets.filter((a, i) => !assetHistories[i] || assetHistories[i].returns.length === 0);
      const validMacros = macroHistories.filter(h => h && h.returns.length > 0);

      if (failedAssets.length > 0) {
        setErrorInfo({
          type: 'partial_data',
          message: `일부 종목의 데이터를 불러오지 못했습니다: ${failedAssets.map(a => a.ticker).join(', ')}`,
          suggestion: '티커 기호가 정확한지 확인해주세요 (예: TESLA -> TSLA).'
        });
        if (validAssets.length === 0) {
          setSimulationResult(null);
          return;
        }
      } else {
        setErrorInfo(null);
      }

      if (validAssets.length === 0 || validMacros.length < 3) {
        setSimulationResult(null);
        return;
      }

      const minLen = Math.min(
        ...validAssets.map(h => h.returns.length),
        ...validMacros.map(h => h.returns.length)
      );

      const returnsMatrix = validAssets.map(h => h.returns.slice(-minLen));
      const macroReturnsMatrix = validMacros.map(h => h.returns.slice(-minLen));
      
      const validTickers = validAssets.map(h => h.ticker);
      const filteredAssets = selectedPortfolio.assets.filter(a => validTickers.includes(a.ticker));
      const subTotal = filteredAssets.reduce((sum, a) => sum + (a.qty * a.cost), 0);
      const weights = filteredAssets.map(a => (a.qty * a.cost) / subTotal);

      const mcResult = runMacroScenarioSimulation(
        returnsMatrix,
        macroReturnsMatrix,
        shocks,
        { weights }
      );

      setSimulationResult({
        ...mcResult,
        totalLoss: Math.round(selectedPortfolio.totalValue * mcResult.cvar),
        totalAfter: Math.round(selectedPortfolio.totalValue * (1 + mcResult.cvar)),
        totalImpactPct: parseFloat((mcResult.cvar * 100).toFixed(2)),
        assetDetails: filteredAssets.map((a, i) => ({
          ticker: a.ticker,
          name: a.name,
          impact: parseFloat((mcResult.assetExpectations[i] * 100).toFixed(1)),
          lossAmount: Math.round(selectedPortfolio.totalValue * (a.qty * a.cost / selectedPortfolio.totalValue) * mcResult.assetExpectations[i])
        }))
      });
    } catch (error) {
      console.error('Simulation failed:', error);
      setErrorInfo({ type: 'error', message: '시뮬레이션 중 오류가 발생했습니다.' });
    } finally {
      setIsSimulating(false);
    }
  }, [selectedPortfolio]);

  // Debounce simulation on slider change
  useEffect(() => {
    if (!selectedPortfolio) return;
    const timer = setTimeout(() => {
      runSimulation({ rate: rateShock, fx: fxShock, oil: oilShock });
    }, 400);
    return () => clearTimeout(timer);
  }, [rateShock, fxShock, oilShock, selectedPortfolio, runSimulation]);

  const applyQuickScenario = (s) => {
    setActiveScenario(s.id);
    setRateShock(s.rate);
    setFxShock(s.fx);
    setOilShock(s.oil);
  };

  if (portfolios.length === 0) {
    return (
      <div className="stress-test-page">
        <div className="empty-state">
          <div className="empty-icon"><Briefcase size={32} /></div>
          <h2>포트폴리오가 없습니다</h2>
          <p>분석을 시작하려면 먼저 자산을 등록해주세요.</p>
          <Button variant="primary" onClick={() => navigate('/register')} style={{marginTop:'1.5rem'}}>
            포트폴리오 등록 <ArrowRight size={14} />
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="stress-test-page">
      {/* Portfolio Selection */}
      <div className="portfolio-select-card mb-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="icon-wrapper"><Briefcase size={18} className="text-accent-light" /></div>
            <div>
              <h3 className="text-sm font-semibold mb-0">분석 대상 포트폴리오 선택</h3>
              <p className="text-xs text-secondary mt-1">시뮬레이션을 진행할 포트폴리오를 선택하세요.</p>
            </div>
          </div>
          <div className="select-wrapper">
            <select 
              value={selectedPortfolioId || ''} 
              onChange={(e) => {
                setSelectedPortfolioId(e.target.value);
                setSimulationResult(null);
                setErrorInfo(null);
              }}
              className="portfolio-dropdown"
            >
              {portfolios.map(p => (
                <option key={p.id} value={p.id}>{p.name} ({p.assets.length}종목)</option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Top Banner */}
      <div className="analysis-target-banner">
        <div className="target-info">
          <div className="target-icon-box"><Activity size={20}/></div>
          <div className="target-text">
            <h4>현재 분석 대상</h4>
            <p>{selectedPortfolio?.name} · {selectedPortfolio?.assets.length}개 자산 기준으로 시나리오를 분석합니다.</p>
          </div>
        </div>
        <div className="target-assets">
          {selectedPortfolio?.assets.slice(0, 3).map(a => (
            <div key={a.ticker} className="asset-pill">
              {a.ticker} {((a.qty * a.cost / selectedPortfolio.totalValue) * 100).toFixed(1)}%
            </div>
          ))}
          {selectedPortfolio?.assets.length > 3 && (
            <div className="asset-pill">+{selectedPortfolio.assets.length - 3} More</div>
          )}
        </div>
      </div>

      <div className="macro-simulation-card">
        <span className="mc-badge">Macro Monte Carlo Simulation</span>
        <h1 className="mc-title">거시경제 변수별 리스크 지표 분석</h1>
        <p className="mc-desc">금리·환율·유가 충격 수준을 조정하면 시뮬레이션을 통해 지표 변화를 확인합니다.</p>

        {/* Quick Scenarios */}
        <div className="quick-scenarios">
          {QUICK_SCENARIOS.map(s => (
            <button
              key={s.id}
              className={`scenario-btn ${activeScenario === s.id ? 'active' : ''}`}
              onClick={() => applyQuickScenario(s)}
            >
              {s.icon} {s.name}
            </button>
          ))}
        </div>

        {/* Controls */}
        <div className="macro-controls">
          <div className="control-group">
            <div className="control-header">
              <div className="control-label">
                <Activity size={18} className="control-icon" /> 금리 변화
              </div>
              <div className="control-value">{rateShock > 0 ? '+' : ''}{rateShock} bp</div>
            </div>
            <input 
              type="range" min="-100" max="300" step="25" 
              value={rateShock} onChange={(e) => {setRateShock(parseInt(e.target.value)); setActiveScenario(null);}} 
              className="mc-slider"
            />
            <div className="slider-marks">
              <span>-100bp</span>
              <span>0</span>
              <span>+100bp</span>
              <span>+200bp</span>
              <span>+300bp</span>
            </div>
          </div>

          <div className="control-group">
            <div className="control-header">
              <div className="control-label">
                <Globe size={18} className="control-icon" /> 환율 변화 (KRW/USD)
              </div>
              <div className="control-value">{fxShock > 0 ? '+' : ''}{fxShock}%</div>
            </div>
            <input 
              type="range" min="-10" max="20" step="1" 
              value={fxShock} onChange={(e) => {setFxShock(parseInt(e.target.value)); setActiveScenario(null);}} 
              className="mc-slider"
            />
            <div className="slider-marks">
              <span>-10%</span>
              <span>0</span>
              <span>+10%</span>
              <span>+20%</span>
            </div>
          </div>

          <div className="control-group">
            <div className="control-header">
              <div className="control-label">
                <Flame size={18} className="control-icon" /> 유가 변화 (WTI)
              </div>
              <div className="control-value">{oilShock > 0 ? '+' : ''}{oilShock}%</div>
            </div>
            <input 
              type="range" min="-30" max="60" step="5" 
              value={oilShock} onChange={(e) => {setOilShock(parseInt(e.target.value)); setActiveScenario(null);}} 
              className="mc-slider"
            />
            <div className="slider-marks">
              <span>-30%</span>
              <span>0</span>
              <span>+30%</span>
              <span>+60%</span>
            </div>
          </div>
        </div>

        {/* Error/Feedback Section */}
        {errorInfo && (
          <div className="simulation-error-alert mb-6">
            <div className="flex items-center gap-3">
              <AlertTriangle size={20} className="text-red" />
              <div className="flex-1">
                <div className="text-sm font-semibold text-red">{errorInfo.message}</div>
                {errorInfo.suggestion && <div className="text-xs text-secondary mt-1">{errorInfo.suggestion}</div>}
              </div>
            </div>
          </div>
        )}

        {/* Results */}
        {simulationResult && (
          <>
            <div className="simulation-results-overlay">
              <div className="metric-card critical">
                <span className="metric-label">예상 총 손실 (CVaR 95%)</span>
                <div className="metric-value">
                  ₩{Math.abs(simulationResult.totalLoss).toLocaleString()}
                </div>
                <div className="metric-sub">{simulationResult.totalImpactPct}% 자산 하락 예상</div>
              </div>

              <div className="metric-card">
                <span className="metric-label">Stressed MDD (낙폭 시뮬레이션)</span>
                <div className="metric-value">
                  {(simulationResult.mddApprox * 100).toFixed(1)}<span className="metric-unit">%</span>
                </div>
                <div className="metric-sub">위기 발생 시 최대 예상 하락폭</div>
              </div>

              <div className="metric-card">
                <span className="metric-label">위기 대응 지수 (MO-Sharpe)</span>
                <div className="metric-value">
                  {simulationResult.moSharpe.moSharpe.toFixed(2)}
                </div>
                <div className={`metric-sub status-${simulationResult.moSharpe.moSharpe > 0.8 ? 'excellent' : simulationResult.moSharpe.moSharpe > 0.4 ? 'stable' : 'weak'}`}>
                  상태: {simulationResult.moSharpe.moSharpe > 0.8 ? 'Excellent' : simulationResult.moSharpe.moSharpe > 0.4 ? 'Stable' : 'Weak'}
                </div>
              </div>
            </div>

            {/* Asset Breakdown Table */}
            <div className="asset-breakdown-card mt-6">
              <h3 className="text-sm font-semibold mb-4">종목별 위기 민감도 분석</h3>
              <div className="asset-table-wrapper">
                <table className="asset-impact-table">
                  <thead>
                    <tr>
                      <th>종목</th>
                      <th>현재 비중</th>
                      <th>시나리오 기대수익</th>
                      <th>예상 손익</th>
                    </tr>
                  </thead>
                  <tbody>
                    {simulationResult.assetDetails.map(asset => (
                      <tr key={asset.ticker}>
                        <td className="font-medium">{asset.ticker}</td>
                        <td className="text-secondary">{((selectedPortfolio.assets.find(a => a.ticker === asset.ticker).qty * selectedPortfolio.assets.find(a => a.ticker === asset.ticker).cost / selectedPortfolio.totalValue) * 100).toFixed(1)}%</td>
                        <td className={asset.impact >= 0 ? 'text-green' : 'text-red'}>
                          {asset.impact >= 0 ? '+' : ''}{asset.impact}%
                        </td>
                        <td className={asset.lossAmount >= 0 ? 'text-green' : 'text-red'}>
                          {asset.lossAmount >= 0 ? '+' : ''}₩{Math.abs(asset.lossAmount).toLocaleString()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </>
        )}

        {isSimulating && (
          <div className="simulation-loader">
            <div className="spinner"></div>
          </div>
        )}
      </div>
    </div>
  );
};
