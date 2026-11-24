// The frame around every staff page: a sidebar on a computer, a top bar with a menu on a phone.
import { useState, type ReactNode } from "react";
import { Navigate, NavLink, Outlet, useLocation } from "react-router-dom";
import { ClipboardList, LogOut, Menu, Users, X } from "lucide-react";
import { Badge, Spinner, cx } from "../components/ui";
import { isAdmin, useAuth } from "../lib/auth";

export function RequireStaff() {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <div className="flex min-h-dvh items-center justify-center"><Spinner label="Opening…" /></div>;
  if (!user) return <Navigate to={`/login?next=${encodeURIComponent(location.pathname + location.search)}`} replace />;
  return <StaffLayout />;
}

function StaffLayout() {
  const { user, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const links = [
    { to: "/surveys", label: "Surveys", icon: ClipboardList },
    ...(isAdmin(user) ? [{ to: "/users", label: "Team", icon: Users }] : []),
  ];

  const nav = (
    <nav className="flex flex-1 flex-col gap-1">
      {links.map(({ to, label, icon: Icon }) => (
        <NavLink
          key={to}
          to={to}
          onClick={() => setOpen(false)}
          className={({ isActive }) => cx(
            "flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-colors",
            isActive ? "bg-indigo-50 text-indigo-700" : "text-slate-600 hover:bg-slate-100 hover:text-slate-900",
          )}
        >
          <Icon className="size-5" /> {label}
        </NavLink>
      ))}
    </nav>
  );

  const account = user && (
    <div className="flex items-center gap-3 rounded-xl bg-slate-50 p-3 ring-1 ring-slate-200">
      <div className="flex size-9 shrink-0 items-center justify-center rounded-full bg-indigo-600 text-sm font-bold text-white">
        {user.name.slice(0, 1).toUpperCase()}
      </div>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-semibold text-slate-900">{user.name}</p>
        <Badge tone={user.role === "admin" ? "indigo" : "slate"}>{user.role === "admin" ? "Admin" : "Researcher"}</Badge>
      </div>
      <button type="button" onClick={logout} className="rounded-lg p-2 text-slate-500 hover:bg-white hover:text-slate-900" aria-label="Log out" title="Log out">
        <LogOut className="size-4" />
      </button>
    </div>
  );

  return (
    <div className="min-h-dvh lg:flex">
      {/* Computer: fixed sidebar */}
      <aside className="sticky top-0 hidden h-dvh w-64 shrink-0 flex-col gap-6 border-r border-slate-200 bg-white p-4 lg:flex">
        <Logo />
        {nav}
        {account}
      </aside>

      {/* Phone: top bar + slide-down menu */}
      <header className="sticky top-0 z-30 flex items-center justify-between border-b border-slate-200 bg-white/95 px-4 py-3 backdrop-blur lg:hidden">
        <Logo />
        <button type="button" onClick={() => setOpen(!open)} className="rounded-lg p-2 text-slate-600 hover:bg-slate-100" aria-label="Menu" aria-expanded={open}>
          {open ? <X className="size-5" /> : <Menu className="size-5" />}
        </button>
      </header>
      {open && (
        <div className="fixed inset-x-0 top-[57px] z-20 flex animate-enter flex-col gap-4 border-b border-slate-200 bg-white p-4 shadow-lg lg:hidden">
          {nav}
          {account}
        </div>
      )}

      <main className="min-w-0 flex-1 px-4 py-6 sm:px-6 lg:px-10 lg:py-8">
        <div className="mx-auto max-w-6xl"><Outlet /></div>
      </main>
    </div>
  );
}

export function Logo() {
  return (
    <span className="flex items-center gap-2.5 px-1">
      <span className="flex size-8 items-center justify-center rounded-xl bg-indigo-600 text-sm font-bold text-white shadow-sm">C</span>
      <span className="leading-tight">
        <span className="block text-sm font-bold text-slate-900">Concave Surveys</span>
        <span className="block text-xs text-slate-500">Research workspace</span>
      </span>
    </span>
  );
}

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div className="min-w-0">
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">{title}</h1>
        {subtitle && <div className="mt-1 text-sm text-slate-500">{subtitle}</div>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}
