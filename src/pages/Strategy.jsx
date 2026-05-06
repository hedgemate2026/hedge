import React, { useState, useEffect } from 'react';
import { Shield, Zap, TrendingDown, Target, ArrowRight, Briefcase } from 'lucide-react';
import { Button } from '../components/Button';
import './Strategy.css';
import { useNavigate } from 'react-router-dom';
import { usePortfolios } from '../context/PortfolioContext';

export const Strategy = () => {
  const navigate = useNavigate();
  const { portfolios, updatePortfolio } = usePortfolios();
  const [selectedPortfolioId, setSelectedPortfolioId] = useState(null);

  useEffect(() => {
    if (!selectedPortfolioId && portfolios.length > 0) {
      setSelectedPortfolioId(portfolios[0].id);
    }
  }, [portfolios, selectedPortfolioId]);

  const strategies = [
    {
      id: 'tail-risk',
      title: 'Tail Risk Hedging',
      desc: '극단적인 시장 폭락(Tail Risk)에 대비하여 풋옵션이나 인버스 ETF를 조합하는 강력한 방어 전략',
      icon: <TrendingDown size={24} className="text-secondary" />,
      tag: 'High Protection'
    },
    {
      id: 'beta-neutral',
      title: 'Beta Neutralization',
      desc: '시장 전체의 위험에 노출되지 않도록 상관계수를 최적화하여 포트폴리오의 베타를 0에 수렴하도록 구성',
      icon: <Target size={24} className="text-blue" />,
      tag: 'Market Neutral'
    },
    {
      id: 'defensive-overlay',
      title: 'Defensive Overlay',
      desc: '기존 포트폴리오를 유지하면서 단기 국채나 금과 같은 방어적 자산을 덧씌우는 저비용 헷징',
      icon: <Shield size={24} className="text-accent-light" />,
      tag: 'Low Cost'
    },
    {
      id: 'dynamic-hedge',
      title: 'Dynamic Hedging',
      desc: 'HedgeMate AI 모델이 실시간 시장 변동성에 따라 헷지 비율을 동적으로 조정하는 완전 자동화 모델',
      icon: <Zap size={24} className="text-warning" />,
      tag: 'AI Powered',
      badge: 'PRO'
    },
    {
      id: 'none',
      title: '전략 미적용',
      desc: '특정 방어 전략을 강제하지 않고, HedgeMate가 제공하는 기본적인 1:1 방어 및 다자산 추천 결과를 확인합니다.',
      icon: <Briefcase size={24} className="text-secondary" />,
      tag: 'Default'
    }
  ];

  const handleStrategySelect = (st) => {
    if (!selectedPortfolioId) {
      alert('전략을 적용할 포트폴리오를 먼저 선택해주세요.');
      return;
    }
    
    // Save strategy to portfolio
    updatePortfolio(selectedPortfolioId, { strategy: st.id, strategyName: st.title });
    
    navigate('/report');
  };

  const selectedPortfolio = portfolios.find(p => p.id === selectedPortfolioId);

  return (
    <div className="strategy-page">
      <div className="report-header mb-8">
        <span className="text-secondary text-xs font-semibold tracking-wider flex items-center gap-2">
          <span className="badge-purple">STRATEGY BUILDER</span>
          • Create New Defense Line
        </span>
        <h1 className="mt-2 mb-2">맞춤형 전략 수립하기</h1>
        <p className="text-secondary text-sm">보유 중인 포트폴리오의 특성과 시장 상황에 맞는 최적의 헷지 전략을 선택하거나 직접 커스텀하세요.</p>
      </div>

      {/* Portfolio Selector Step */}
      <div className="strategy-step mb-8">
        <h3 className="text-sm font-semibold mb-3 flex items-center gap-2 text-secondary">
          <Briefcase size={16} /> 1. 전략을 적용할 포트폴리오 선택
        </h3>
        
        {portfolios.length === 0 ? (
          <div className="empty-state-box" style={{padding: '2rem', textAlign: 'center', background: 'var(--bg-card)', borderRadius: '12px', border: '1px dashed var(--border-color)'}}>
            <p className="text-sm text-secondary mb-4">등록된 포트폴리오가 없습니다. 전략을 수립하기 전에 포트폴리오를 먼저 등록해주세요.</p>
            <Button variant="primary" onClick={() => navigate('/register')}>포트폴리오 등록하기</Button>
          </div>
        ) : (
          <div className="portfolio-chips-container" style={{display: 'flex', gap: '1rem', overflowX: 'auto', paddingBottom: '0.5rem'}}>
            {portfolios.map(p => (
              <button
                key={p.id}
                className={`portfolio-select-chip ${selectedPortfolioId === p.id ? 'active' : ''}`}
                onClick={() => setSelectedPortfolioId(p.id)}
              >
                <div className="chip-name font-semibold text-sm">{p.name}</div>
                <div className="chip-meta text-xs text-secondary mt-1">{p.assets.length}종목 · ₩{p.totalValue.toLocaleString()}</div>
                {p.strategy && <div className="chip-strategy text-xs text-accent-light mt-2 bg-dark rounded px-2 py-1 inline-block">적용된 전략: {p.strategyName}</div>}
              </button>
            ))}
          </div>
        )}
      </div>

      {portfolios.length > 0 && (
        <div className="strategy-step">
          <h3 className="text-sm font-semibold mb-4 flex items-center gap-2 text-secondary">
            <Target size={16} /> 2. 헷지 전략 선택
          </h3>
          <div className="strategy-grid">
            {strategies.map((st) => (
              <div key={st.id} className="strategy-card">
                <div className="flex justify-between items-start mb-4">
                  <div className="icon-wrapper bg-dark">{st.icon}</div>
                  <div className="flex gap-2 items-center">
                    {st.badge && <span className="badge-purple" style={{fontSize: '0.65rem'}}>{st.badge}</span>}
                    <span className="text-xs font-semibold text-secondary">{st.tag}</span>
                  </div>
                </div>
                <h3 className="font-semibold text-lg mb-2">{st.title}</h3>
                <p className="text-sm text-secondary mb-6 flex-1">{st.desc}</p>
                <Button 
                  variant={selectedPortfolio?.strategy === st.id ? "primary" : "outline"} 
                  className="w-full text-sm" 
                  onClick={() => handleStrategySelect(st)}
                >
                  {selectedPortfolio?.strategy === st.id ? '현재 적용중' : '이 전략 선택하기'} <ArrowRight size={14} />
                </Button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
