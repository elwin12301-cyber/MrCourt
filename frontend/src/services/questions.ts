import { api } from './api';

export interface Citation {
  number: number;
  label: string;
  source_url: string | null;
  /** Lets the reader open the cited passage; null once the source has been removed. */
  passage_id?: string | null;
}

export interface AnswerParagraph {
  text: string;
  citation_numbers: number[];
  kind?: 'law' | 'case';
}

export interface Answer {
  question_id?: string;
  /** 'passages' when no AI service wrote the answer. */
  answer_mode?: 'full' | 'passages';
  /** Whether meaning-based search took part in finding the sources. */
  search_mode?: 'meaning' | 'keywords';
  /** Which language the sources are in, when it differs from the question's. */
  source_language_note?: string | null;
  outcome: 'cited' | 'answered' | 'no_reliable_source';
  paragraphs: AnswerParagraph[];
  citations: Citation[];
  message: string | null;
  disclaimer: string;
  /** Clients only: set when the question looks like it is about their own case. */
  case_specific_notice?: string | null;
  /** Clients only: a standing reminder to ask their lawyer about their own case. */
  lawyer_reminder?: string | null;
}

export type InputMethod = 'typed' | 'voice';

export function askQuestion(text: string, caseId?: string, inputMethod: InputMethod = 'typed'): Promise<Answer> {
  return api.post<Answer>('/questions', { text, case_id: caseId, input_method: inputMethod });
}

/** Suggested questions, as in the prototype. */
export const SUGGESTIONS: { label: string; question: string }[] = [
  {
    label: 'Cheque bounce, S.138',
    question: 'What is the punishment for cheque bounce under Section 138 of the NI Act?',
  },
  { label: 'Bail under BNSS', question: 'How does bail work for non-bailable offences under BNSS?' },
  {
    label: 'Consumer complaint limitation',
    question: 'What is the limitation period for a consumer complaint?',
  },
];
