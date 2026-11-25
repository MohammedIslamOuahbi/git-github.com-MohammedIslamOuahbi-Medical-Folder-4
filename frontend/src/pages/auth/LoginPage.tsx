import { useState } from "react";
import type { FormEvent } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import axios from "axios";
import {
  CheckCircle2,
  Link2,
  Network,
  Server,
  Settings2,
  ShieldCheck,
} from "lucide-react";

import { Button } from "@/components/common/Button";
import { Card } from "@/components/common/Card";
import { Input } from "@/components/common/Input";
import { AuthProfileFetchError } from "@/context/AuthContext";
import { useAuth } from "@/hooks/useAuth";
import { useRuntimeConnection } from "@/hooks/useRuntimeConnection";
import { buildUserDashboardUid } from "@/utils/uid";
import {
  LOGIN_CONFIGURATION_PATH,
  buildLoginConnectionInfo,
} from "./loginConnectionInfo";

export const LoginPage = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { login } = useAuth();
  const runtimeConnection = useRuntimeConnection();

  const [form, setForm] = useState({
    email: "",
    password: "",
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const getLoginErrorMessage = (cause: unknown) => {
    if (cause instanceof AuthProfileFetchError) {
      return "Connexion réussie, mais impossible de charger votre profil. Réessayez.";
    }

    if (axios.isAxiosError(cause)) {
      const payload = cause.response?.data as
        | {
            detail?: { message?: string } | string;
            message?: string;
            details?: unknown;
          }
        | undefined;

      const backendMessage =
        payload?.message ||
        (payload?.detail && typeof payload.detail === "object"
          ? (payload.detail.message ?? "")
          : "") ||
        (typeof payload?.detail === "string" ? payload.detail : "");

      if (backendMessage) {
        if (backendMessage === "Invalid email or password") {
          return "Identifiants incorrects.";
        }

        if (backendMessage === "Inactive user") {
          return "Ce compte est inactif.";
        }

        return backendMessage;
      }

      if (!cause.response) {
        return "Impossible de joindre le serveur. Vérifiez l’adresse API et votre connexion.";
      }

      if (cause.response.status >= 500) {
        return "Le serveur a rencontré une erreur. Réessayez dans un instant.";
      }
    }

    return "Connexion impossible pour le moment.";
  };

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const normalizedForm = {
        email: form.email.trim().toLowerCase(),
        password: form.password,
      };

      const user = await login(normalizedForm);

      const from = (
        location.state as {
          from?: { pathname?: string };
        } | null
      )?.from?.pathname;

      navigate(from || `/dashboard/${buildUserDashboardUid(user)}`, {
        replace: true,
      });
    } catch (cause) {
      setError(getLoginErrorMessage(cause));
    } finally {
      setLoading(false);
    }
  };

  const connectionInfo = buildLoginConnectionInfo(
    runtimeConnection.connectionMode,
    runtimeConnection.apiBaseUrl,
  );

  const connectionVerified =
    runtimeConnection.state === "connected" ||
    runtimeConnection.state === "connected_pending_validation";

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 px-6 py-10">
      <Card className="w-full max-w-xl rounded-2xl border border-slate-200 bg-white p-8 shadow-sm">
        {/* Header */}
        <div className="mb-7 text-center">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-[#0085A3]/10 text-[#0085A3]">
            <ShieldCheck className="h-6 w-6" />
          </div>

          <h1 className="mt-4 text-2xl font-bold tracking-tight text-slate-950">
            Connexion
          </h1>

          <p className="mt-1 text-sm text-slate-500">
            Accédez à votre espace Medical Folder
          </p>
        </div>

        {/* Connection information */}
        <section className="mb-7 rounded-xl border border-slate-200 bg-slate-50/70 p-4">
          <div className="flex items-center justify-between gap-5">
            <div className="flex min-w-0 items-center gap-3.5">
              <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg border border-[#0085A3]/10 bg-[#0085A3]/10 text-[#0085A3]">
                <Server className="h-5 w-5" />
              </div>

              <div className="min-w-0">
                <div className="flex items-center gap-2.5">
                  <h2 className="truncate text-sm font-semibold text-slate-900">
                    {connectionInfo.modeLabel}
                  </h2>

                  {connectionVerified && (
                    <span className="inline-flex shrink-0 items-center gap-1.5 rounded-full bg-emerald-100 px-2 py-1 text-[11px] font-semibold text-emerald-700">
                      <CheckCircle2 className="h-3.5 w-3.5" />
                      Vérifiée
                    </span>
                  )}
                </div>

                <div className="mt-1.5 flex min-w-0 items-center gap-1.5 text-xs text-slate-500">
                  <Link2 className="h-3.5 w-3.5 shrink-0" />

                  <span className="shrink-0 font-medium">
                    {connectionInfo.apiLabel}
                  </span>

                  <span className="shrink-0 text-slate-300">•</span>

                  <span
                    className="truncate font-mono text-slate-600"
                    title={connectionInfo.apiBaseUrl}
                  >
                    {connectionInfo.apiBaseUrl}
                  </span>
                </div>
              </div>
            </div>

            <Button
              type="button"
              variant="ghost"
              size="sm"
              icon={Settings2}
              disabled={loading}
              onClick={() =>
                navigate(LOGIN_CONFIGURATION_PATH, {
                  state: { edit: true },
                })
              }
              className="shrink-0 border border-slate-200 bg-white text-slate-700 shadow-sm hover:border-slate-300 hover:bg-slate-100"
            >
              Modifier
            </Button>
          </div>
        </section>

        {/* Login form */}
        <form className="space-y-5" onSubmit={onSubmit}>
          <Input
            label="Adresse e-mail"
            type="email"
            value={form.email}
            onChange={(event) =>
              setForm((current) => ({
                ...current,
                email: event.target.value,
              }))
            }
            placeholder="admin@ibnsina.com"
            autoComplete="email"
            required
          />

          <Input
            label="Mot de passe"
            type="password"
            value={form.password}
            onChange={(event) =>
              setForm((current) => ({
                ...current,
                password: event.target.value,
              }))
            }
            placeholder="••••••••"
            autoComplete="current-password"
            required
          />

          {error && (
            <div
              role="alert"
              className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-medium text-red-700"
            >
              {error}
            </div>
          )}

          <Button
            type="submit"
            size="lg"
            loading={loading}
            className="w-full rounded-xl bg-[#0085A3] shadow-sm hover:bg-[#00728c]"
          >
            Se connecter
          </Button>

          <button
            type="button"
            disabled={loading}
            onClick={() => void runtimeConnection.refreshConnection()}
            className="mx-auto flex items-center gap-2 text-xs font-medium text-slate-500 transition-colors hover:text-[#0085A3] disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Network className="h-3.5 w-3.5" />
            Vérifier la connexion au serveur
          </button>
        </form>
      </Card>
    </main>
  );
};