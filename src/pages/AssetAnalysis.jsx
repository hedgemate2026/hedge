import React, { useState, useEffect } from 'react';
import { Search, BarChart2, Globe, Shield, Zap, TrendingUp, AlertCircle, Loader2, ArrowRight } from 'lucide-react';
import { Button } from '../components/Button';
import { useNavigate, useSearchParams } from 'react-router-dom';
import './AssetAnalysis.css';

const ASSET_DB = {
  'AAPL':  { name: 'Apple Inc.',       price: 178.72, riskVol: 14.2, correlation: 'Moderate Positive', alpha: 0.91, beta: 1.05, confidence: 96, hedgeAsset: 'SHY (단기국채 ETF)', mddReduction: 18.4 },
  'NVDA':  { name: 'NVIDIA Corp.',      price: 875.28, riskVol: 28.7, correlation: 'Strong Positive',  alpha: 1.42, beta: 1.68, confidence: 88, hedgeAsset: 'GLD (금 ETF)',       mddReduction: 22.1 },
  'MSFT':  { name: 'Microsoft Corp.',   price: 415.50, riskVol: 12.8, correlation: 'Moderate Positive', alpha: 0.78, beta: 0.95, confidence: 97, hedgeAsset: 'SHY (단기국채 ETF)', mddReduction: 15.2 },
  'TSLA':  { name: 'Tesla Inc.',        price: 171.05, riskVol: 42.3, correlation: 'Strong Positive',  alpha: 0.34, beta: 1.92, confidence: 72, hedgeAsset: 'SQQQ (인버스 ETF)',  mddReduction: 31.5 },
  'BTC':   { name: 'Bitcoin',           price: 67420,  riskVol: 58.1, correlation: 'Weak Positive',    alpha: 0.55, beta: 2.15, confidence: 65, hedgeAsset: 'GLD (금 ETF)',       mddReduction: 28.9 },
  'GOOGL': { name: 'Alphabet Inc.',     price: 141.80, riskVol: 16.5, correlation: 'Moderate Positive', alpha: 0.82, beta: 1.12, confidence: 94, hedgeAsset: 'SHY (단기국채 ETF)', mddReduction: 17.3 },
  'AMZN':  { name: 'Amazon.com Inc.',   price: 178.15, riskVol: 19.4, correlation: 'Strong Positive',  alpha: 0.67, beta: 1.22, confidence: 91, hedgeAsset: 'TLT (장기국채 ETF)', mddReduction: 20.8 },
  'META':  { name: 'Meta Platforms',    price: 485.58, riskVol: 24.1, correlation: 'Strong Positive',  alpha: 1.15, beta: 1.35, confidence: 89, hedgeAsset: 'GLD (금 ETF)',       mddReduction: 19.7 },
  'JPM':   { name: 'JPMorgan Chase',    price: 196.20, riskVol: 15.8, correlation: 'Moderate Positive', alpha: 0.45, beta: 1.08, confidence: 93, hedgeAsset: 'SHY (단기국채 ETF)', mddReduction: 14.6 },
  'SPY':   { name: 'S&P 500 Index',     price: 502.10, riskVol: 12.4, correlation: 'Strong Positive',  alpha: 0.84, beta: 1.12, confidence: 94, hedgeAsset: 'SHY (단기국채 ETF)', mddReduction: 16.2 },
};

const HISTORY_INIT = [];

