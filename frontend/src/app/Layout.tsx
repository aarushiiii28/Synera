import React from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import { TelemetryBar } from '../components/TelemetryBar';
import {
  IconObservatory, IconDiscovery, IconFindings, 
  IconBiology, IconTrust, IconBenchmark, IconRisk
} from '../components/NavIcons';

export function Layout() {
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
      <nav className="w-[72px] h-full border-r border-line bg-void flex flex-col items-center py-6 gap-8 z-50">
        <div className="w-8 h-8 flex items-center justify-center font-display font-light text-2xl text-signal tracking-[0.18em]">
          S
        </div>
        
        <div className="flex flex-col gap-4 mt-4 flex-1">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              title={item.title}
              className={({ isActive }) => 
                `w-10 h-10 flex items-center justify-center rounded-[2px] transition-colors
                 ${isActive ? 'text-signal bg-hull border border-line-strong' : 'text-faint hover:text-muted'}`
              }
            >
              {item.icon}
            </NavLink>
          ))}
        </div>
        
        {/* Design System Link */}
        <NavLink to="/_design" className="text-[10px] font-mono text-faint hover:text-signal uppercase" title="Design System">
          DS
        </NavLink>
      </nav>

      {/* Main Area */}
      <div className="flex-1 flex flex-col h-full relative">
        <TelemetryBar />
        
        <main className="flex-1 overflow-auto relative">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
