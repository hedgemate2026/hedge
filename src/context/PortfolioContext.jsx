import React, { createContext, useContext, useState, useEffect } from 'react';
import { getTickerQuote } from '../services/yahooFinance';

const PortfolioContext = createContext();

const STORAGE_KEY = 'hedgemate_portfolios';

const DEFAULT_PORTFOLIOS = [];

export const PortfolioProvider = ({ children }) => {
  const [usdKrwRate, setUsdKrwRate] = useState(1380);

  useEffect(() => {
    const fetchRate = async () => {
      try {
        const quote = await getTickerQuote('USDKRW=X');
        if (quote && quote.price) {
          setUsdKrwRate(quote.price);
          console.log('Fetched dynamic USD/KRW rate:', quote.price);
        }
      } catch (e) {
        console.error('Error fetching USDKRW=X rate, using fallback:', e);
      }
    };
    fetchRate();
  }, []);

  const [portfolios, setPortfolios] = useState(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        return JSON.parse(stored);
      }
    } catch (e) {
      console.error('Failed to load portfolios from storage', e);
    }
    return DEFAULT_PORTFOLIOS;
  });

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(portfolios));
    } catch (e) {
      console.error('Failed to save portfolios to storage', e);
    }
  }, [portfolios]);

  const addPortfolio = (portfolio) => {
    const now = new Date();
    const dateStr = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
    
    const getValInKRW = (a) => {
      const isUSD = a.currency === 'USD' || (!a.currency && a.ticker !== 'SAMSUNG' && a.ticker !== 'KIA');
      const rate = isUSD ? usdKrwRate : 1;
      return a.qty * a.cost * rate;
    };

    const totalValue = portfolio.assets.reduce((sum, a) => sum + getValInKRW(a), 0);
    const assetsWithWeight = portfolio.assets.map(a => {
      const valInKRW = getValInKRW(a);
      return {
        ...a,
        weight: totalValue > 0 ? Math.round(valInKRW / totalValue * 100) : 0,
      };
    });

    const newPortfolio = {
      id: `portfolio-${Date.now()}`,
      name: portfolio.name,
      purpose: portfolio.purpose,
      createdAt: dateStr,
      totalValue,
      returnRate: 0,
      riskLevel: 'Moderate',
      status: 'new',
      assets: assetsWithWeight,
    };

    setPortfolios(prev => [newPortfolio, ...prev]);
    return newPortfolio;
  };

  const deletePortfolio = (id) => {
    setPortfolios(prev => prev.filter(p => p.id !== id));
  };

  const updatePortfolio = (id, updates) => {
    setPortfolios(prev => prev.map(p => {
      if (p.id === id) {
        return { ...p, ...updates };
      }
      return p;
    }));
  };

  const getPortfolioById = (id) => {
    return portfolios.find(p => p.id === id);
  };

  return (
    <PortfolioContext.Provider value={{
      portfolios,
      addPortfolio,
      deletePortfolio,
      updatePortfolio,
      getPortfolioById,
      usdKrwRate,
    }}>
      {children}
    </PortfolioContext.Provider>
  );
};

export const usePortfolios = () => {
  const context = useContext(PortfolioContext);
  if (!context) {
    throw new Error('usePortfolios must be used within a PortfolioProvider');
  }
  return context;
};
