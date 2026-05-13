import React, { useState, useCallback } from 'react';
import { Activity, ShieldCheck, AlertTriangle, Info, Search, ChevronRight, Loader2 } from 'lucide-react';
import { searchTickers, getTickerQuote } from '../services/yahooFinance';
import { debounce, ASSET_DATABASE, generateSimulatedMetrics } from '../utils/helpers';
import './AssetSensitivity.css';

const STOCK_DB = ASSET_DATABASE;

const CORRELATION_DATA = {
  'KIA':      [[1.0, 0.35, 0.70, 0.25, 0.55], [0.35, 1.0, 0.40, 0.30, 0.20], [0.70, 0.40, 1.0, 0.15, 0.45], [0.25, 0.30, 0.15, 1.0, 0.50], [0.55, 0.20, 0.45, 0.50, 1.0]],
  'SAMSUNG':  [[1.0, 0.45, 0.30, 0.55, 0.80], [0.45, 1.0, 0.25, 0.40, 0.35], [0.30, 0.25, 1.0, 0.20, 0.40], [0.55, 0.40, 0.20, 1.0, 0.60], [0.80, 0.35, 0.40, 0.60, 1.0]],
  'default':  [[1.0, 0.40, 0.50, 0.30, 0.45], [0.40, 1.0, 0.35, 0.35, 0.30], [0.50, 0.35, 1.0, 0.20, 0.50], [0.30, 0.35, 0.20, 1.0, 0.55], [0.45, 0.30, 0.50, 0.55, 1.0]],
};

// Initial state helper to ensure consistent data structure
const getInitialSensitivityData = (ticker) => {
  return generateSensitivityData(ticker);
};

const generateSensitivityData = (ticker) => {
  const base = generateSimulatedMetrics(ticker);
  const dirVal = ((base.score % 20) - 10).toFixed(1);
  const direction60d = (dirVal > 0 ? '+' : '') + dirVal + '%';

  return {
    ...base,
    code: ticker,
    marketCap: (base.score % 100 + 10) + '.2T KRW',
    direction60d,
    kospi200Corr: 0.5 + (base.score % 40) / 100, // Add missing property
    dirMomentum: dirVal > 5 ? 'Bullish' : dirVal < -5 ? 'Bearish' : 'Sideways',
    betaLabel: base.sp500Beta > 1.2 ? 'High' : base.sp500Beta < 0.8 ? 'Low' : 'Moderate',
    downsideLabel: base.downsideBeta < 0.8 ? 'Strong Defense' : base.downsideBeta > 1.2 ? 'Aggressive' : 'Moderate',
    corrLabel: 0.5 + (base.score % 40) / 100 > 0.8 ? 'High' : 'Moderate',
  };
};


const SECTORS = ['TECH', 'FIN', 'CONS', 'ENRG', 'AUTO'];

