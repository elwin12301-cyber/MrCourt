/**
 * The question-bar microphone and voice control must never listen at the same time (research D10). The question
 * bar announces when it starts and ends; voice control sets its own listening aside in between.
 */
export const MIC_EVENT = 'mrcourt:question-mic';

export function announceQuestionMic(state: 'start' | 'end'): void {
  if (typeof window !== 'undefined') window.dispatchEvent(new CustomEvent(MIC_EVENT, { detail: state }));
}
