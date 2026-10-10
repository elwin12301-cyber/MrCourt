import type { ReactNode } from 'react';
import { Icon } from './Icon';

/** Navy left half shared by the welcome, login and registration screens. */
export function BrandPanel({ children }: { children: ReactNode }) {
  return (
    <div className="brand">
      <div className="mark">
        <Icon name="scale" />
      </div>
      {children}
    </div>
  );
}
