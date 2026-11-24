// Instant checks in the browser, so the respondent sees a problem without waiting for the server.
// The server checks everything again (backend/app/engine/answers.py); its message wins if they ever differ.
import type { AnswerDraft, ScreenQuestion } from "../lib/types";

const PINCODE = /^[1-9]\d{5}$/;
const EMAIL = /^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$/;

export function normalisePhone(raw: string): string | null {
  let digits = raw.replace(/[\s\-().]/g, "");
  if (digits.startsWith("+91")) digits = digits.slice(3);
  else if (digits.length === 12 && digits.startsWith("91")) digits = digits.slice(2);
  else if (digits.length === 11 && digits.startsWith("0")) digits = digits.slice(1);
  return /^[6-9]\d{9}$/.test(digits) ? digits : null;
}

function isEmpty(value: unknown): boolean {
  if (value === null || value === undefined) return true;
  if (typeof value === "string") return value.trim() === "";
  if (Array.isArray(value)) return value.length === 0;
  if (typeof value === "object") return Object.keys(value as object).length === 0;
  return false;
}

/** The value to send to the server for this question, or a message saying what is missing. */
export function checkAnswer(question: ScreenQuestion, draft: AnswerDraft): string | null {
  const { type, settings: s, required } = question;
  const value = draft.value;
  if (type === "info") return null;
  if (isEmpty(value)) return required ? (type === "multi" ? "Please choose at least one option." : "Please answer this question.") : null;

  const otherPicked = question.options.some(
    (o) => o.other && (Array.isArray(value) ? value.includes(o.value) : value === o.value),
  );
  if (otherPicked && !draft.other_text?.trim()) return "Please type your answer in the box.";

  switch (type) {
    case "multi": {
      const picked = value as string[];
      if (s.max !== undefined && picked.length > s.max) return `Please choose at most ${s.max}.`;
      if (s.min !== undefined && picked.length < s.min) return `Please choose at least ${s.min}.`;
      return null;
    }
    case "number": {
      const n = Number(String(value).replace(/,/g, "").trim());
      if (!Number.isFinite(n)) return "Please enter a number.";
      if (s.min !== undefined && s.max !== undefined && (n < s.min || n > s.max)) return `Please enter a number from ${s.min} to ${s.max}.`;
      if (s.min !== undefined && n < s.min) return `Please enter ${s.min} or more.`;
      if (s.max !== undefined && n > s.max) return `Please enter ${s.max} or less.`;
      return null;
    }
    case "text":
    case "longtext": {
      const length = String(value).trim().length;
      if (s.minlength && length < s.minlength) return `Please write at least ${s.minlength} characters (${length} so far).`;
      if (s.maxlength && length > s.maxlength) return `Please keep it under ${s.maxlength} characters.`;
      return null;
    }
    case "formatted": {
      const text = String(value).trim();
      if (s.format === "pincode" && !PINCODE.test(text.replace(/\s/g, ""))) return "Please enter a valid 6-digit pincode.";
      if (s.format === "phone" && !normalisePhone(text)) return "Please enter a valid 10-digit mobile number.";
      if (s.format === "email" && !EMAIL.test(text)) return "Please enter a valid email address.";
      return null;
    }
    case "matrix": {
      const answered = Object.values(value as Record<string, string>).filter(Boolean).length;
      const left = question.rows.length - answered;
      if (required && left > 0) return `Please answer every row (${left} left).`;
      return null;
    }
    default:
      return null;
  }
}

/** Multi select: what happens when an option is tapped. Exclusive options ("None of these") clear the rest. */
export function toggleOption(question: ScreenQuestion, picked: string[], value: string): string[] {
  const option = question.options.find((o) => o.value === value);
  if (picked.includes(value)) return picked.filter((v) => v !== value);
  if (option?.exclusive) return [value];
  const withoutExclusive = picked.filter((v) => !question.options.find((o) => o.value === v)?.exclusive);
  const max = question.settings.max;
  if (max !== undefined && withoutExclusive.length >= max) return withoutExclusive; // full: ignore the tap
  return [...withoutExclusive, value];
}

/** An empty answer of the right shape for each question type. */
export function emptyValue(question: ScreenQuestion): unknown {
  if (question.type === "multi") return [];
  if (question.type === "matrix") return {};
  return null;
}
