import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Shield, Rocket, Activity, ChevronRight, TrendingDown } from 'lucide-react';
import './Onboarding.css';
import { Button } from '../components/Button';

export const Onboarding = () => {
  const navigate = useNavigate();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  return (
    <div className={`onboarding-container ${mounted ? 'is-mounted' : ''}`}>
      {/* Background Effects */}
      <div className="ob-bg-glow glow-1"></div>
      <div className="ob-bg-glow glow-2"></div>
      <div className="ob-bg-grid"></div>

      <div className="ob-content">
        
        {/* Navigation / Header */}
        <header className="ob-header">
          <div className="logo-container">
            <div className="logo-icon-wrap">
              <Shield size={22} className="text-secondary" />
            </div>
            <span className="logo-text">HedgeMate</span>
          </div>
          <Button variant="secondary" onClick={() => navigate('/register')}>
            앱으로 돌아가기
          </Button>
        </header>

        {/* Hero Section */}
        <section className="ob-hero">
          <div className="ob-hero-badge">A.I. Powered Risk Management</div>
          <h1 className="ob-hero-title">
            나의 포트폴리오를 언제든 안전하게,<br />
            <span className="text-gradient">HedgeMate</span>
          </h1>
          <p className="ob-hero-subtitle">
            예측 불가능한 시장의 변동성 속에서도 당신의 포트폴리오를 지켜냅니다. 단 3단계로 기관 투자자 수준의 헷지 전략을 구축하세요.
          </p>
          
          <div className="ob-hero-actions">
            <button className="ob-btn-primary group" onClick={() => navigate('/register')}>
              지금 시작하기
              <ChevronRight size={18} className="group-hover:translate-x-1 transition-transform" />
            </button>
          </div>
        </section>

        {/* Steps Section */}
        <section className="ob-steps-section">
          <h2 className="ob-steps-heading">단 3단계로 끝내는 리스크 관리</h2>
          
          <div className="ob-steps-grid">
            {/* Step 1 */}
            <div className="ob-step-card" style={{ transitionDelay: '0.1s' }}>
              <div className="ob-step-num">01</div>
              <div className="ob-step-icon" style={{ color: '#c084fc', background: 'rgba(192, 132, 252, 0.1)' }}>
                <BriefcaseIcon />
              </div>
              <h3 className="ob-step-title">포트폴리오 등록</h3>
              <p className="ob-step-desc">
                보유 중인 자산과 수량을 입력하세요. 주식, ETF, 채권 등 다양한 자산군을 지원하며 현재 가치를 즉시 평가합니다.
              </p>
            </div>

            {/* Step 2 */}
            <div className="ob-step-card" style={{ transitionDelay: '0.2s' }}>
              <div className="ob-step-num">02</div>
              <div className="ob-step-icon" style={{ color: '#60a5fa', background: 'rgba(96, 165, 250, 0.1)' }}>
                <Activity size={24} />
              </div>
              <h3 className="ob-step-title">취약점 및 민감도 분석</h3>
              <p className="ob-step-desc">
                금리, 임금, 유가 등 거시 경제 지표에 대한 민감도를 분석하고, Tail Risk와 최대 낙폭(MDD)을 예측합니다.
              </p>
            </div>

            {/* Step 3 */}
            <div className="ob-step-card" style={{ transitionDelay: '0.3s' }}>
              <div className="ob-step-num">03</div>
              <div className="ob-step-icon" style={{ color: '#10b981', background: 'rgba(16, 185, 129, 0.1)' }}>
                <Rocket size={24} />
              </div>
              <h3 className="ob-step-title">맞춤형 헷지 전략 적용</h3>
              <p className="ob-step-desc">
                AI가 제안하는 다자산 배분 모델 및 방어 전략을 적용하여 샤프 지수(Sharpe Ratio)를 극대화하세요.
              </p>
            </div>
          </div>
        </section>
        
        {/* Feature Highlights */}
        <section className="ob-feature-banner mt-12">
          <div className="ob-feature-item">
            <TrendingDown size={20} className="text-accent-light" />
            <span>최대 오차율 2.4% 초정밀 시뮬레이션</span>
          </div>
          <div className="ob-feature-item">
            <Shield size={20} className="text-blue" />
            <span>하락장 방어 확률 89.2%</span>
          </div>
        </section>

      </div>
    </div>
  );
};

function BriefcaseIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect width="20" height="14" x="2" y="7" rx="2" ry="2"/>
      <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/>
    </svg>
  );
} 