const generateAssetData = (ticker) => {
  if (ASSET_DB[ticker]) return ASSET_DB[ticker];

  // Pseudo-random generation based on ticker string for consistent results
  let hash = 0;
  for (let i = 0; i < ticker.length; i++) {
    hash = ticker.charCodeAt(i) + ((hash << 5) - hash);
  }
  
  const rand1 = Math.abs(hash % 100);
  const rand2 = Math.abs((hash >> 4) % 100);
  
  // Decide fundamental risk metrics
  const beta = 0.5 + (rand1 / 100) * 2; // 0.5 to 2.5
  const riskVol = 10 + ((rand1 + rand2) % 100) / 100 * 50; // 10% to 60%
  const alpha = -0.3 + (rand2 / 100) * 1.5; // -0.3 to 1.2
  const confidence = 65 + (rand1 % 25); // 65% to 90%

  let correlation = 'Moderate Positive';
  if (rand1 > 80) correlation = 'Strong Positive';
  else if (rand1 < 20) correlation = 'Weak Positive';
  else if (rand1 % 7 === 0) correlation = 'Negative';

  // Rule-based engine logic for predicting Hedge Asset & MDD Reduction
  let hedgeAsset = '';
  let mddReduction = 0;

  if (beta > 1.6 && riskVol > 35) {
    hedgeAsset = rand1 % 2 === 0 ? 'SQQQ (인버스 ETF)' : 'VIXY (변동성 지수 ETF)';
    mddReduction = 25 + (rand1 % 10);
  } else if (beta > 1.2 && riskVol > 20) {
    hedgeAsset = rand2 % 2 === 0 ? 'GLD (금 ETF)' : 'TLT (초장기국채 ETF)';
    mddReduction = 15 + (rand2 % 8);
  } else if (beta < 1.0) {
    hedgeAsset = 'SHY (단기국채 ETF)';
    mddReduction = 8 + (rand1 % 5);
  } else {
    hedgeAsset = 'BIL (초단기채 ETF)';
    mddReduction = 5 + (rand2 % 5);
  }

  return {
    name: `${ticker} Asset (AI Calc)`,
    price: 50 + (rand1 * 2.5),
    riskVol: parseFloat(riskVol.toFixed(1)),
    correlation,
    alpha: parseFloat(alpha.toFixed(2)),
    beta: parseFloat(beta.toFixed(2)),
    confidence,
    hedgeAsset,
    mddReduction: parseFloat(mddReduction.toFixed(1))
  };
};

