// Shared building blocks. Every screen uses these, so loading, empty and error states look the same everywhere.
import {
  createContext, useCallback, useContext, useEffect, useRef, useState,
  type ButtonHTMLAttributes, type ReactNode,
} from "react";
import { AlertTriangle, CheckCircle2, Info, Loader2, RefreshCw, X } from "lucide-react";
import type { SurveyStatus } from "../lib/types";
import { STATUS_LABEL } from "../lib/format";

export function cx(...classes: (string | false | null | undefined)[]) {
  return classes.filter(Boolean).join(" ");
}

// ---------------------------------------------------------------- buttons

type Variant = "primary" | "secondary" | "ghost" | "danger" | "success";
const VARIANTS: Record<Variant, string> = {
  primary: "bg-indigo-600 text-white shadow-sm hover:bg-indigo-700 active:bg-indigo-800 disabled:bg-indigo-300",
  secondary: "bg-white text-slate-700 ring-1 ring-slate-300 shadow-sm hover:bg-slate-50 active:bg-slate-100 disabled:text-slate-400",
  ghost: "text-slate-600 hover:bg-slate-100 active:bg-slate-200 disabled:text-slate-300",
  danger: "bg-rose-600 text-white shadow-sm hover:bg-rose-700 active:bg-rose-800 disabled:bg-rose-300",
  success: "bg-emerald-600 text-white shadow-sm hover:bg-emerald-700 active:bg-emerald-800 disabled:bg-emerald-300",
};

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: "sm" | "md" | "lg";
  loading?: boolean;
  icon?: ReactNode;
}

export function Button({ variant = "primary", size = "md", loading, icon, className, children, disabled, ...rest }: ButtonProps) {
  const sizes = { sm: "h-8 px-3 text-sm gap-1.5", md: "h-10 px-4 text-sm gap-2", lg: "h-13 px-6 text-base gap-2" };
  return (
    <button
      type="button"
      className={cx(
        "inline-flex select-none items-center justify-center rounded-xl font-semibold transition-colors disabled:cursor-not-allowed",
        sizes[size], VARIANTS[variant], className,
      )}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...rest}
    >
      {loading ? <Loader2 className="size-4 animate-spin" aria-hidden /> : icon}
      {children}
    </button>
  );
}

// ---------------------------------------------------------------- layout pieces

export function Card({ className, children }: { className?: string; children: ReactNode }) {
  return <div className={cx("rounded-2xl bg-white shadow-sm ring-1 ring-slate-200", className)}>{children}</div>;
}

export function Spinner({ label = "Loading…", className }: { label?: string; className?: string }) {
  return (
    <div role="status" className={cx("flex items-center justify-center gap-2 text-sm text-slate-500", className)}>
      <Loader2 className="size-5 animate-spin text-indigo-500" aria-hidden />
      <span>{label}</span>
    </div>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cx("animate-pulse rounded-lg bg-slate-200/80", className)} aria-hidden />;
}

export function ErrorBox({ title = "Something went wrong", message, onRetry }: { title?: string; message: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="flex items-start gap-3 rounded-2xl bg-rose-50 p-4 text-rose-900 ring-1 ring-rose-200">
      <AlertTriangle className="mt-0.5 size-5 shrink-0 text-rose-500" aria-hidden />
      <div className="min-w-0 flex-1">
        <p className="font-semibold">{title}</p>
        <p className="mt-0.5 text-sm text-rose-800">{message}</p>
        {onRetry && (
          <Button variant="secondary" size="sm" className="mt-3" icon={<RefreshCw className="size-3.5" />} onClick={onRetry}>
            Try again
          </Button>
        )}
      </div>
    </div>
  );
}

