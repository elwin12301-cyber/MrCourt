import { api } from './api';

export interface RankedPassage {
  position: number;
  /** Another user's private document: no title, case or person is shown. */
  hidden: boolean;
  label: string | null;
  pinned: boolean;
  scores: { keyword: number; meaning: number; rerank: number | null; combined: number };
  signals: { name: string; label: string; value: number | string }[];
}

export interface QuestionRanking {
  question_id: string;
  recorded: boolean;
  mode: string | null;
  question_type: string | null;
  references: string[];
  passages: RankedPassage[];
}

/** Administrators only (feature 009). */
export const getQuestionRanking = (questionId: string) =>
  api.get<QuestionRanking>(`/admin/questions/${questionId}/ranking`);
