import { useEffect, useRef, useState } from 'react';
import { useVoice } from '../voice/voiceContext';

/** React 18's types do not know the popover attribute yet. */
const POPOVER = { popover: 'manual' } as Record<string, string>;

interface Badge {
  key: number;
  number: number;
  left: number;
  top: number;
}

/**
 * Number labels drawn beside the controls on screen ("click 7"). The layer ignores the pointer and is hidden
 * from assistive technology (each control already has its own name). It lives in the browser's top layer so it
 * also shows above an open dialog.
 */
export function VoiceNumbers() {
  const { numbers } = useVoice();
  const layer = useRef<HTMLDivElement>(null);
  const [badges, setBadges] = useState<Badge[]>([]);

  useEffect(() => {
    const el = layer.current;
    if (!el) return undefined;
    if (!numbers || !numbers.length) {
      setBadges([]);
      try {
        el.hidePopover?.();
      } catch {
        /* not shown */
      }
      return undefined;
    }
    let frame = 0;
    const draw = () => {
      frame = 0;
      const next: Badge[] = [];
      numbers.forEach((control, i) => {
        if (!control.element.isConnected || control.number === undefined) return;
        const r = control.element.getBoundingClientRect();
        if (r.width === 0 && r.height === 0) return;
        if (r.bottom < 0 || r.top > window.innerHeight || r.right < 0 || r.left > window.innerWidth) return;
        next.push({ key: i, number: control.number, left: Math.max(2, r.left - 8), top: Math.max(2, r.top - 8) });
      });
      setBadges(next);
    };
    const schedule = () => {
      if (!frame) frame = requestAnimationFrame(draw);
    };
    try {
      // Hide and show again so the layer sits above any dialog opened since.
      el.hidePopover?.();
      el.showPopover?.();
    } catch {
      /* the popover API is not available: the fixed layer still shows */
    }
    draw();
    window.addEventListener('scroll', schedule, true);
    window.addEventListener('resize', schedule);
    return () => {
      window.removeEventListener('scroll', schedule, true);
      window.removeEventListener('resize', schedule);
      if (frame) cancelAnimationFrame(frame);
    };
  }, [numbers]);

  return (
    <div ref={layer} className="vc-numbers" data-voice-ui aria-hidden="true" {...POPOVER}>
      {badges.map((b) => (
        <span key={b.key} className="vc-num" data-voice-num style={{ left: b.left, top: b.top }}>
          {b.number}
        </span>
      ))}
    </div>
  );
}
