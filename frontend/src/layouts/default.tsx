export default function DefaultLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const currentYear = new Date().getFullYear();

  return (
    <div className="relative flex min-h-screen flex-col overflow-hidden bg-slate-950 text-slate-100">
      <div className="pointer-events-none absolute inset-0 -z-10">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,rgba(59,130,246,0.18),transparent_55%)]" />
        <div className="absolute left-1/2 top-1/3 h-[520px] w-[520px] -translate-x-1/2 rounded-full bg-[radial-gradient(circle,rgba(236,72,153,0.18),transparent_60%)] blur-3xl" />
        <div className="absolute -left-24 bottom-12 h-80 w-80 rounded-full bg-[radial-gradient(circle,rgba(14,165,233,0.22),transparent_65%)] blur-3xl" />
        <div className="absolute -right-24 -top-16 h-72 w-72 rounded-full bg-[radial-gradient(circle,rgba(168,85,247,0.22),transparent_65%)] blur-3xl" />
      </div>

      <header className="border-b border-white/10 bg-slate-900/30 py-6 backdrop-blur-xl">
        <div className="mx-auto flex w-full max-w-4xl items-center justify-between px-6">
          <div>
            <p className="text-xs uppercase tracking-[0.4em] text-slate-400">
              Planner
            </p>
            <h1 className="mt-1 text-xl font-semibold text-white">
              Портал управления балансом
            </h1>
          </div>
          <span className="rounded-full border border-white/10 bg-white/10 px-4 py-1 text-xs font-medium text-white/80 shadow-lg shadow-blue-500/20">
            Secure Access
          </span>
        </div>
      </header>

      <main className="relative mx-auto flex w-full max-w-4xl flex-1 px-6 py-14">
        <div className="w-full">{children}</div>
      </main>

      <footer className="border-t border-white/5 bg-slate-900/40 py-4 text-center text-sm text-slate-400 backdrop-blur">
        Planner © {currentYear}
      </footer>
    </div>
  );
}
