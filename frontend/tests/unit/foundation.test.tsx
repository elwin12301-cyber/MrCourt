import { render, screen } from '@testing-library/react';
import { Button, Chip, Disclaimer, Pill } from '../../src/components/ui';
import { applyTheme } from '../../src/services/theme';

describe('shared components', () => {
  it('renders the not-legal-advice disclaimer', () => {
    render(<Disclaimer />);
    expect(screen.getByText('Informational only, not legal advice.')).toBeInTheDocument();
  });

  it('marks a pill as pressed through aria-pressed', () => {
    render(<Pill pressed>Active</Pill>);
    expect(screen.getByRole('button', { name: 'Active' })).toHaveAttribute('aria-pressed', 'true');
  });

  it('uses prototype class names for chips and buttons', () => {
    render(
      <>
        <Chip tone="soon">Hearing soon</Chip>
        <Button variant="gold">Go</Button>
      </>,
    );
    expect(screen.getByText('Hearing soon')).toHaveClass('chip', 'soon');
    expect(screen.getByRole('button', { name: 'Go' })).toHaveClass('btn', 'gold');
  });
});

describe('theme', () => {
  it('sets and clears the data-theme attribute', () => {
    applyTheme('dark');
    expect(document.documentElement.dataset.theme).toBe('dark');
    applyTheme('system');
    expect(document.documentElement.dataset.theme).toBeUndefined();
  });
});
