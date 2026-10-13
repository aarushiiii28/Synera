import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import React from 'react';
import { StatusChip } from '../components/StatusChip';
import { Caveat } from '../components/Caveat';
import { HashRing } from '../components/HashRing';

describe('Component tests', () => {
  it('StatusChip semantics', () => {
    const { container } = render(<StatusChip status="VERIFIED" />);
    expect(container.textContent).toContain('VERIFIED');
  });

  it('HashRing determinism', () => {
    const { container: c1 } = render(<HashRing hash="a1b2c3d4e5f67890" />);
    const { container: c2 } = render(<HashRing hash="a1b2c3d4e5f67890" />);
    expect(c1.innerHTML).toEqual(c2.innerHTML);
  });

  it('Caveat banner logic renders properly', () => {
    const { container } = render(<Caveat>SIMULATED DEMONSTRATION</Caveat>);
    expect(container.textContent).toContain('SIMULATED DEMONSTRATION');
  });
});
