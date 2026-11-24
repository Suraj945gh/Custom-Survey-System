// The frame around every respondent screen: full screen on a phone, a centred card on a computer.
import type { ReactNode } from "react";
import { cx } from "../components/ui";

export function RespondentShell({ children, footer, header, testRun }: {
  children: ReactNode; footer?: ReactNode; header?: ReactNode; testRun?: boolean;
}) {
  return (
    <div className="min-h-dvh bg-gradient-to-b from-indigo-50 via-slate-50 to-slate-100 sm:py-8">
      <div
        className={cx(
          "mx-auto flex min-h-dvh w-full max-w-lg flex-col bg-white sm:min-h-[calc(100dvh-4rem)] sm:rounded-3xl sm:shadow-xl sm:ring-1 sm:ring-slate-200",
        )}
      >
        {testRun && (
          <div className="rounded-t-none bg-amber-400 px-4 py-1.5 text-center text-xs font-semibold text-amber-950 sm:rounded-t-3xl">
            Test run: these answers are never counted
          </div>
        )}
        {header}
        <main className="flex flex-1 flex-col px-5 pb-6 pt-4 sm:px-8">{children}</main>
        {footer && (
          <footer className="sticky bottom-0 border-t border-slate-100 bg-white/95 px-5 py-4 pb-[max(1rem,env(safe-area-inset-bottom))] backdrop-blur sm:rounded-b-3xl sm:px-8">
            {footer}
          </footer>
        )}
      </div>
    </div>
  );
}

export function Brand() {
  return (
    <span className="inline-flex items-center gap-2 text-sm font-semibold text-slate-700">
      <span className="flex size-6 items-center justify-center rounded-lg bg-indigo-600 text-[11px] font-bold text-white">C</span>
      Concave Insights
    </span>
  );
}
