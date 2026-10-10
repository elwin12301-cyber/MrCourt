import { useCallback, useEffect, useRef, useState } from 'react';
import { concat, downsample, encodeWav } from '../services/wav';

export const MAX_TURN_SECONDS = 25;

export type RecorderState = 'idle' | 'recording' | 'denied' | 'error';

export const RECORDER_DENIED =
  'The microphone is blocked. Allow it for this site in your browser settings, or type instead.';
export const RECORDER_FAILED = 'Could not use the microphone. Please type instead.';

/**
 * Records one short spoken turn from the microphone and hands back a 16 kHz mono WAV file. The
 * audio lives only in memory: it goes to the speech service through MrCourt and is never saved.
 */
export function useRecorder(onTurn: (wav: Blob) => void) {
  const [state, setState] = useState<RecorderState>('idle');
  const [seconds, setSeconds] = useState(0);
  const stopRef = useRef<(() => void) | null>(null);

  useEffect(() => () => stopRef.current?.(), []);

  const stop = useCallback(() => stopRef.current?.(), []);

  const start = useCallback(async () => {
    if (stopRef.current) return;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const AudioCtor =
        window.AudioContext ?? (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      const context = new AudioCtor();
      const source = context.createMediaStreamSource(stream);
      const processor = context.createScriptProcessor(4096, 1, 1);
      const chunks: Float32Array[] = [];
      processor.onaudioprocess = (event) => chunks.push(new Float32Array(event.inputBuffer.getChannelData(0)));
      source.connect(processor);
      processor.connect(context.destination);
      const startedAt = Date.now();
      const timer = window.setInterval(() => {
        const elapsed = Math.floor((Date.now() - startedAt) / 1000);
        setSeconds(elapsed);
        if (elapsed >= MAX_TURN_SECONDS) stopRef.current?.();
      }, 250);
      setSeconds(0);
      setState('recording');
      stopRef.current = () => {
        stopRef.current = null;
        window.clearInterval(timer);
        processor.disconnect();
        source.disconnect();
        stream.getTracks().forEach((t) => t.stop());
        const rate = context.sampleRate;
        void context.close();
        setState('idle');
        const samples = concat(chunks);
        if (samples.length > 0) onTurn(encodeWav(downsample(samples, rate)));
      };
    } catch (error) {
      const name = (error as { name?: string }).name;
      setState(name === 'NotAllowedError' || name === 'SecurityError' ? 'denied' : 'error');
    }
  }, [onTurn]);

  return { state, recording: state === 'recording', seconds, start, stop };
}
