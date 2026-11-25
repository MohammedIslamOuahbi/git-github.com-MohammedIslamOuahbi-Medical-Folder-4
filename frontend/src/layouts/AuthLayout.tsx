import { HeartPulse } from "lucide-react";
import { Outlet } from "react-router-dom";
import { env } from "@/config/env";

export const AuthLayout = () => (
  <div className="grid min-h-screen min-w-[1280px] grid-cols-[0.9fr_1fr]">
    <section className="flex overflow-hidden bg-gradient-to-br from-[#003B49] via-[#005E73] to-[#0085A3] px-10 py-12 text-white">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(255,255,255,0.14),transparent_28%),radial-gradient(circle_at_bottom_left,rgba(255,255,255,0.08),transparent_24%)]" />

      <div className="relative z-10 flex w-full flex-col justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl border border-white/15 bg-white/10 backdrop-blur-xl">
            <HeartPulse className="h-7 w-7 text-cyan-100" />
          </div>

          <div>
            <p className="text-xs font-bold uppercase tracking-[0.28em] text-cyan-100/70">
              Opérations médicales
            </p>

            <h1 className="mt-1 text-2xl font-black tracking-tight">
              {env.appName}
            </h1>
          </div>
        </div>

        <div className="max-w-md">
          <p className="mb-4 text-xs font-bold uppercase tracking-[0.28em] text-cyan-100/70">
            Intelligence clinique
          </p>

          <h2 className="text-4xl font-black leading-tight tracking-tight">
            Un centre de pilotage unique pour les cliniques de terrain.
          </h2>

          <p className="mt-5 text-base leading-7 text-cyan-50/80">
            Coordonnez les campagnes médicales, les travailleurs, les examens médicaux
            et les opérations sur les sites de forage avec des tableaux de bord complets
            et une synchronisation hors ligne fiable.
          </p>
        </div>

        <div className="grid grid-cols-3 gap-3 text-sm">
          <div className="rounded-[1.7rem] border border-white/10 bg-white/10 p-4 backdrop-blur-xl">
            <p className="text-[10px] uppercase tracking-[0.22em] text-cyan-100/70">
              Campagnes médicales
            </p>

            <h3 className="mt-2 text-2xl font-black">44</h3>

            <p className="mt-1 text-xs text-cyan-50/70">
              Opérations actives
            </p>
          </div>

          <div className="rounded-[1.7rem] border border-white/10 bg-white/10 p-4 backdrop-blur-xl">
            <p className="text-[10px] uppercase tracking-[0.22em] text-cyan-100/70">
              Travailleurs
            </p>

            <h3 className="mt-2 text-2xl font-black">1,480</h3>

            <p className="mt-1 text-xs text-cyan-50/70">
              Profils suivis
            </p>
          </div>

          <div className="rounded-[1.7rem] border border-white/10 bg-white/10 p-4 backdrop-blur-xl">
            <p className="text-[10px] uppercase tracking-[0.22em] text-cyan-100/70">
              Synchronisation
            </p>

            <h3 className="mt-2 text-2xl font-black">99.2%</h3>

            <p className="mt-1 text-xs text-cyan-50/70">
              Indice d'intégrité
            </p>
          </div>
        </div>
      </div>
    </section>

    <section className="relative flex items-center justify-center overflow-hidden bg-slate-100 px-10 py-12">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(0,133,163,0.08),transparent_24%),radial-gradient(circle_at_bottom_right,rgba(14,165,233,0.08),transparent_26%)]" />

      <div className="relative z-10 w-full max-w-xl">
        <Outlet />
      </div>
    </section>
  </div>
);
