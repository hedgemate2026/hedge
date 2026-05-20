/**
 * Utility Helpers
 */

/**
 * Simple debounce implementation
 */
export const debounce = (func, wait) => {
  let timeout;
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout);
      func(...args);
    };
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
};

/**
 * Shared mock database for common tickers
 */
export const ASSET_DATABASE = {
  'AAPL':  { name: 'Apple Inc.',       price: 178.72, sector: 'Technology',          riskVol: 14.2, sp500Beta: 1.05, downsideBeta: 0.88, score: 96, logo: 'AAPL', logoColor: '#555', currency: 'USD' },
  'NVDA':  { name: 'NVIDIA Corp.',      price: 875.28, sector: 'Technology',          riskVol: 28.7, sp500Beta: 1.68, downsideBeta: 1.12, score: 88, logo: 'NVDA', logoColor: '#76b900', currency: 'USD' },
  'MSFT':  { name: 'Microsoft Corp.',   price: 415.50, sector: 'Technology',          riskVol: 12.8, sp500Beta: 0.95, downsideBeta: 0.72, score: 97, logo: 'MSFT', logoColor: '#00a4ef', currency: 'USD' },
  'TSLA':  { name: 'Tesla Inc.',        price: 171.05, sector: 'Consumer Cyclical',  riskVol: 42.3, sp500Beta: 1.92, downsideBeta: 1.35, score: 72, logo: 'TSLA', logoColor: '#e81d23', currency: 'USD' },
  'BTC':   { name: 'Bitcoin',           price: 67420,  sector: 'Digital Asset',      riskVol: 58.1, sp500Beta: 2.15, downsideBeta: 1.85, score: 65, logo: 'BTC',  logoColor: '#f7931a', currency: 'USD' },
  'GOOGL': { name: 'Alphabet Inc.',     price: 141.80, sector: 'Communication',     riskVol: 16.5, sp500Beta: 1.12, downsideBeta: 0.92, score: 94, logo: 'GOOG', logoColor: '#4285f4', currency: 'USD' },
  'SAMSUNG': { name: '삼성전자',        price: 71500,  sector: 'Technology',          riskVol: 15.2, sp500Beta: 0.95, downsideBeta: 0.72, score: 91, logo: 'SEC',  logoColor: '#1d4ed8', currency: 'KRW' },
  'KIA':   { name: '기아',              price: 114200, sector: 'Consumer Cyclical',  riskVol: 18.4, sp500Beta: 1.24, downsideBeta: 0.88, score: 82, logo: 'KIA',  logoColor: '#ef4444', currency: 'KRW' },
};

/**
 * Shared data generator for simulated metrics
 */
export const generateSimulatedMetrics = (ticker) => {
  if (ASSET_DATABASE[ticker]) return ASSET_DATABASE[ticker];

  let hash = 0;
  for (let i = 0; i < ticker.length; i++) {
    hash = ticker.charCodeAt(i) + ((hash << 5) - hash);
  }
  const r = Math.abs(hash);
  
  const sp500Beta = parseFloat((0.5 + (r % 150) / 100).toFixed(2));
  const downsideBeta = parseFloat((0.4 + ((r >> 2) % 120) / 100).toFixed(2));
  const riskVol = parseFloat((10 + (r % 50)).toFixed(1));
  const score = 40 + (r % 55);
  
  const sectors = ['Technology', 'Financial', 'Consumer Cyclical', 'Energy', 'Communication', 'Healthcare'];
  
  return {
    ticker,
    name: `${ticker} Asset (AI Calc)`,
    price: 100 + (r % 1000),
    sector: sectors[r % sectors.length],
    riskVol,
    sp500Beta,
    downsideBeta,
    score,
    logo: ticker.substring(0, 3).toUpperCase(),
    logoColor: `hsl(${r % 360}, 60%, 45%)`
  };
};
