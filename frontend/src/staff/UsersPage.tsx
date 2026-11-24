// /users  Admins add researchers and other admins.
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Navigate } from "react-router-dom";
import { UserPlus } from "lucide-react";
import { Badge, Button, Card, ErrorBox, Field, Skeleton, inputClass, useToast } from "../components/ui";
import { api } from "../lib/api";
import { isAdmin, useAuth } from "../lib/auth";
import type { Role, User } from "../lib/types";
import { PageHeader } from "./StaffLayout";

export function UsersPage() {
  const { user } = useAuth();
  const toast = useToast();
  const [users, setUsers] = useState<User[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({ name: "", email: "", role: "researcher" as Role, password: "" });
  const [formError, setFormError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    api.listUsers().then(setUsers).catch((err: Error) => setError(err.message));
  }, []);
  useEffect(load, [load]);

  if (!isAdmin(user)) return <Navigate to="/surveys" replace />;

  async function add(e: FormEvent) {
    e.preventDefault();
    if (form.password.length < 8) {
      setFormError("The password needs at least 8 characters.");
      return;
    }
    setBusy(true);
    setFormError(null);
    try {
      await api.createUser(form);
      toast(`${form.name} can now log in`);
      setForm({ name: "", email: "", role: "researcher", password: "" });
      load();
    } catch (err) {
      setFormError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <PageHeader title="Team" subtitle="Researchers upload, check, preview and export. Admins can also approve, go live and close." />
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <Card className="overflow-hidden">
          {error && <div className="p-4"><ErrorBox message={error} onRetry={load} /></div>}
          {!users && !error && <div className="space-y-2 p-4">{[0, 1].map((i) => <Skeleton key={i} className="h-12" />)}</div>}
          <ul className="divide-y divide-slate-100">
            {users?.map((u) => (
              <li key={u.id} className="flex items-center gap-3 px-4 py-3">
                <span className="flex size-9 items-center justify-center rounded-full bg-slate-100 text-sm font-bold text-slate-600">{u.name.slice(0, 1).toUpperCase()}</span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-semibold text-slate-900">{u.name}{u.id === user?.id && <span className="font-normal text-slate-400"> (you)</span>}</span>
                  <span className="block truncate text-xs text-slate-500">{u.email}</span>
                </span>
                <Badge tone={u.role === "admin" ? "indigo" : "slate"}>{u.role === "admin" ? "Admin" : "Researcher"}</Badge>
              </li>
            ))}
          </ul>
        </Card>
        <Card className="p-5">
          <h2 className="flex items-center gap-2 font-semibold"><UserPlus className="size-4 text-indigo-500" /> Add a person</h2>
          <form onSubmit={add} className="mt-4 space-y-3.5" noValidate>
            <Field label="Name" htmlFor="u-name"><input id="u-name" required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className={inputClass} /></Field>
            <Field label="Email" htmlFor="u-email"><input id="u-email" type="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} className={inputClass} /></Field>
            <Field label="Role" htmlFor="u-role">
              <select id="u-role" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value as Role })} className={inputClass}>
                <option value="researcher">Researcher</option>
                <option value="admin">Admin</option>
              </select>
            </Field>
            <Field label="Temporary password" htmlFor="u-pass" hint="At least 8 characters. Share it with them privately.">
              <input id="u-pass" type="password" autoComplete="new-password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} className={inputClass} />
            </Field>
            {formError && <p role="alert" className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">{formError}</p>}
            <Button type="submit" className="w-full" loading={busy}>Add person</Button>
          </form>
        </Card>
      </div>
    </div>
  );
}
