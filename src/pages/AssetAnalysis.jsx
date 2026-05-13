import React, { useState, useEffect, useCallback } from 'react';
import { Search, BarChart2, Globe, Shield, Zap, TrendingUp, AlertCircle, Loader2, ArrowRight } from 'lucide-react';
import { Button } from '../components/Button';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { searchTickers, getTickerQuote } from '../services/yahooFinance';
import { debounce, ASSET_DATABASE, generateSimulatedMetrics } from '../utils/helpers';
import './AssetAnalysis.css';

const ASSET_DB = ASSET_DATABASE;

const HISTORY_INIT = [];

const generateAssetData = (ticker) => {
  const base = generateSimulatedMetrics(ticker);
  
  // Decide fundamental risk metrics (additional for Analysis page)
  let correlation = 'Moderate Positive';
  if (base.sp500Beta > 1.4) correlation = 'Strong Positive';
  else if (base.sp500Beta < 0.8) correlation = 'Weak Positive';
  
  const alpha = (base.score - 50) / 40;

  // Rule-based engine logic for predicting Hedge Asset & MDD Reduction
  let hedgeAsset = '';
  let mddReduction = 0;

  if (base.sp500Beta > 1.6 && base.riskVol > 35) {
    hedgeAsset = 'SQQQ (인버스 ETF)';
    mddReduction = 25 + (base.score % 10);
  } else if (base.sp500Beta > 1.2 && base.riskVol > 20) {
    hedgeAsset = 'GLD (금 ETF)';
    mddReduction = 15 + (base.score % 8);
  } else if (base.sp500Beta < 1.0) {
    hedgeAsset = 'SHY (단기국채 ETF)';
    mddReduction = 8 + (base.score % 5);
  } else {
    hedgeAsset = 'BIL (초단기채 ETF)';
    mddReduction = 5 + (base.score % 5);
  }

  return {
    ...base,
    correlation,
    alpha: parseFloat(alpha.toFixed(2)),
    beta: base.sp500Beta,
    confidence: base.score,
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

  // Debounced search function
  const debouncedSearch = useCallback(
    debounce(async (val) => {
      if (val.length >= 1) {
        // First, filter local DB for instant results
        const localMatches = Object.entries(ASSET_DB)
          .filter(([ticker, data]) => 
            ticker.toLowerCase().includes(val.toLowerCase()) || 
            data.name.toLowerCase().includes(val.toLowerCase())
          )
          .map(([ticker, data]) => ({
            ticker,
            name: data.name,
            source: 'local'
          }));

        // Then fetch from Yahoo Finance
        const remoteMatches = await searchTickers(val);
        
        // Combine and remove duplicates
        const combined = [...localMatches];
        remoteMatches.forEach(rm => {
          if (!combined.find(c => c.ticker === rm.ticker)) {
            combined.push({ ...rm, source: 'yahoo' });
          }
        });

        setSuggestions(combined.slice(0, 8));
      } else {
        setSuggestions([]);
      }
    }, 300),
    []
  );

  const handleSearchChange = (e) => {
    const val = e.target.value;
    setSearchQuery(val);
    debouncedSearch(val);
  };

  const selectSuggestion = (ticker) => {
    setSearchQuery(ticker);
    setSuggestions([]);
    
    // Use the generator to ensure all required properties are present
    const data = generateAssetData(ticker);
    setResult({ ticker, ...data });
  };

  const runAnalysis = async (overrideTicker) => {
    const term = typeof overrideTicker === 'string' ? overrideTicker : searchQuery;
    const ticker = term.toUpperCase().trim();
    if (!ticker) return;

    setIsAnalyzing(true);
    setResult(null);

    try {
      // Try to get real quote data
      const quote = await getTickerQuote(ticker);
      const asset = generateAssetData(ticker);

      // Merge real data with simulated risk metrics
      const finalAsset = {
        ...asset,
        name: quote?.name || asset.name,
        price: quote?.price || asset.price,
        realData: !!quote
      };

      setTimeout(() => {
        setResult({ ticker, ...finalAsset });
        setIsAnalyzing(false);
        // Add to history
        setHistory(prev => [
          { 
            ticker, 
            name: finalAsset.name, 
            time: '방금 전', 
            type: finalAsset.riskVol > 25 ? 'warning' : 'up',
            isReal: !!quote
          },
          ...prev.filter(h => h.ticker !== ticker).slice(0, 4),
        ]);
      }, 1000);
    } catch (error) {
      console.error('Analysis failed:', error);
      setIsAnalyzing(false);
    }
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
                  {suggestions.map((item) => (
                    <div key={item.ticker} className="suggestion-item" onClick={() => selectSuggestion(item.ticker)}>
                      <div className="flex flex-col">
                        <span className="font-semibold">{item.ticker}</span>
                        <span className="text-secondary text-xs truncate max-w-[200px]">{item.name}</span>
                      </div>
                      {item.source === 'yahoo' && <span className="yahoo-badge">Yahoo</span>}
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
