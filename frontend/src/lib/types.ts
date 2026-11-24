// The shapes of the JSON the Python API sends. They mirror backend/app/api/schemas.py.

export type Role = "admin" | "researcher";

export interface User {
  id: number;
  email: string;
  name: string;
  role: Role;
  is_active: boolean;
}

// ---------------------------------------------------------------- checking files

export interface Issue {
  line: number;
  severity: "error" | "warning";
  code: string;
  message: string;
}

export interface CheckResult {
  ok: boolean;
  error_count: number;
  warning_count: number;
  issues: Issue[];
  survey: { id: string | null; title: string | null; target: string | null; questions: number; quotas: number } | null;
}

// ---------------------------------------------------------------- surveys

export type SurveyStatus = "draft" | "live" | "closed";
export type ClosedReason = "closed_by_team" | "deadline_passed" | "target_reached";

export interface SurveySummary {
  id: number;
  slug: string;
  title: string;
  status: SurveyStatus;
  target: number | null;
  deadline: string | null;
  live_at: string | null;
  closed_at: string | null;
  closed_reason: ClosedReason | null;
  created_at: string;
  current_version_no: number | null;
  has_draft: boolean;
  completed: number;
}

export interface Version {
  id: number;
  version_no: number;
  file_name: string | null;
  approved_at: string | null;
  approved_by: string | null;
  question_count: number;
}

export interface Draft {
  id: number;
  file_name: string | null;
  text: string;
  updated_at: string;
  updated_by: string | null;
  check: CheckResult;
}

export interface SurveyDetail extends SurveySummary {
  versions: Version[];
  draft: Draft | null;
}

export interface VersionDetail extends Version {
  text: string;
  questions: { qid: string; type: string; text: string; required: boolean }[];
  quotas: { question_qid: string; value: string; target: number }[];
}

export interface Dashboard {
  survey_id: number;
  status: SurveyStatus;
  target: number | null;
  started: number;
  completed: number;
  terminated: number;
  in_progress: number;
  progress: number;
  quotas: { question: string; value: string; target: number; done: number; left: number; full: boolean }[];
  reasons: { reason: string; count: number }[];
  versions: { version_no: number | null; started: number; completed: number }[];
  drop_off: { question: string; count: number }[];
  quality: {
    checked: number;
    speeders: number;
    straight_liners: number;
    flagged: { respondent_id: number | null; flags: string[]; seconds: number }[];
  };
  test_runs: number;
  updated_at: string;
}

// ---------------------------------------------------------------- respondents

export type QuestionType =
  | "single" | "multi" | "dropdown" | "yesno" | "rating" | "nps" | "matrix"
  | "text" | "longtext" | "number" | "formatted" | "info" | "consent";

export interface ScreenOption {
  value: string;
  label: string;
  other: boolean;
  exclusive: boolean;
}

export interface ScreenQuestion {
  qid: string;
  type: QuestionType;
  text: string;
  required: boolean;
  options: ScreenOption[];
  rows: string[];
  settings: {
    min?: number;
    max?: number;
    minlength?: number;
    maxlength?: number;
    format?: "pincode" | "phone" | "email";
    low_label?: string;
    high_label?: string;
  };
}

/** What the respondent has typed or picked so far on one screen. */
export interface AnswerDraft {
  value: unknown;
  other_text: string | null;
}

export interface QuestionScreen {
  kind: "question";
  survey_title: string;
  is_test: boolean;
  progress: number;
  previous_qid: string | null;
  question: ScreenQuestion;
  answer: AnswerDraft | null;
}

export interface EndScreen {
  kind: "end";
  survey_title: string;
  is_test: boolean;
  progress: number | null;
  end: "completed" | "already_completed" | "not_eligible" | "closed";
  title: string;
  message: string;
  reasons?: string | null;
}

export type Screen = QuestionScreen | EndScreen;

export interface PublicSurvey {
  slug: string;
  title: string;
  open: boolean;
  message: string | null;
}
