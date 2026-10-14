import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import App from './App';

describe('App', () => {
  it('shows the IP Studio page heading', () => {
    render(<App />);

    const heading = screen.getByRole('heading', { level: 1, name: 'IP Studio' });

    expect(heading.textContent).toBe('IP Studio');
  });
});