export const AssetSensitivity = () => {
  const [selectedStockName, setSelectedStockName] = useState('KIA');
  const [stockData, setStockData] = useState(getInitialSensitivityData('KIA'));
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [suggestions, setSuggestions] = useState([]);
  const [isSearching, setIsSearching] = useState(false);
  const [hoveredCell, setHoveredCell] = useState(null);

  const stock = stockData;
  const corrData = CORRELATION_DATA[selectedStockName] || CORRELATION_DATA['default'];

  const getScoreColor = (score) => {
    if (score >= 85) return '#059669';
    if (score >= 70) return '#c084fc';
    if (score >= 55) return '#f59e0b';
    return '#ef4444';
  };

  const getCellClass = (val) => {
    if (val >= 0.7) return 'cell-high';
    if (val >= 0.4) return 'cell-med';
    return 'cell-low';
  };

  const getDefensiveFit = (score) => {
    if (score >= 85) return 'Very High';
    if (score >= 70) return 'High';
    if (score >= 55) return 'Moderate';
    return 'Low';
  };

  const strokeDashoffset = 339.292 * (1 - stock.score / 100);

  // Debounced search function
  const debouncedSearch = useCallback(
    debounce(async (val) => {
      if (val.length >= 1) {
        setIsSearching(true);
        // Local check
        const localMatches = Object.keys(STOCK_DB)
          .filter(ticker => ticker.toLowerCase().includes(val.toLowerCase()) || STOCK_DB[ticker].name.toLowerCase().includes(val.toLowerCase()))
          .map(ticker => ({
            name: STOCK_DB[ticker].name,
            ticker,
            price: STOCK_DB[ticker].price,
            logo: STOCK_DB[ticker].logo,
            logoColor: STOCK_DB[ticker].logoColor,
            source: 'local'
          }));

        // Yahoo check
        const remoteMatches = await searchTickers(val);
        const combined = [...localMatches];
        remoteMatches.forEach(rm => {
          if (!combined.find(c => c.ticker === rm.ticker)) {
            combined.push({ ...rm, source: 'yahoo' });
          }
        });
        
        setSuggestions(combined.slice(0, 8));
        setIsSearching(false);
      } else {
        setSuggestions([]);
      }
    }, 300),
    []
  );

  const handleSearchChange = (e) => {
    const val = e.target.value;
    setSearchTerm(val);
    debouncedSearch(val);
  };

  const selectStock = async (item) => {
    setSearchOpen(false);
    setSearchTerm('');
    setSuggestions([]);
    
    setSelectedStockName(item.ticker);
    
    if (item.source === 'local') {
      setStockData(STOCK_DB[item.ticker]);
    } else {
      // Fetch full details and generate sensitivity
      const quote = await getTickerQuote(item.ticker);
      const generated = generateSensitivityData(item.ticker);
      setStockData({
        ...generated,
        name: quote?.name || item.name,
        price: quote?.price || generated.price,
        code: item.ticker
      });
    }
  };

  return (
    <div className="sensitivity-page">
      <div className="report-header mb-6">
        <h1 className="mb-2">자산 민감도 확인</h1>
        <p className="text-secondary text-sm">시장 변동성에 따른 개별 자산의 리스크 노출도와 정량적 지표를 분석합니다.</p>
      </div>

      <div className="sensitivity-grid mt-6">
        {/* Left Column */}
        <div className="flex-col gap-4 left-dash">
          <div className="card-box asset-info-card" style={{minHeight: '240px', position: 'relative'}}>
             <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-4">
                  <div className="brand-logo" style={{backgroundColor: stock.logoColor}}>{stock.logo}</div>
                  <div>
                    <h3 className="font-bold text-xl m-0 truncate max-w-[120px]">{stock.name || selectedStockName}</h3>
                    <div className="text-xs text-secondary tracking-widest mt-1">{stock.code}</div>
                  </div>
                </div>
                <button className="icon-btn-search" onClick={() => setSearchOpen(!searchOpen)}>
                  <Search size={18} className="text-secondary" />
                </button>
             </div>

             {searchOpen && (
               <div className="card-search-container">
                 <div className="search-input-container">
                    <input 
                      type="text" 
                      placeholder="종목명/티커 검색..."
                      value={searchTerm}
                      onChange={handleSearchChange}
                      autoFocus
                      className="stock-search-input"
                    />
                    {isSearching && <Loader2 size={14} className="spin-icon search-loader" />}
                 </div>
                 <div className="stock-options-list mini-list">
                    {suggestions.map(item => (
                      <div 
                        key={item.ticker} 
                        className="stock-option"
                        onClick={() => selectStock(item)}
                      >
                        <div className="mini-logo" style={{backgroundColor: item.logoColor || '#3b82f6'}}>{item.logo || item.ticker.substring(0, 2)}</div>
                        <div className="flex-1">
                          <div className="text-sm font-medium">{item.name}</div>
                          <div className="text-xs text-secondary">{item.ticker}</div>
                        </div>
                      </div>
                    ))}
                 </div>
               </div>
             )}
             
             <div className="mt-6">
                <div className="text-xs text-secondary font-semibold tracking-wider mb-2">CURRENT PRICE</div>
                <div className="flex items-end gap-2">
                  <span className="text-3xl font-bold tracking-tight">₩{stock.price.toLocaleString()}</span>
                </div>
             </div>

             <div className="flex justify-between text-xs font-medium border-t pt-3 mt-4" style={{borderColor: 'var(--border-color)'}}>
                <div className="text-secondary">Sector</div>
                <div>{stock.sector}</div>
             </div>
             <div className="flex justify-between text-xs font-medium mt-1">
                <div className="text-secondary">Market Cap</div>
                <div>{stock.marketCap}</div>
             </div>
          </div>

          <div className="card-box flex-1">
            <div className="flex justify-between items-center mb-6">
              <span className="font-bold">Diagnosis</span>
              <span className="badge-purple">Live AI</span>
            </div>
            
            <div className="score-circle-container flex justify-center">
               <div className="score-circle">
                 <div className="text-3xl font-bold" style={{color: getScoreColor(stock.score)}}>{stock.score}</div>
                 <div className="text-xs text-secondary font-semibold">SCORE</div>
                 <svg className="progress-ring" viewBox="0 0 120 120">
                    <circle className="ring-bg" cx="60" cy="60" r="54"></circle>
                    <circle className="ring-fill" cx="60" cy="60" r="54" style={{stroke: getScoreColor(stock.score), strokeDashoffset: strokeDashoffset}}></circle>
                 </svg>
               </div>
            </div>

            <div className="text-center text-sm font-bold mt-6 mb-8" style={{color: getScoreColor(stock.score)}}>
              Defensive Fit: {getDefensiveFit(stock.score)}
            </div>

            <div className="diagnosis-item flex gap-3 mb-4">
               <ShieldCheck size={16} className="shrink-0 mt-1" style={{color: '#059669'}} />
               <div>
                 <div className="text-xs font-bold mb-1">Strength</div>
                 <div className="text-xs text-secondary">
                   {stock.downsideBeta < 1 
                     ? 'Low Downside Beta indicates strong resilience during market corrections.'
                     : 'Sector momentum shows strong upward trend with high trading volume.'}
                 </div>
               </div>
            </div>
            <div className="diagnosis-item flex gap-3">
               <AlertTriangle size={16} className="text-warning shrink-0 mt-1" />
               <div>
                 <div className="text-xs font-bold mb-1">Concern</div>
                 <div className="text-xs text-secondary">
                   {stock.kospi200Corr > 0.8 
                     ? 'High Market Correlation may reduce diversification benefits in small portfolios.'
                     : stock.sp500Beta > 1.3
                       ? 'High Beta exposure increases sensitivity to broad market downturns.'
                       : 'Moderate correlation requires careful position sizing for optimal hedging.'}
                 </div>
               </div>
            </div>
          </div>
        </div>

        {/* Right Column */}
        <div className="flex-col gap-4 right-dash">
           {/* Top 4 Metric Cards */}
           <div className="metric-row-grid">
              <div className="card-box p-4 metric-card-hover" onClick={() => alert(`S&P 500 Beta: ${stock.sp500Beta}\n\n이 지표는 S&P 500 대비 변동성을 나타냅니다.\n1.0 이상이면 시장보다 변동성이 큽니다.`)}>
                 <div className="flex justify-between items-start mb-2">
                   <span className="text-xs text-secondary font-semibold tracking-wider">S&P 500 BETA</span>
                   <Info size={12} className="text-secondary"/>
                 </div>
                 <div className="text-2xl font-bold mt-2">{stock.sp500Beta}</div>
                 <div className="text-xs mt-1" style={{color: stock.sp500Beta > 1.2 ? '#f59e0b' : '#059669'}}>Market Sensitivity: {stock.betaLabel}</div>
              </div>
              <div className="card-box p-4 metric-card-hover" onClick={() => alert(`Downside Beta: ${stock.downsideBeta}\n\n하락장에서의 민감도를 나타냅니다.\n1.0 미만이면 방어적, 이상이면 공격적입니다.`)}>
                 <div className="flex justify-between items-start mb-2">
                   <span className="text-xs text-secondary font-semibold tracking-wider">DOWNSIDE BETA</span>
                   <ShieldCheck size={12} className="text-secondary"/>
                 </div>
                 <div className="text-2xl font-bold mt-2">{stock.downsideBeta}</div>
                 <div className="text-xs mt-1" style={{color: stock.downsideBeta < 1 ? '#059669' : '#ef4444'}}>Risk Exposure: {stock.downsideLabel}</div>
              </div>
              <div className="card-box p-4 metric-card-hover" onClick={() => alert(`60일 방향성: ${stock.direction60d}\n\n최근 60거래일 동안의 가격 추세를 나타냅니다.`)}>
                 <div className="flex justify-between items-start mb-2">
                   <span className="text-xs text-secondary font-semibold tracking-wider">60D DIRECTION</span>
                   <Activity size={12} className="text-secondary"/>
                 </div>
                 <div className="text-2xl font-bold mt-2" style={{color: stock.direction60d.startsWith('+') ? '#059669' : '#ef4444'}}>{stock.direction60d}</div>
                 <div className="text-xs text-accent-light mt-1">Momentum Tracking: {stock.dirMomentum}</div>
              </div>
              <div className="card-box p-4 metric-card-hover" onClick={() => alert(`KOSPI 200 상관관계: ${stock.kospi200Corr}\n\n코스피 200 지수와의 상관계수입니다.\n0.8 이상이면 높은 상관관계를 의미합니다.`)}>
                 <div className="flex justify-between items-start mb-2">
                   <span className="text-xs text-secondary font-semibold tracking-wider">KOSPI 200 CORR</span>
                   <Info size={12} className="text-secondary"/>
                 </div>
                 <div className="text-2xl font-bold mt-2">{stock.kospi200Corr}</div>
                 <div className="text-xs text-secondary mt-1">Correlation: {stock.corrLabel}</div>
              </div>
           </div>

           {/* Correlation Map */}
           <div className="card-box flex-1">
              <div className="flex justify-between items-center mb-6">
                <span className="font-bold">Sector Correlation Map</span>
                <div className="flex items-center gap-2 text-xs text-secondary">
                   <span className="dot dot-dark" style={{background: '#2d2d3a'}}></span> Low
                   <span className="dot dot-purple ml-2"></span> High
                </div>
              </div>

              <div className="heatmap-container mt-4">
                <div className="heatmap-row header-row">
                   <div className="axis-label y-axis"></div>
                   {SECTORS.map(s => <div key={s} className="axis-label x-axis">{s}</div>)}
                </div>
                {SECTORS.map((rowLabel, i) => (
                  <div className="heatmap-row" key={rowLabel}>
                    <div className="axis-label y-axis">{rowLabel}</div>
                    {SECTORS.map((colLabel, j) => {
                       const val = corrData[i][j];
                       return (
                         <div 
                           key={j} 
                           className={`heatmap-cell ${getCellClass(val)}`}
                           onMouseEnter={() => setHoveredCell({row: rowLabel, col: colLabel, val})}
                           onMouseLeave={() => setHoveredCell(null)}
                           title={`${rowLabel} ↔ ${colLabel}: ${val.toFixed(2)}`}
                         >
                           {i === j && <span className="cell-diag">1.0</span>}
                         </div>
                       );
                    })}
                  </div>
                ))}

                {hoveredCell && (
                  <div className="heatmap-tooltip mt-4">
                    <span className="font-semibold">{hoveredCell.row} ↔ {hoveredCell.col}</span>: 상관계수 <span className="text-accent-light font-bold">{hoveredCell.val.toFixed(2)}</span>
                    {hoveredCell.val >= 0.7 ? ' (높은 상관관계)' : hoveredCell.val >= 0.4 ? ' (중간 상관관계)' : ' (낮은 상관관계)'}
                  </div>
                )}

                <div className="heatmap-note mt-6 text-xs text-secondary">
                  <span className="text-accent-light font-bold">Note:</span> {stock.name || selectedStockName}의 {stock.sector} 섹터는 주요 시장 섹터와의 상관관계를 기반으로 분석됩니다. 낮은 상관관계의 섹터를 헷지 자산으로 활용하면 포트폴리오 분산 효과를 극대화할 수 있습니다.
                </div>
              </div>
           </div>
        </div>
      </div>
    </div>
  );
};