export const AssetAnalysis = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const queryParam = searchParams.get('q');

  const [searchQuery, setSearchQuery] = useState(queryParam || '');
  const [holdingAmount, setHoldingAmount] = useState(10000000);
  const [hedgeBudget, setHedgeBudget] = useState(5000000);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [result, setResult] = useState(null);
  const [history, setHistory] = useState(HISTORY_INIT);
  const [suggestions, setSuggestions] = useState([]);

  const handleSearchChange = (e) => {
    const val = e.target.value;
    setSearchQuery(val);
    if (val.length >= 1) {
      const matches = Object.entries(ASSET_DB)
        .filter(([ticker, data]) => 
          ticker.toLowerCase().includes(val.toLowerCase()) || 
          data.name.toLowerCase().includes(val.toLowerCase())
        )
        .slice(0, 5);
      setSuggestions(matches);
    } else {
      setSuggestions([]);
    }
  };

  const selectSuggestion = (ticker) => {
    setSearchQuery(ticker);
    setSuggestions([]);
  };

  const runAnalysis = (overrideTicker) => {
    const term = typeof overrideTicker === 'string' ? overrideTicker : searchQuery;
    const ticker = term.toUpperCase().trim();
    if (!ticker) return;

    const asset = generateAssetData(ticker);

    setIsAnalyzing(true);
    setResult(null);
    setTimeout(() => {
      setResult({ ticker, ...asset });
      setIsAnalyzing(false);
      // Add to history
      setHistory(prev => [
        { ticker, name: asset.name, time: '방금 전', type: asset.riskVol > 25 ? 'warning' : 'up' },
        ...prev.filter(h => h.ticker !== ticker).slice(0, 4),
      ]);
    }, 1500);
  };

  useEffect(() => {
    if (queryParam) {
      setSearchQuery(queryParam);
      runAnalysis(queryParam);
    }
  }, [queryParam]);

  const handleHistoryClick = (ticker) => {
    setSearchQuery(ticker);
    setTimeout(() => {
      const asset = generateAssetData(ticker);
      if (asset) {
        setResult({ ticker, ...asset });
      }
    }, 200);
  };

  const getRiskLevel = (vol) => {
    if (vol > 40) return { label: 'Very High Risk', color: '#ef4444' };
    if (vol > 25) return { label: 'High Risk', color: '#f59e0b' };
    if (vol > 15) return { label: 'Moderate Risk', color: '#c084fc' };
    return { label: 'Low Risk', color: '#059669' };
  };

  return (
    <div className="analysis-page">
      <div className="report-header mb-6">
        <span className="text-secondary text-xs font-semibold tracking-wider flex items-center gap-2">
          <span className="badge-purple">ENGINE V2.4</span>
          • Real-time Risk Analysis
        </span>
        <h1 className="mt-2 mb-2">단일 자산 분석 실행</h1>
        <p className="text-secondary text-sm">시장의 변동성으로부터 자산을 보호하세요. HedgeMate의 인공지능 알고리즘이 실시간 시장 데이터를 기반으로 최적의 헷지 전략을 계산합니다.</p>
      </div>

      <div className="analysis-grid">
        {/* Left Column */}
        <div className="flex-col gap-6">
          <div className="card-box">
            <div className="card-header mb-6">
              <span className="icon-wrapper"><BarChart2 size={16}/></span>
              <span className="font-semibold">분석 파라미터 설정</span>
            </div>
            
            <div className="form-group" style={{position:'relative'}}>
              <label>종목 / 자산 검색</label>
              <div className="search-input-wrapper">
                <Search size={16} className="text-secondary" />
                <input 
                  type="text" 
                  placeholder="예: AAPL, BTC, TSLA..." 
                  value={searchQuery}
                  onChange={handleSearchChange}
                  onKeyDown={(e) => e.key === 'Enter' && runAnalysis()}
                />
              </div>
              {suggestions.length > 0 && (
                <div className="suggestions-dropdown">
                  {suggestions.map(([ticker, data]) => (
                    <div key={ticker} className="suggestion-item" onClick={() => selectSuggestion(ticker)}>
                      <span className="font-semibold">{ticker}</span>
                      <span className="text-secondary text-xs">{data.name}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="flex gap-4 mt-6">
              <div className="form-group flex-1">
                <label>보유 금액 (KRW)</label>
                <div className="input-with-symbol">
                  <span>₩</span>
                  <input 
                    type="text" 
                    value={holdingAmount.toLocaleString()}
                    onChange={(e) => setHoldingAmount(parseInt(e.target.value.replace(/,/g, '')) || 0)}
                  />
                </div>
              </div>
              <div className="form-group flex-1">
                <label>헷지 예산 (KRW)</label>
                <div className="input-with-symbol">
                  <span>₩</span>
                  <input 
                    type="text" 
                    value={hedgeBudget.toLocaleString()}
                    onChange={(e) => setHedgeBudget(parseInt(e.target.value.replace(/,/g, '')) || 0)}
                  />
                </div>
              </div>
            </div>

            <Button variant="primary" className="w-full mt-6 py-3" onClick={runAnalysis} disabled={isAnalyzing}>
              {isAnalyzing ? (
                <><Loader2 size={16} className="spin-icon" /> 분석 중...</>
              ) : (
                <>단일 자산 분석 실행 <ArrowRight size={16}/></>
              )}
            </Button>
          </div>

          <div className="history-list mt-6">
            <div className="flex justify-between items-center mb-4">
              <span className="text-sm font-semibold text-secondary">최근 분석 이력</span>
              <button className="text-xs text-accent-light" onClick={() => setHistory([])}>초기화</button>
            </div>
            
            {history.length === 0 ? (
              <div className="text-xs text-secondary text-center" style={{padding:'2rem'}}>분석 이력이 없습니다</div>
            ) : (
              history.map((item, i) => (
                <div className="history-item" key={`${item.ticker}-${i}`} style={{marginTop: i > 0 ? '0.75rem' : 0}} onClick={() => handleHistoryClick(item.ticker)}>
                  <div className={`history-icon ${item.type === 'warning' ? 'bg-orange-dim' : 'bg-blue-dim'}`}>
                    {item.type === 'warning' ? <AlertCircle size={16} className="text-warning"/> : <TrendingUp size={16} className="text-blue"/>}
                  </div>
                  <div className="flex-1">
                    <div className="text-sm font-medium">{item.name}</div>
                    <div className="text-xs text-secondary">{item.time}</div>
                  </div>
                  <span className="text-secondary">&gt;</span>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Right Column */}
        <div className="card-box right-col">
          <div className="card-header justify-between mb-6">
            <div className="flex items-center gap-2">
              <span className="icon-wrapper bg-dark"><Globe size={16}/></span>
              <span className="font-semibold">실시간 시장 강도</span>
            </div>
            <div className="flex gap-2 text-xs text-secondary">
              <span className="badge-dark">US</span>
              <span className="badge-dark">EU</span>
              <span className="badge-dark">KR</span>
              <span className="flex items-center gap-1"><span className="dot dot-purple"></span> LIVE FEEDS CONNECTED</span>
            </div>
          </div>

          {result ? (
            <>
              <div className="market-stats flex justify-between mt-4 mb-6">
                <div>
                  <div className="text-xs font-semibold tracking-wider mb-1" style={{color: getRiskLevel(result.riskVol).color}}>RISK VOLATILITY</div>
                  <div className="text-4xl font-bold">{result.riskVol}%</div>
                  <div className="text-xs mt-1" style={{color: getRiskLevel(result.riskVol).color}}>~ {getRiskLevel(result.riskVol).label}</div>
                </div>
                <div className="text-right">
                  <div className="text-xs text-secondary font-semibold tracking-wider mb-1">GLOBAL CORRELATION</div>
                  <div className="text-lg font-medium">{result.correlation}</div>
                </div>
              </div>

              <div className="map-placeholder">
                <div className="progress-bar mb-10">
                  <div className="progress-fill" style={{width: `${result.riskVol}%`}}></div>
                </div>
                
                <div className="signal-cards flex gap-4">
                  <div className="signal-card">
                    <div className="text-xs text-secondary mb-2">ALPHA SIGNAL</div>
                    <div className="text-xl font-bold text-accent-light">{result.alpha}</div>
                  </div>
                  <div className="signal-card">
                    <div className="text-xs text-secondary mb-2">BETA EXPOSURE</div>
                    <div className="text-xl font-bold">{result.beta}</div>
                  </div>
                  <div className="signal-card">
                    <div className="text-xs text-secondary mb-2">CONFIDENCE</div>
                    <div className="text-xl font-bold text-accent-light">{result.confidence}%</div>
                  </div>
                </div>
              </div>

              {/* Hedge Recommendation Result */}
              <div className="hedge-result mt-6">
                <h4 className="font-semibold text-sm mb-3 text-accent-light">🛡️ 추천 헷지 전략</h4>
                <div className="flex justify-between text-sm mb-2">
                  <span className="text-secondary">추천 자산</span>
                  <span className="font-medium">{result.hedgeAsset}</span>
                </div>
                <div className="flex justify-between text-sm mb-2">
                  <span className="text-secondary">예상 MDD 감소</span>
                  <span className="font-medium text-accent-light">-{result.mddReduction}%</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-secondary">헷지 비용</span>
                  <span className="font-medium">₩{hedgeBudget.toLocaleString()}</span>
                </div>
                <Button variant="primary" className="w-full mt-4" onClick={() => navigate('/report')}>
                  상세 리포트 보기 →
                </Button>
              </div>
            </>
          ) : isAnalyzing ? (
            <div className="analyzing-state">
              <Loader2 size={48} className="spin-icon text-accent-light" />
              <p className="text-sm text-secondary mt-4">시장 데이터를 분석하고 있습니다...</p>
              <p className="text-xs text-secondary mt-1">약 1~2초 소요됩니다</p>
            </div>
          ) : (
            <>
              <div className="market-stats flex justify-between mt-8 mb-8">
                <div>
                  <div className="text-xs text-accent-light font-semibold tracking-wider mb-1">RISK VOLATILITY</div>
                  <div className="text-4xl font-bold">—</div>
                  <div className="text-xs text-secondary mt-1">종목을 검색하여 분석을 시작하세요</div>
                </div>
                <div className="text-right">
                  <div className="text-xs text-secondary font-semibold tracking-wider mb-1">GLOBAL CORRELATION</div>
                  <div className="text-lg font-medium text-secondary">—</div>
                </div>
              </div>

              <div className="map-placeholder">
                <div className="progress-bar mb-10"><div className="progress-fill" style={{width:'0%'}}></div></div>
                <div className="signal-cards flex gap-4">
                  <div className="signal-card"><div className="text-xs text-secondary mb-2">ALPHA SIGNAL</div><div className="text-xl font-bold text-secondary">—</div></div>
                  <div className="signal-card"><div className="text-xs text-secondary mb-2">BETA EXPOSURE</div><div className="text-xl font-bold text-secondary">—</div></div>
                  <div className="signal-card"><div className="text-xs text-secondary mb-2">CONFIDENCE</div><div className="text-xl font-bold text-secondary">—</div></div>
                </div>
              </div>
            </>
          )}

          <div className="bottom-badges flex gap-4 mt-8">
            <div className="badge-info flex-1 flex gap-3">
              <Zap size={20} className="text-accent-light"/>
              <div>
                <div className="text-sm font-semibold">AI 기반 위험 관리</div>
                <div className="text-xs text-secondary mt-1">과거의 위기 시나리오 100만 건을 학습한 모델이 귀하의 자산을 보호합니다.</div>
              </div>
            </div>
            <div className="badge-info flex-1 flex gap-3">
              <Shield size={20} className="text-blue"/>
              <div>
                <div className="text-sm font-semibold">규제 준수 엔진</div>
                <div className="text-xs text-secondary mt-1">최신 금융 규제 및 파생상품 한도를 자동으로 계산하여 추천합니다.</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
