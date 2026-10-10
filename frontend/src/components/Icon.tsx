import type { CSSProperties } from 'react';
import { SPRITE, type IconName } from './sprite';

/** Renders the shared SVG symbol sprite once, at the top of the app. */
export function IconSprite() {
  return (
    <svg
      width="0"
      height="0"
      style={{ position: 'absolute' }}
      aria-hidden="true"
      // Constant markup generated from the prototype, never user input.
      dangerouslySetInnerHTML={{ __html: `<defs>${SPRITE}</defs>` }}
    />
  );
}

export function Icon({ name, size, style }: { name: IconName; size?: number; style?: CSSProperties }) {
  const sized = size ? { width: size, height: size, ...style } : style;
  return (
    <svg className="icon" style={sized} aria-hidden="true" focusable="false">
      <use href={`#i-${name}`} />
    </svg>
  );
}
