import { axe } from 'axe-core';
import { ReactElement } from 'react';
import { render } from '@testing-library/react';

/**
 * Runs accessibility tests on a React component
 * @param ui The React element to test
 * @returns Promise that resolves with the accessibility results
 */
export async function checkAccessibility(ui: ReactElement) {
  const { container } = render(ui);
  // Properly use axe by creating a new instance with run method
  const results = await axe.run(container);
  return results;
}

// Custom matcher for accessibility testing
expect.extend({
  toHaveNoViolations(received) {
    const pass = received.violations.length === 0;
    
    if (pass) {
      return {
        pass: true,
        message: () => 'Expected accessibility violations, but none were found'
      };
    }

    const violations = received.violations
      .map((violation) => {
        return `${violation.impact} impact: ${violation.help} (${violation.nodes.length} elements affected)`;
      })
      .join('\n');

    return {
      pass: false,
      message: () => `Accessibility violations found:\n${violations}`
    };
  }
});