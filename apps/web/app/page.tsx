import Link from "next/link";

export default function HomePage() {
  return (
    <main className="space-y-6">
      <section className="card">
        <p className="mb-2 text-xs font-semibold uppercase tracking-[0.2em] text-red-500">AutoPrep AI</p>
        <h1 className="title text-3xl font-bold md:text-5xl">Intelligent Dataset Cleaning, Profiling, and EDA Assistant</h1>
        <p className="mt-3 max-w-3xl text-slate-600">
          Upload a dataset and get AI-driven data quality audit, explainable cleaning recommendations, automated preprocessing,
          interactive analytics, and ML readiness evaluation.
        </p>
        <div className="mt-6 flex gap-3">
          <Link href="/upload" className="rounded-xl bg-red-500 px-4 py-2 text-white hover:bg-red-600">
            Start with Upload
          </Link>
          <Link href="/dashboard" className="rounded-xl border border-slate-300 px-4 py-2 text-slate-700 hover:bg-slate-50">
            Open Dashboard
          </Link>
        </div>
      </section>
    </main>
  );
}
