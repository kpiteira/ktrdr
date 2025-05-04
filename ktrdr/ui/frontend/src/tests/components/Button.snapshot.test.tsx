import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { Button } from '@/components/common/Button';

describe('Button Component Snapshots', () => {
  it('renders primary button correctly', () => {
    const { container } = render(<Button>Primary Button</Button>);
    expect(container).toMatchSnapshot();
  });

  it('renders secondary button correctly', () => {
    const { container } = render(<Button variant="secondary">Secondary Button</Button>);
    expect(container).toMatchSnapshot();
  });

  it('renders loading button correctly', () => {
    const { container } = render(<Button isLoading>Loading Button</Button>);
    expect(container).toMatchSnapshot();
  });

  it('renders button with icons correctly', () => {
    const { container } = render(
      <Button 
        leftIcon={<span data-testid="left-icon">←</span>}
        rightIcon={<span data-testid="right-icon">→</span>}
      >
        Button with Icons
      </Button>
    );
    expect(container).toMatchSnapshot();
  });

  it('renders disabled button correctly', () => {
    const { container } = render(<Button disabled>Disabled Button</Button>);
    expect(container).toMatchSnapshot();
  });

  it('renders full width button correctly', () => {
    const { container } = render(<Button isFullWidth>Full Width Button</Button>);
    expect(container).toMatchSnapshot();
  });
});