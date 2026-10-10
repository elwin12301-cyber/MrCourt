import { initials } from '../../src/components/AppShell';
import { formatToday, greetingFor, greetingName } from '../../src/pages/Dashboard';

describe('dashboard greeting helpers', () => {
  it('addresses advocates by title and surname like the prototype', () => {
    expect(greetingName('Adv. Rohan Sharma')).toBe('Adv. Sharma');
  });

  it('uses the first name for people without a title', () => {
    expect(greetingName('Anita Sharma')).toBe('Anita');
  });

  it('chooses the greeting from the hour', () => {
    expect(greetingFor(new Date(2026, 9, 7, 9))).toBe('Good morning');
    expect(greetingFor(new Date(2026, 9, 7, 14))).toBe('Good afternoon');
    expect(greetingFor(new Date(2026, 9, 7, 20))).toBe('Good evening');
  });

  it('formats the date like the prototype', () => {
    expect(formatToday(new Date(2026, 9, 7))).toBe('Wednesday, 7 October 2026');
  });

  it('builds avatar initials without the title', () => {
    expect(initials('Adv. Rohan Sharma')).toBe('RS');
    expect(initials('Anita Sharma')).toBe('AS');
  });
});
