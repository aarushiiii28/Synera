import React, { Suspense, lazy } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Layout } from './Layout';
import { DesignSystem } from './pages/DesignSystem';
import { BootSequence } from './BootSequence';

const queryClient = new QueryClient();

// Lazy load pages
const Observatory = lazy(() => import('./pages/Observatory').then(m => ({ default: m.Observatory })));
const Discovery = lazy(() => import('./pages/Discovery').then(m => ({ default: m.Discovery })));
const Findings = lazy(() => import('./pages/Findings').then(m => ({ default: m.Findings })));
const SpaceBiology = lazy(() => import('./pages/SpaceBiology').then(m => ({ default: m.SpaceBiology })));
const TrustCenter = lazy(() => import('./pages/TrustCenter').then(m => ({ default: m.TrustCenter })));
const Benchmark = lazy(() => import('./pages/Benchmark').then(m => ({ default: m.Benchmark })));
const RiskAssessment = lazy(() => import('./pages/RiskAssessment').then(m => ({ default: m.RiskAssessment })));

function Loader() {
  return (
    <div className="flex h-full items-center justify-center p-8">
      <div className="w-64 h-1 bg-hull relative overflow-hidden rounded-[2px]">
        <div className="absolute top-0 left-0 h-full bg-signal/50 w-1/3 animate-[scanning_1.5s_ease-in-out_infinite_alternate]" />
      </div>
      <style>{`
        @keyframes scanning {
          0% { transform: translateX(-100%); }
          100% { transform: translateX(300%); }
        }
      `}</style>
    </div>
  );
}

export function App() {
  const [booted, setBooted] = React.useState(false);

  return (
    <QueryClientProvider client={queryClient}>
      {!booted ? (
        <BootSequence onComplete={() => setBooted(true)} />
      ) : (
        <BrowserRouter>
          <Suspense fallback={<Loader />}>
          <Routes>
            <Route path="/" element={<Layout />}>
              <Route index element={<Observatory />} />
              <Route path="discovery" element={<Discovery />} />
              <Route path="findings" element={<Findings />} />
              <Route path="space-biology" element={<SpaceBiology />} />
              <Route path="trust" element={<TrustCenter />} />
              <Route path="benchmark" element={<Benchmark />} />
              <Route path="risk" element={<RiskAssessment />} />
              <Route path="_design" element={<DesignSystem />} />
            </Route>
          </Routes>
        </Suspense>
        </BrowserRouter>
      )}
    </QueryClientProvider>
  );
}
