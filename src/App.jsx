import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { Layout } from './components/Layout';
import { PortfolioRegistration } from './pages/PortfolioRegistration';
import { ImprovementReport } from './pages/ImprovementReport';
import { AssetAnalysis } from './pages/AssetAnalysis';
import { AssetSensitivity } from './pages/AssetSensitivity';
import { Strategy } from './pages/Strategy';
import { Settings } from './pages/Settings';
import { MyPortfolios } from './pages/MyPortfolios';
import { StressTest } from './pages/StressTest';
import { PortfolioProvider } from './context/PortfolioContext';

import { Onboarding } from './pages/Onboarding';

function App() {
  return (
    <PortfolioProvider>
      <Router>
        <Routes>
          <Route path="/" element={<Onboarding />} />
          <Route path="/*" element={
            <Layout>
              <Routes>
                <Route path="/register" element={<PortfolioRegistration />} />
                <Route path="/report" element={<ImprovementReport />} />
                <Route path="/analysis" element={<AssetAnalysis />} />
                <Route path="/sensitivity" element={<AssetSensitivity />} />
                <Route path="/strategy" element={<Strategy />} />
                <Route path="/settings" element={<Settings />} />
                <Route path="/portfolios" element={<MyPortfolios />} />
                <Route path="/stress-test" element={<StressTest />} />
                <Route path="/stress" element={<StressTest />} />
              </Routes>
            </Layout>
          } />
        </Routes>
      </Router>
    </PortfolioProvider>
  );
}

export default App;
