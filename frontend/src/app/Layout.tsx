import React from 'react';
import { NavLink, Outlet, useLocation } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { TelemetryBar } from '../components/TelemetryBar';
import {
  IconObservatory, IconDiscovery, IconFindings, 
  IconBiology, IconTrust, IconBenchmark, IconRisk
} from '../components/NavIcons';
import { Logo, Wordmark } from '../components/Logo';
import { Graticule } from '../components/Graticule';
import { Stars } from '../components/Stars';

export function Layout() {
  const location = useLocation();
  const reducedMotion = typeof window !== 'undefined' ? window.matchMedia('(prefers-reduced-motion: reduce)').matches : false;
  const navItems = [
    { to: '/', icon: <IconObservatory />, title: 'Observatory' },
    { to: '/discovery', icon: <IconDiscovery />, title: 'Discovery Engine' },
    { to: '/findings', icon: <IconFindings />, title: 'Finding Registry' },
    { to: '/space-biology', icon: <IconBiology />, title: 'Space Biology' },
    { to: '/trust', icon: <IconTrust />, title: 'Trust Center' },
    { to: '/benchmark', icon: <IconBenchmark />, title: 'Engine Benchmark' },
    { to: '/risk', icon: <IconRisk />, title: 'Risk Assessment' },
  ];

  return (
    <div className="flex h-screen overflow-hidden text-text selection:bg-signal/30">
      {/* Left Rail */}
      <nav className="w-[72px] h-full border-r border-line bg-void flex flex-col items-center py-6 gap-8 z-50 group transition-all duration-300 hover:w-[240px] hover:items-start hover:px-6">
        <div className="flex items-center gap-4 w-full">
          <Logo size={28} className="flex-shrink-0 mx-auto group-hover:mx-0" />
          <Wordmark className="hidden group-hover:flex" />
        </div>
        
        <div className="flex flex-col gap-2 mt-4 flex-1 w-full">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              title={item.title}
              className={({ isActive }) => 
                `flex items-center gap-4 h-12 w-full px-[21px] group-hover:px-0 transition-colors relative
                 ${isActive ? 'text-signal' : 'text-faint hover:text-muted'}`
              }
            >
              {({ isActive }) => (
                <>
                  {isActive && <div className="absolute left-[-24px] group-hover:left-[-24px] top-1/2 -translate-y-1/2 w-[2px] h-6 bg-signal shadow-[0_0_8px_var(--signal)]" />}
                  <div className={`flex-shrink-0 w-6 h-6 flex items-center justify-center ${isActive ? '[&>svg]:stroke-[1.5px] [&>svg]:stroke-signal' : '[&>svg]:stroke-[1px]'}`}>
                    {item.icon}
                  </div>
                  <span className="hidden group-hover:block font-sans text-sm tracking-wide whitespace-nowrap overflow-hidden">
                    {item.title}
                  </span>
                </>
              )}
            </NavLink>
          ))}
        </div>
        
        {/* Design System Link */}
        {import.meta.env.DEV && (
          <NavLink to="/_design" className="text-[10px] font-mono text-faint hover:text-signal uppercase mx-auto group-hover:mx-0 group-hover:w-full" title="Design System">
            <span className="group-hover:hidden">DS</span>
            <span className="hidden group-hover:inline">DESIGN SYSTEM</span>
          </NavLink>
        )}
      </nav>

      {/* Main Area */}
      <div className="flex-1 flex flex-col h-full relative overflow-hidden bg-transparent">
        {/* Atmosphere */}
        <Stars />
        <div className="absolute inset-0 z-0 bg-[radial-gradient(circle_at_80%_105%,rgba(255,181,71,0.06)_0%,transparent_50%)] pointer-events-none" />
        <div className="absolute inset-0 z-0 pointer-events-none shadow-[inset_0_0_120px_rgba(5,13,24,1)]" />
        <Graticule />
        
        <div className="relative z-10 flex flex-col h-full">
          <TelemetryBar />
          
          <main className="flex-1 overflow-auto relative">
            <AnimatePresence mode="wait">
              <motion.div
                key={location.pathname}
                initial={reducedMotion ? { opacity: 1 } : { opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={reducedMotion ? { opacity: 1 } : { opacity: 0, y: -10 }}
                transition={{ duration: 0.3, staggerChildren: 0.1 }}
                className="h-full w-full relative"
              >
                {/* Scan line effect */}
                {!reducedMotion && (
                  <motion.div 
                    initial={{ top: '-10%', opacity: 1 }}
                    animate={{ top: '110%', opacity: 0 }}
                    transition={{ duration: 0.3, ease: 'linear' }}
                    className="absolute left-0 right-0 h-[2px] bg-signal shadow-[0_0_10px_var(--signal)] z-50 pointer-events-none"
                  />
                )}
                <Outlet />
              </motion.div>
            </AnimatePresence>
          </main>
        </div>
      </div>
    </div>
  );
}
