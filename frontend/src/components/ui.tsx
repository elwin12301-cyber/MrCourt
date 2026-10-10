import type { ButtonHTMLAttributes, HTMLAttributes, ReactNode } from 'react';
import { Icon } from './Icon';

export type ChipTone = 'active' | 'ok' | 'soon' | 'closed';

export function Chip({ tone, children }: { tone: ChipTone; children: ReactNode }) {
  return <span className={`chip ${tone}`}>{children}</span>;
}

interface PillProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  pressed?: boolean;
}

export function Pill({ pressed, className = '', ...rest }: PillProps) {
  const aria = pressed === undefined ? {} : { 'aria-pressed': pressed };
  return <button type="button" className={`pill ${className}`.trim()} {...aria} {...rest} />;
}

export function Card({ className = '', ...rest }: HTMLAttributes<HTMLDivElement>) {
  return <div className={`card ${className}`.trim()} {...rest} />;
}

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'gold' | 'ghost';
  small?: boolean;
}

export function Button({ variant = 'primary', small, className = '', type, ...rest }: ButtonProps) {
  const classes = ['btn', variant === 'primary' ? '' : variant, small ? 'small' : '', className]
    .filter(Boolean)
    .join(' ');
  return <button type={type ?? 'button'} className={classes} {...rest} />;
}

export const DISCLAIMER_TEXT = 'Informational only, not legal advice.';

/** The single place the not-legal-advice line is rendered (constitution principle II). */
export function Disclaimer({ text = DISCLAIMER_TEXT }: { text?: string }) {
  return (
    <div className="disc">
      <Icon name="shield" />
      {text}
    </div>
  );
}
