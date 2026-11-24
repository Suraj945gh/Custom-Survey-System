// One small wrapper around fetch() for every call to the Python API.
// - adds the login token (staff only)
// - turns any failure into an ApiError with a message that can be shown as-is
import type {
  CheckResult, Dashboard, Issue, PublicSurvey, Screen, SurveyDetail, SurveySummary, User, VersionDetail,
} from "./types";

export class ApiError extends Error {
  status: number;
  code?: string;
  issues?: Issue[];
  data: Record<string, unknown>;

  constructor(status: number, message: string, data: Record<string, unknown> = {}) {
    super(message);
    this.status = status;
    this.data = data;
    this.code = typeof data.code === "string" ? data.code : undefined;
    this.issues = Array.isArray(data.issues) ? (data.issues as Issue[]) : undefined;
  }
}

// ---------------------------------------------------------------- login token (kept in the browser)

const TOKEN_KEY = "concave.staff.token";

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null; // private mode or blocked storage: just behave as logged out
  }
}

export function setToken(token: string | null) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* ignore */
  }
}

let onUnauthorized: (() => void) | null = null;
export function setUnauthorizedHandler(handler: (() => void) | null) {
  onUnauthorized = handler;
}

// ---------------------------------------------------------------- the request helper

function messageFrom(data: Record<string, unknown>, status: number): string {
  const detail = data.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail[0]?.msg) return String(detail[0].msg).replace(/^Value error, /, "");
  if (status >= 500) return "Something went wrong on the server. Please try again.";
  return "That didn't work. Please try again.";
}

async function send(method: string, path: string, body?: unknown): Promise<Response> {
  const headers: Record<string, string> = {};
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  let payload: BodyInit | undefined;
  if (body instanceof FormData) payload = body;
  else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }
  let response: Response;
  try {
    response = await fetch(`/api${path}`, { method, headers, body: payload });
  } catch {
    throw new ApiError(0, "Can't reach the server. Check your internet connection and try again.");
  }
  if (response.status === 401 && token && onUnauthorized) onUnauthorized();
  if (!response.ok) {
    let data: Record<string, unknown> = {};
    try {
      data = await response.json();
    } catch {
      /* not JSON */
    }
    throw new ApiError(response.status, messageFrom(data, response.status), data);
  }
  return response;
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const response = await send(method, path, body);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

/** Download a file (export) using the login token, then save it with the server's file name. */
async function download(path: string, fallbackName: string) {
  const response = await send("GET", path);
  const blob = await response.blob();
  const disposition = response.headers.get("Content-Disposition") ?? "";
  const name = /filename="([^"]+)"/.exec(disposition)?.[1] ?? fallbackName;
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

// ---------------------------------------------------------------- every API call in one place

export const api = {
  // staff: login
  login: (email: string, password: string) =>
    request<{ token: string; user: User }>("POST", "/auth/login", { email, password }),
  me: () => request<User>("GET", "/auth/me"),

  // staff: surveys
  listSurveys: () => request<SurveySummary[]>("GET", "/surveys"),
  getSurvey: (id: number) => request<SurveyDetail>("GET", `/surveys/${id}`),
  check: (text: string) => request<CheckResult>("POST", "/check", { text }),
  createDraft: (text: string, fileName?: string | null) =>
    request<SurveyDetail>("POST", "/surveys", { text, file_name: fileName ?? null }),
  updateDraft: (id: number, text: string, fileName?: string | null) =>
    request<SurveyDetail>("PUT", `/surveys/${id}/draft`, { text, file_name: fileName ?? null }),
  discardDraft: (id: number) => request<void>("DELETE", `/surveys/${id}/draft`),
  version: (id: number, no: number) => request<VersionDetail>("GET", `/surveys/${id}/versions/${no}`),
  approve: (id: number) => request<SurveyDetail>("POST", `/surveys/${id}/approve`),
  goLive: (id: number, deadline?: string) =>
    request<SurveyDetail>("POST", `/surveys/${id}/go-live`, deadline ? { deadline } : {}),
  setDeadline: (id: number, deadline: string) => request<SurveyDetail>("PATCH", `/surveys/${id}/deadline`, { deadline }),
  close: (id: number) => request<SurveyDetail>("POST", `/surveys/${id}/close`),
  testRun: (id: number, useDraft?: boolean) =>
    request<{ token: string; version_no: number | null; is_draft: boolean }>(
      "POST", `/surveys/${id}/test-runs`, useDraft === undefined ? {} : { use_draft: useDraft },
    ),
  dashboard: (id: number) => request<Dashboard>("GET", `/surveys/${id}/dashboard`),
  exportFile: (id: number, slug: string, format: "csv" | "xlsx") =>
    download(`/surveys/${id}/export?format=${format}`, `${slug}_completes.${format}`),
  network: () => request<{ addresses: string[] }>("GET", "/meta/network"),

  // staff: users (admin)
  listUsers: () => request<User[]>("GET", "/users"),
  createUser: (body: { email: string; name: string; role: string; password: string }) =>
    request<User>("POST", "/users", body),

  // respondents (no login)
  surveyInfo: (slug: string) => request<PublicSurvey>("GET", `/public/surveys/${encodeURIComponent(slug)}`),
  join: (slug: string, phone: string) =>
    request<{ token: string; resumed: boolean }>("POST", `/public/surveys/${encodeURIComponent(slug)}/join`, { phone }),
  screen: (token: string) => request<Screen>("GET", `/public/r/${encodeURIComponent(token)}`),
  question: (token: string, qid: string) =>
    request<Screen>("GET", `/public/r/${encodeURIComponent(token)}/questions/${encodeURIComponent(qid)}`),
  answer: (token: string, qid: string, value: unknown, otherText: string | null) =>
    request<Screen>("POST", `/public/r/${encodeURIComponent(token)}/answers`, { qid, value, other_text: otherText }),
};