export function EmptyState({ icon, title, text, action }: { icon: ReactNode; title: string; text: string; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center rounded-2xl border-2 border-dashed border-slate-200 px-6 py-12 text-center">
      <div className="flex size-12 items-center justify-center rounded-2xl bg-indigo-50 text-indigo-600">{icon}</div>
      <h3 className="mt-4 font-semibold text-slate-900">{title}</h3>
      <p className="mt-1 max-w-sm text-sm text-slate-500">{text}</p>
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

export function Notice({ tone = "info", children }: { tone?: "info" | "warning" | "success"; children: ReactNode }) {
  const styles = {
    info: ["bg-indigo-50 text-indigo-900 ring-indigo-200", <Info key="i" className="size-4 text-indigo-500" />],
    warning: ["bg-amber-50 text-amber-900 ring-amber-200", <AlertTriangle key="w" className="size-4 text-amber-500" />],
    success: ["bg-emerald-50 text-emerald-900 ring-emerald-200", <CheckCircle2 key="s" className="size-4 text-emerald-500" />],
  } as const;
  const [classes, icon] = styles[tone];
  return (
    <div className={cx("flex items-start gap-2.5 rounded-xl px-3.5 py-3 text-sm ring-1", classes)}>
      <span className="mt-0.5 shrink-0">{icon}</span>
      <div className="min-w-0">{children}</div>
    </div>
  );
}

// ---------------------------------------------------------------- status and progress

const STATUS_STYLE: Record<SurveyStatus, string> = {
  draft: "bg-slate-100 text-slate-700 ring-slate-300",
  live: "bg-emerald-50 text-emerald-700 ring-emerald-300",
  closed: "bg-rose-50 text-rose-700 ring-rose-200",
};

export function StatusChip({ status }: { status: SurveyStatus }) {
  return (
    <span className={cx("inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1", STATUS_STYLE[status])}>
      {status === "live" && (
        <span className="relative flex size-2">
          <span className="absolute inline-flex size-full animate-ping rounded-full bg-emerald-400 opacity-75" />
          <span className="relative inline-flex size-2 rounded-full bg-emerald-500" />
        </span>
      )}
      {STATUS_LABEL[status]}
    </span>
  );
}

export function Badge({ children, tone = "slate" }: { children: ReactNode; tone?: "slate" | "indigo" | "amber" | "rose" | "emerald" }) {
  const tones = {
    slate: "bg-slate-100 text-slate-700", indigo: "bg-indigo-50 text-indigo-700", amber: "bg-amber-50 text-amber-800",
    rose: "bg-rose-50 text-rose-700", emerald: "bg-emerald-50 text-emerald-700",
  };
  return <span className={cx("inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs font-medium", tones[tone])}>{children}</span>;
}

export function ProgressBar({ value, tone = "indigo", className, label }: { value: number; tone?: "indigo" | "emerald" | "amber" | "rose"; className?: string; label?: string }) {
  const tones = { indigo: "bg-indigo-500", emerald: "bg-emerald-500", amber: "bg-amber-500", rose: "bg-rose-500" };
  const pct = Math.max(0, Math.min(100, value));
  return (
    <div
      className={cx("h-2 overflow-hidden rounded-full bg-slate-200", className)}
      role="progressbar" aria-valuenow={Math.round(pct)} aria-valuemin={0} aria-valuemax={100} aria-label={label}
    >
      <div className={cx("h-full rounded-full transition-[width] duration-500 ease-out", tones[tone])} style={{ width: `${pct}%` }} />
    </div>
  );
}

// ---------------------------------------------------------------- dialogs

interface DialogProps {
  open: boolean;
  title: string;
  children?: ReactNode;
  confirmLabel: string;
  tone?: "primary" | "danger" | "success";
  onConfirm: () => Promise<void> | void;
  onClose: () => void;
}

/** A confirm dialog. Shows its own loading state and any error from onConfirm. */
export function ConfirmDialog({ open, title, children, confirmLabel, tone = "primary", onConfirm, onClose }: DialogProps) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) {
      setError(null);
      dialog.showModal?.();
    }
    if (!open && dialog.open) dialog.close?.();
  }, [open]);

  async function confirm() {
    setBusy(true);
    setError(null);
    try {
      await onConfirm();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "That didn't work.");
    } finally {
      setBusy(false);
    }
  }

  if (!open) return null;
  return (
    <dialog
      ref={ref}
      onClose={onClose}
      onCancel={(e) => { if (busy) e.preventDefault(); }}
      className="m-auto w-[calc(100%-2rem)] max-w-md rounded-2xl bg-white p-0 shadow-2xl backdrop:bg-slate-900/40 backdrop:backdrop-blur-sm"
    >
      <div className="p-6">
        <div className="flex items-start justify-between gap-4">
          <h2 className="text-lg font-semibold text-slate-900">{title}</h2>
          <button type="button" onClick={onClose} className="-m-1 rounded-lg p-1 text-slate-400 hover:bg-slate-100" aria-label="Close">
            <X className="size-5" />
          </button>
        </div>
        <div className="mt-2 space-y-3 text-sm text-slate-600">{children}</div>
        {error && <p role="alert" className="mt-4 rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p>}
        <div className="mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <Button variant="secondary" onClick={onClose} disabled={busy}>Cancel</Button>
          <Button variant={tone} onClick={confirm} loading={busy}>{confirmLabel}</Button>
        </div>
      </div>
    </dialog>
  );
}

// ---------------------------------------------------------------- toasts (short "Saved" / "Copied" messages)

interface Toast { id: number; text: string; tone: "success" | "error" }
const ToastContext = createContext<(text: string, tone?: Toast["tone"]) => void>(() => {});

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const show = useCallback((text: string, tone: Toast["tone"] = "success") => {
    const id = Date.now() + Math.random();
    setToasts((list) => [...list, { id, text, tone }]);
    setTimeout(() => setToasts((list) => list.filter((t) => t.id !== id)), 3500);
  }, []);
  return (
    <ToastContext.Provider value={show}>
      {children}
      <div className="pointer-events-none fixed inset-x-0 bottom-4 z-50 flex flex-col items-center gap-2 px-4" aria-live="polite">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={cx(
              "pointer-events-auto flex animate-enter items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-medium text-white shadow-lg",
              t.tone === "success" ? "bg-slate-900" : "bg-rose-600",
            )}
          >
            {t.tone === "success" ? <CheckCircle2 className="size-4 text-emerald-400" /> : <AlertTriangle className="size-4" />}
            {t.text}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export const useToast = () => useContext(ToastContext);

// ---------------------------------------------------------------- form field

export function Field({ label, hint, error, children, htmlFor }: { label: string; hint?: string; error?: string | null; children: ReactNode; htmlFor?: string }) {
  return (
    <div>
      <label htmlFor={htmlFor} className="block text-sm font-medium text-slate-700">{label}</label>
      <div className="mt-1.5">{children}</div>
      {error ? <p className="mt-1.5 text-sm text-rose-600">{error}</p> : hint ? <p className="mt-1.5 text-xs text-slate-500">{hint}</p> : null}
    </div>
  );
}

export const inputClass =
  "block w-full rounded-xl border-0 bg-white px-3.5 py-2.5 text-slate-900 shadow-sm ring-1 ring-slate-300 placeholder:text-slate-400 focus:ring-2 focus:ring-indigo-500 focus:outline-none disabled:bg-slate-50 disabled:text-slate-500";
