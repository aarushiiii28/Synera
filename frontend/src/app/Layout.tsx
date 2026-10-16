import { Suspense } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { Backdrop } from '../components/Backdrop';
import { BottomBar, Rail } from '../components/Rail';
import { TopBar } from '../components/TopBar';
import { Tour } from '../components/Tour';
import { StaticBanner } from '../components/StaticBanner';
import { Skeleton } from '../components/States';

export function Layout() {
  const { pathname } = useLocation();
  return (
    <div className="relative flex min-h-screen text-text">
      <Backdrop />
      <Rail />
      <div className="relative z-10 flex-1 min-w-0 flex flex-col min-h-screen pb-16 lg:pb-0">
        <TopBar />
        <StaticBanner />
        <main id="main" className="flex-1" key={pathname}>
          <Suspense fallback={<div className="p-10"><Skeleton h={220} label="ENTERING ORBIT" /></div>}>
            <Outlet />
          </Suspense>
        </main>
      </div>
      <BottomBar />
      <Tour />
    </div>
  );
}
