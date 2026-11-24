// /s/:slug  The shareable survey page. The person enters a phone number and gets their own link.
// Same phone again = the same link (resume). Completed any survey in the last 90 days = not yet.
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowRight, CalendarClock, Clock3, Lock, SearchX, ShieldCheck } from "lucide-react";
import { Button, ErrorBox, Skeleton, cx } from "../components/ui";
import { ApiError, api } from "../lib/api";
import { formatDate } from "../lib/format";
import type { PublicSurvey } from "../lib/types";
import { Brand, RespondentShell } from "./Shell";
import { normalisePhone } from "./validate";

type Blocked = { kind: "cool_off"; date: string } | { kind: "closed"; message: string } | { kind: "missing" };

export function JoinPage() {
  const { slug = "" } = useParams();
  const navigate = useNavigate();
  const [info, setInfo] = useState<PublicSurvey | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [blocked, setBlocked] = useState<Blocked | null>(null);
  const [phone, setPhone] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    setLoadError(null);
    api.surveyInfo(slug)
      .then((data) => {
        setInfo(data);
        if (!data.open) setBlocked({ kind: "closed", message: data.message ?? "This survey is closed." });
      })
      .catch((err: ApiError) => (err.status === 404 ? setBlocked({ kind: "missing" }) : setLoadError(err.message)));
  }, [slug]);

  useEffect(load, [load]);

  async function start(e: FormEvent) {
    e.preventDefault();
    if (!normalisePhone(phone)) {
      setError("Please enter a valid 10-digit mobile number.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const { token } = await api.join(slug, phone);
      navigate(`/r/${token}`, { replace: true });
    } catch (err) {
      const apiError = err as ApiError;
      if (apiError.code === "cool_off") setBlocked({ kind: "cool_off", date: String(apiError.data.eligible_from) });
      else if (apiError.code === "closed") setBlocked({ kind: "closed", message: apiError.message });
      else setError(apiError.message);
    } finally {
      setBusy(false);
    }
  }

  const header = <header className="px-5 pt-5 sm:px-8 sm:pt-7"><Brand /></header>;

  if (loadError) {
    return <RespondentShell header={header}><div className="my-auto"><ErrorBox message={loadError} onRetry={load} /></div></RespondentShell>;
  }
  if (blocked) {
    return <RespondentShell header={header}><BlockedView blocked={blocked} title={info?.title} /></RespondentShell>;
  }
  if (!info) {
    return (
      <RespondentShell header={header}>
        <div className="space-y-4 pt-10"><Skeleton className="h-8 w-3/4" /><Skeleton className="h-4 w-full" /><Skeleton className="h-14 w-full" /></div>
      </RespondentShell>
    );
  }

  return (
    <RespondentShell header={header}>
      <form onSubmit={start} className="flex flex-1 animate-enter flex-col">
        <div className="pt-8">
          <p className="text-xs font-semibold uppercase tracking-wider text-indigo-600">You're invited</p>
          <h1 className="mt-2 text-[28px] font-bold leading-tight tracking-tight text-slate-900">{info.title}</h1>
          <ul className="mt-5 space-y-2.5 text-[15px] text-slate-600">
            <li className="flex items-center gap-2.5"><Clock3 className="size-5 text-indigo-500" /> One short question at a time</li>
            <li className="flex items-center gap-2.5"><ShieldCheck className="size-5 text-indigo-500" /> Your answers save as you go, so you can stop and come back</li>
          </ul>
        </div>

        <div className="mt-10">
          <label htmlFor="phone" className="block text-sm font-semibold text-slate-800">Your mobile number</label>
          <div className={cx("mt-2 flex items-center rounded-2xl bg-white ring-1 transition-shadow focus-within:ring-2 focus-within:ring-indigo-500", error ? "ring-rose-400" : "ring-slate-300")}>
            <span className="pl-4 pr-1 text-lg font-semibold text-slate-500">+91</span>
            <input
              id="phone"
              type="tel"
              inputMode="tel"
              autoComplete="tel-national"
              placeholder="98765 43210"
              maxLength={16}
              value={phone}
              onChange={(e) => { setPhone(e.target.value); setError(null); }}
              className="block w-full min-w-0 rounded-2xl border-0 bg-transparent py-3.5 pl-2 pr-4 text-lg font-semibold tracking-wider text-slate-900 outline-none placeholder:font-medium placeholder:text-slate-400"
              aria-invalid={Boolean(error)}
              aria-describedby="phone-help"
            />
          </div>
          {error ? (
            <p id="phone-help" role="alert" className="mt-2 text-sm font-medium text-rose-600">{error}</p>
          ) : (
            <p id="phone-help" className="mt-2 text-xs text-slate-500">
              Used only to give you your own link and to make sure each person answers once. It's never shown to anyone.
            </p>
          )}
        </div>

        <div className="mt-auto pt-8">
          <Button type="submit" size="lg" className="w-full" loading={busy}>
            Start survey {!busy && <ArrowRight className="size-5" />}
          </Button>
        </div>
      </form>
    </RespondentShell>
  );
}

function BlockedView({ blocked, title }: { blocked: Blocked; title?: string }) {
  const view = {
    missing: { icon: SearchX, tone: "bg-slate-100 text-slate-600", heading: "Survey not found", text: "This link doesn't match any open survey. Please check the link you were sent." },
    closed: { icon: Lock, tone: "bg-amber-100 text-amber-700", heading: "This survey is closed", text: blocked.kind === "closed" ? blocked.message : "" },
    cool_off: {
      icon: CalendarClock, tone: "bg-indigo-100 text-indigo-600", heading: "Thanks for coming back!",
      text: blocked.kind === "cool_off" ? `You took part in one of our surveys recently. To keep results fair, you can join again from ${formatDate(blocked.date)}.` : "",
    },
  }[blocked.kind];
  const Icon = view.icon;
  return (
    <div className="flex flex-1 animate-enter flex-col items-center justify-center py-10 text-center">
      <div className={cx("flex size-20 items-center justify-center rounded-full", view.tone)}><Icon className="size-10" /></div>
      <h1 className="mt-6 text-2xl font-bold tracking-tight">{view.heading}</h1>
      <p className="mt-2 max-w-xs text-[15px] leading-relaxed text-slate-600">{view.text}</p>
      {title && <p className="mt-6 text-sm text-slate-400">{title}</p>}
    </div>
  );
}
