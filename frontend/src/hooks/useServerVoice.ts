import { useCallback, useState } from 'react';
import { ApiError } from '../services/api';
import { transcribe } from '../services/text';
import { RECORDER_DENIED, RECORDER_FAILED, useRecorder } from './useRecorder';
import type { SpeechInput, VoiceState } from './useSpeechInput';

export const SERVER_LISTENING = 'Recording… speak now, then press the microphone again to stop.';
export const SERVER_WORKING = 'Turning your speech into text…';
export const SERVER_EMPTY = "I didn't catch any words. Try again, or type instead.";

/**
 * The same shape as the browser microphone hook, but the audio is sent to the speech service
 * (Better for Tamil and other Indian languages). Used only when the person chooses it.
 */
export function useServerVoice(onText: (text: string) => void, language: string, setLanguage: (code: string) => void): SpeechInput {
  const [notice, setNotice] = useState<string | null>(null);
  const [working, setWorking] = useState(false);
  const [usedVoice, setUsedVoice] = useState(false);

  const onTurn = useCallback(
    async (wav: Blob) => {
      setWorking(true);
      setNotice(SERVER_WORKING);
      try {
        const text = await transcribe(wav, language);
        if (text) {
          onText(text);
          setUsedVoice(true);
          setNotice('Done. Check the text, then send.');
        } else {
          setNotice(SERVER_EMPTY);
        }
      } catch (error) {
        setNotice(error instanceof ApiError ? error.message : RECORDER_FAILED);
      } finally {
        setWorking(false);
      }
    },
    [language, onText],
  );

  const recorder = useRecorder((wav) => void onTurn(wav));

  const toggle = useCallback(() => {
    if (recorder.recording) {
      recorder.stop();
      return;
    }
    setNotice(SERVER_LISTENING);
    void recorder.start();
  }, [recorder]);

  const state: VoiceState =
    recorder.state === 'recording' ? 'listening' : recorder.state === 'denied' ? 'denied' : recorder.state === 'error' ? 'error' : 'idle';
  const shown = recorder.state === 'denied' ? RECORDER_DENIED : recorder.state === 'error' ? RECORDER_FAILED : notice;

  return {
    toggle,
    state,
    listening: state === 'listening' || working,
    notice: shown,
    language,
    setLanguage,
    usedVoice,
    clearUsedVoice: () => setUsedVoice(false),
  };
}
