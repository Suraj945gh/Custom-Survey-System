// Small helpers for showing dates and statuses in plain words.
import type { ClosedReason, SurveyStatus } from "./types";

const dateFormat = new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short", year: "numeric" });
const dateTimeFormat = new Intl.DateTimeFormat("en-IN", {
  day: "numeric", month: "short", year: "numeric", hour: "numeric", minute: "2-digit",
});

export const formatDate = (iso: string | null | undefined) => (iso ? dateFormat.format(new Date(iso)) : "—");
export const formatDateTime = (iso: string | null | undefined) => (iso ? dateTimeFormat.format(new Date(iso)) : "—");

/** "in 12 days", "in 3 hours", "2 days ago" */
export function relative(iso: string | null | undefined, now = Date.now()): string {
  if (!iso) return "";
  const diff = new Date(iso).getTime() - now;
  const abs = Math.abs(diff);
  const units: [number, string][] = [[86_400_000, "day"], [3_600_000, "hour"], [60_000, "minute"]];
  for (const [ms, name] of units) {
    if (abs >= ms) {
      const n = Math.round(abs / ms);
      const label = `${n} ${name}${n === 1 ? "" : "s"}`;
      return diff > 0 ? `in ${label}` : `${label} ago`;
    }
  }
  return diff > 0 ? "in a moment" : "just now";
}

export const STATUS_LABEL: Record<SurveyStatus, string> = { draft: "Draft", live: "Live", closed: "Closed" };

export const CLOSED_LABEL: Record<ClosedReason, string> = {
  closed_by_team: "Closed by the team",
  deadline_passed: "Deadline passed",
  target_reached: "Target reached",
};

/** Default deadline for the "Go live" dialog: today + 15 days, as a value for <input type="datetime-local">. */
export function localInputValue(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

export function plural(n: number, word: string, many = `${word}s`) {
  return `${n} ${n === 1 ? word : many}`;
}
