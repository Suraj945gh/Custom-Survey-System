// /login  Staff log in. The demo accounts from the seed script can be filled in with one tap.
import { useState, type FormEvent } from "react";
import { Navigate, useNavigate, useSearchParams } from "react-router-dom";
import { LogIn } from "lucide-react";
import { Button, Card, Field, inputClass } from "../components/ui";
import { useAuth } from "../lib/auth";
import { Logo } from "./StaffLayout";

const DEMO = [
  { role: "Admin", email: "admin@demo.local", password: "admin12345", note: "can approve, go live and close" },
  { role: "Researcher", email: "researcher@demo.local", password: "research12345", note: "uploads, checks and previews" },
];

export function LoginPage() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const next = params.get("next") || "/surveys";

  if (user) return <Navigate to={next} replace />;

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!email.trim() || !password) {
      setError("Please enter your email and password.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await login(email, password);
      navigate(next, { replace: true });
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-dvh items-center justify-center bg-gradient-to-br from-indigo-50 via-white to-slate-100 px-4 py-10">
      <div className="w-full max-w-sm">
        <div className="mb-8 flex justify-center"><Logo /></div>
        <Card className="p-6 sm:p-8">
          <h1 className="text-xl font-bold tracking-tight">Welcome back</h1>
          <p className="mt-1 text-sm text-slate-500">Log in to manage your surveys.</p>
          <form onSubmit={submit} className="mt-6 space-y-4" noValidate>
            <Field label="Email" htmlFor="email">
              <input id="email" type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} className={inputClass} />
            </Field>
            <Field label="Password" htmlFor="password">
              <input id="password" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} className={inputClass} />
            </Field>
            {error && <p role="alert" className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p>}
            <Button type="submit" className="w-full" loading={busy} icon={<LogIn className="size-4" />}>Log in</Button>
          </form>
        </Card>
        <div className="mt-6 rounded-2xl bg-white/70 p-4 ring-1 ring-slate-200">
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Demo accounts</p>
          <div className="mt-3 space-y-2">
            {DEMO.map((d) => (
              <button
                key={d.email}
                type="button"
                onClick={() => { setEmail(d.email); setPassword(d.password); setError(null); }}
                className="flex w-full items-center justify-between rounded-xl bg-white px-3 py-2.5 text-left text-sm ring-1 ring-slate-200 transition-colors hover:ring-indigo-300"
              >
                <span><span className="font-semibold text-slate-900">{d.role}</span> <span className="text-slate-500">· {d.note}</span></span>
                <span className="text-xs font-medium text-indigo-600">Use</span>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
