// The four end screens: Completed, Already completed, Not eligible, Survey closed.
import { CheckCircle2, HeartHandshake, Lock, ShieldCheck } from "lucide-react";
import type { EndScreen } from "../lib/types";
import { cx } from "../components/ui";

const LOOK = {
  completed: { icon: CheckCircle2, ring: "bg-emerald-100 text-emerald-600" },
  already_completed: { icon: ShieldCheck, ring: "bg-indigo-100 text-indigo-600" },
  not_eligible: { icon: HeartHandshake, ring: "bg-slate-100 text-slate-600" },
  closed: { icon: Lock, ring: "bg-amber-100 text-amber-700" },
} as const;

export function EndView({ screen }: { screen: EndScreen }) {
  const { icon: Icon, ring } = LOOK[screen.end];
  return (
    <div className="flex flex-1 animate-enter flex-col items-center justify-center py-10 text-center">
      <div className={cx("flex size-20 animate-pop items-center justify-center rounded-full", ring)}>
        <Icon className="size-10" aria-hidden />
      </div>
      <h1 className="mt-6 text-2xl font-bold tracking-tight text-slate-900">{screen.title}</h1>
      <p className="mt-2 max-w-xs text-[15px] leading-relaxed text-slate-600">{screen.message}</p>
      <p className="mt-6 text-sm text-slate-400">{screen.survey_title}</p>
      {screen.is_test && (
        <div className="mt-8 w-full rounded-2xl bg-amber-50 p-4 text-left text-sm ring-1 ring-amber-200">
          <p className="font-semibold text-amber-900">Test run result</p>
          <p className="mt-1 text-amber-800">
            {screen.reasons ? <>Ended because: <strong>{screen.reasons}</strong></> : "Finished without any termination rule."}
          </p>
          <p className="mt-2 text-xs text-amber-700">Real respondents never see this box.</p>
        </div>
      )}
    </div>
  );
}
