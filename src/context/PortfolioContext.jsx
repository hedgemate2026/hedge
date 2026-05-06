import React, { createContext, useContext, useState, useEffect } from 'react';

const PortfolioContext = createContext();

const STORAGE_KEY = 'hedgemate_portfolios';

const DEFAULT_PORTFOLIOS = [];

export const PortfolioProvider = ({ children }) => {
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
    
    const totalValue = portfolio.assets.reduce((sum, a) => sum + (a.qty * a.cost), 0);
    const totalQtyCost = portfolio.assets.reduce((sum, a) => sum + (a.qty * a.cost), 0);
    const assetsWithWeight = portfolio.assets.map(a => ({
      ...a,
      weight: totalQtyCost > 0 ? Math.round((a.qty * a.cost) / totalQtyCost * 100) : 0,
    }));

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
