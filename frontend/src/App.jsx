import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import AppShell from './components/layout/AppShell';
import Overview from './pages/Overview';
import AgentDashboard from './pages/AgentDashboard';
import Analysis from './pages/Analysis';
import RuleEngine from './pages/RuleEngine';
import Assistant from './pages/Assistant';
import ModelStudio from './pages/ModelStudio';

export default function App() {
  return (
    <BrowserRouter>
      <AppShell>
        <Routes>
          <Route path="/" element={<Overview />} />
          <Route path="/agents" element={<AgentDashboard />} />
          <Route path="/analysis" element={<Analysis />} />
          <Route path="/rules" element={<RuleEngine />} />
          <Route path="/assistant" element={<Assistant />} />
          <Route path="/model-studio" element={<ModelStudio />} />
          {/* Fallback route */}
          <Route path="*" element={<Overview />} />
        </Routes>
      </AppShell>
    </BrowserRouter>
  );
}
