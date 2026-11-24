// The app's entry point: which page shows for which address.
//   Staff (login needed):   /login  /surveys  /surveys/new  /surveys/:id  /users
//   Respondents (public):   /s/:slug (join with phone)   /r/:token (their personal link)
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Link, Navigate, Route, Routes } from "react-router-dom";
import "./index.css";
import { ToastProvider } from "./components/ui";
import { AuthProvider } from "./lib/auth";
import { JoinPage } from "./respondent/JoinPage";
import { SurveyPage } from "./respondent/SurveyPage";
import { LoginPage } from "./staff/LoginPage";
import { NewSurveyPage } from "./staff/NewSurveyPage";
import { RequireStaff } from "./staff/StaffLayout";
import { SurveyDetailPage } from "./staff/SurveyDetailPage";
import { SurveyListPage } from "./staff/SurveyListPage";
import { UsersPage } from "./staff/UsersPage";

function NotFound() {
  return (
    <div className="flex min-h-dvh flex-col items-center justify-center gap-3 p-6 text-center">
      <p className="text-5xl font-bold text-slate-300">404</p>
      <p className="text-slate-600">This page doesn't exist.</p>
      <Link to="/" className="text-sm font-semibold text-indigo-600">Go to the start</Link>
    </div>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <ToastProvider>
        <AuthProvider>
          <Routes>
            <Route path="/s/:slug" element={<JoinPage />} />
            <Route path="/r/:token" element={<SurveyPage />} />
            <Route path="/login" element={<LoginPage />} />
            <Route element={<RequireStaff />}>
              <Route path="/surveys" element={<SurveyListPage />} />
              <Route path="/surveys/new" element={<NewSurveyPage />} />
              <Route path="/surveys/:id" element={<SurveyDetailPage />} />
              <Route path="/users" element={<UsersPage />} />
            </Route>
            <Route path="/" element={<Navigate to="/surveys" replace />} />
            <Route path="*" element={<NotFound />} />
          </Routes>
        </AuthProvider>
      </ToastProvider>
    </BrowserRouter>
  </StrictMode>,
);
