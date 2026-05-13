/**
 * Yahoo Finance API Service
 * Uses the proxy configured in vite.config.js to bypass CORS.
 */

const CACHE = {
  search: new Map(),
  quotes: new Map(),
};

const CACHE_TTL = 5 * 60 * 1000; // 5 minutes

export const searchTickers = async (query) => {
  if (!query || query.length < 1) return [];
  
  const cacheKey = query.toLowerCase().trim();
  if (CACHE.search.has(cacheKey)) {
    const { data, timestamp } = CACHE.search.get(cacheKey);
    if (Date.now() - timestamp < CACHE_TTL) return data;
  }

  try {
    const response = await fetch(`/api/yahoo/v1/finance/search?q=${encodeURIComponent(query)}&quotesCount=10&newsCount=0`);
    if (!response.ok) throw new Error('Network response was not ok');
    
    const data = await response.json();
    const results = (data.quotes || []).map(quote => ({
      ticker: quote.symbol,
      name: quote.shortname || quote.longname || quote.symbol,
      exchange: quote.exchange,
      type: quote.quoteType,
    }));

    CACHE.search.set(cacheKey, { data: results, timestamp: Date.now() });
    return results;
  } catch (error) {
    console.error('Error searching tickers:', error);
    return [];
  }
};

export const getTickerQuote = async (ticker) => {
  if (!ticker) return null;
  
  const cacheKey = ticker.toUpperCase().trim();
  if (CACHE.quotes.has(cacheKey)) {
    const { data, timestamp } = CACHE.quotes.get(cacheKey);
    if (Date.now() - timestamp < CACHE_TTL) return data;
  }

  try {
    const response = await fetch(`/api/yahoo/v7/finance/quote?symbols=${encodeURIComponent(ticker)}`);
    if (!response.ok) throw new Error('Network response was not ok');
    
    const data = await response.json();
    const quote = data.quoteResponse?.result?.[0];
    
    if (!quote) return null;
    
    const result = {
      ticker: quote.symbol,
      name: quote.shortName || quote.longName || quote.symbol,
      price: quote.regularMarketPrice,
      currency: quote.currency,
      exchange: quote.exchange,
      change: quote.regularMarketChange,
      changePercent: quote.regularMarketChangePercent,
    };

    CACHE.quotes.set(cacheKey, { data: result, timestamp: Date.now() });
    return result;
  } catch (error) {
    console.error('Error fetching ticker quote:', error);
    return null;
  }
};
