import React from 'react';
import { Panel } from '../../components/Panel';

export function Observatory() {
  return (
    <div className="p-8">
      <h1 className="font-display text-4xl mb-8">PLANETARY OBSERVATORY</h1>
      <Panel>
        <p className="font-mono text-muted">Awaiting connection...</p>
      </Panel>
    </div>
  );
}
