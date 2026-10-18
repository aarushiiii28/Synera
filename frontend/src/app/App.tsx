import { lazy } from 'react';
import { BrowserRouter, Route, Routes } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Layout } from './Layout';

const queryClient = new QueryClient({ defaultOptions: { queries: { staleTime: 10_000, refetchOnWindowFocus: false } } });

// Route-level code splitting: three.js only loads with the pages that use the globe.
const Observatory = lazy(() => import('./pages/Observatory'));
const Discovery = lazy(() => import('./pages/Discovery'));
const Findings = lazy(() => import('./pages/Findings'));
const Dossier = lazy(() => import('./pages/Dossier'));
const TrustCenter = lazy(() => import('./pages/TrustCenter'));
const SpaceBiology = lazy(() => import('./pages/SpaceBiology'));
const Benchmark = lazy(() => import('./pages/Benchmark'));
const RiskBrief = lazy(() => import('./pages/RiskBrief'));
const Guide = lazy(() => import('./pages/Guide'));
const Scenario = lazy(() => import('./pages/Scenario'));
const DesignSystem = lazy(() => import('./pages/DesignSystem'));

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<Observatory />} />
            <Route path="discovery" element={<Discovery />} />
            <Route path="findings" element={<Findings />} />
            <Route path="findings/:id" element={<Dossier />} />
            <Route path="trust" element={<TrustCenter />} />
            <Route path="space-biology" element={<SpaceBiology />} />
            <Route path="benchmark" element={<Benchmark />} />
            <Route path="risk" element={<RiskBrief />} />
            <Route path="scenario" element={<Scenario />} />
            <Route path="guide" element={<Guide />} />
            {import.meta.env.DEV && <Route path="_design" element={<DesignSystem />} />}
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
