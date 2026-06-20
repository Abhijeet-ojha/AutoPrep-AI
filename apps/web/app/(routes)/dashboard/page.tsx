"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { ChatPanel } from "@/components/ChatPanel";
import { getJSON, postJSON, API_BASE } from "@/lib/api";

const Plot = dynamic(() => import("react-plotly.js"), { ssr: false });

type DashboardData = {
	profile: any;
	quality: any;
	recommendations: any[];
	health: any;
	readiness: any;
	eda: any;
	versions: any[];
	featureEngineering: any[];
};

export default function DashboardPage() {
	const [datasetId, setDatasetId] = useState<string>("");
	const [data, setData] = useState<DashboardData | null>(null);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);
	const [actionState, setActionState] = useState({
		fill_missing: true,
		remove_duplicates: true,
		fix_formatting: true,
		handle_outliers: false,
		convert_dtypes: true
	});

	const fetchData = async (id: string) => {
		const [profileRes, qualityRes, recRes, healthRes, readinessRes, edaRes, versionsRes, feRes] = await Promise.all([
			getJSON(`/datasets/${id}/profile`),
			getJSON(`/datasets/${id}/quality`),
			getJSON(`/datasets/${id}/recommendations`),
			getJSON(`/datasets/${id}/health`),
			getJSON(`/datasets/${id}/ml-readiness`),
			getJSON(`/datasets/${id}/eda`),
			getJSON(`/datasets/${id}/versions`),
			getJSON(`/datasets/${id}/feature-engineering`)
		]);

		setData({
			profile: profileRes.profile,
			quality: qualityRes.quality,
			recommendations: recRes.recommendations,
			health: healthRes,
			readiness: readinessRes,
			eda: edaRes,
			versions: versionsRes.versions,
			featureEngineering: feRes.suggestions
		});
	};

	useEffect(() => {
		const id = localStorage.getItem("autoprep_dataset_id") || "";
		setDatasetId(id);
		if (!id) {
			setLoading(false);
			return;
		}

		fetchData(id)
			.catch((e) => setError(e instanceof Error ? e.message : "Failed to load dashboard"))
			.finally(() => setLoading(false));
	}, []);

	const runCleaning = async () => {
		if (!datasetId) return;
		const actions = Object.entries(actionState)
			.filter(([, checked]) => checked)
			.map(([action]) => action);
		await postJSON(`/datasets/${datasetId}/clean`, { actions });
		await fetchData(datasetId);
	};

	const rollback = async (version: number) => {
		if (!datasetId) return;
		await postJSON(`/datasets/${datasetId}/rollback`, { version });
		await fetchData(datasetId);
	};

	const missingColumns = useMemo(() => {
		if (!data) return [];
		return Object.entries(data.quality.missing.by_column).filter(([, v]) => Number(v) > 0);
	}, [data]);

	if (loading) {
		return <p>Loading dashboard...</p>;
	}

	if (!datasetId) {
		return (
			<div className="card">
				<p>No dataset selected.</p>
				<Link href="/upload" className="text-red-500 underline">
					Upload dataset first
				</Link>
			</div>
		);
	}

	if (error || !data) {
		return <p className="text-red-600">{error || "Unable to load dashboard"}</p>;
	}

	const healthBreakdown = Object.entries(data.health.breakdown);
	const readinessFlags = Object.entries(data.readiness.ready_for || {});

	return (
		<main className="space-y-5">
			<header className="card">
				<p className="text-xs uppercase tracking-[0.2em] text-cyan-600">AutoPrep AI Analyst Studio</p>
				<h1 className="title text-3xl font-bold">Dataset Intelligence Dashboard</h1>
				<p className="text-slate-600">Dataset ID: {datasetId}</p>
			</header>

			<section className="grid gap-4 md:grid-cols-4">
				<div className="card">
					<p className="text-sm text-slate-500">Rows</p>
					<p className="title text-2xl font-semibold">{data.profile.summary.rows}</p>
				</div>
				<div className="card">
					<p className="text-sm text-slate-500">Columns</p>
					<p className="title text-2xl font-semibold">{data.profile.summary.columns}</p>
				</div>
				<div className="card">
					<p className="text-sm text-slate-500">Dataset Health</p>
					<p className="title text-2xl font-semibold">{data.health.score}/100</p>
				</div>
				<div className="card">
					<p className="text-sm text-slate-500">ML Readiness</p>
					<p className="title text-2xl font-semibold">{data.readiness.score}/100</p>
				</div>
			</section>

			<section className="grid gap-4 md:grid-cols-2">
				<div className="card">
					<h2 className="title text-xl font-semibold">Health Score Breakdown</h2>
					<ul className="mt-3 space-y-2">
						{healthBreakdown.map(([k, v]) => (
							<li key={k} className="flex items-center justify-between rounded-lg bg-slate-50 p-2 text-sm">
								<span>{k}</span>
								<span className="font-semibold">{String(v)}</span>
							</li>
						))}
					</ul>
					<p className="mt-3 text-sm text-slate-600">{data.health.improvement_suggestions?.join(" ")}</p>
				</div>

				<div className="card">
					<h2 className="title text-xl font-semibold">ML Readiness</h2>
					<ul className="mt-3 space-y-2 text-sm">
						{readinessFlags.map(([k, v]) => (
							<li key={k}>
								{v ? "YES" : "NO"} - {k}
							</li>
						))}
					</ul>
					<p className="mt-3 text-sm text-slate-600">{data.readiness.reasoning}</p>
				</div>
			</section>

			<section className="grid gap-4 md:grid-cols-2">
				<div className="card">
					<h2 className="title text-xl font-semibold">Missing Value Heatmap</h2>
					<Plot
						data={[
							{
								type: "bar",
								x: missingColumns.map(([c]) => c),
								y: missingColumns.map(([, v]) => Number(v)),
								marker: { color: "#ef4444" }
							}
						]}
						layout={{ margin: { l: 30, r: 10, b: 40, t: 20 }, autosize: true }}
						style={{ width: "100%", height: 280 }}
					/>
				</div>

				<div className="card">
					<h2 className="title text-xl font-semibold">Correlation Heatmap</h2>
					<Plot
						data={[
							{
								type: "heatmap",
								z: Object.values(data.eda.correlation_heatmap || {}).map((row: any) => Object.values(row as object)),
								x: Object.keys(data.eda.correlation_heatmap || {}),
								y: Object.keys(data.eda.correlation_heatmap || {}),
								colorscale: "RdBu"
							}
						]}
						layout={{ margin: { l: 40, r: 10, b: 40, t: 20 }, autosize: true }}
						style={{ width: "100%", height: 280 }}
					/>
				</div>
			</section>

			<section className="grid gap-4 md:grid-cols-2">
				<div className="card">
					<h2 className="title text-xl font-semibold">AI Cleaning Recommendations</h2>
					<ul className="mt-3 space-y-2 text-sm">
						{data.recommendations.slice(0, 8).map((r, i) => (
							<li key={`${r.column}-${i}`} className="rounded-lg bg-slate-50 p-2">
								<p className="font-semibold">{r.column}: {r.recommended_action}</p>
								<p>{r.explanation}</p>
								<p className="text-slate-500">Confidence: {Math.round(Number(r.confidence) * 100)}%</p>
							</li>
						))}
					</ul>
				</div>

				<div className="card space-y-2">
					<h2 className="title text-xl font-semibold">Automated Cleaning Pipeline</h2>
					{Object.keys(actionState).map((k) => (
						<label key={k} className="flex items-center gap-2 text-sm">
							<input
								type="checkbox"
								checked={actionState[k as keyof typeof actionState]}
								onChange={(e) => setActionState((prev) => ({ ...prev, [k]: e.target.checked }))}
							/>
							{k}
						</label>
					))}
					<button onClick={runCleaning} className="mt-3 rounded-xl bg-red-500 px-4 py-2 text-white">
						One-Click Auto Clean
					</button>
				</div>
			</section>

			<section className="grid gap-4 md:grid-cols-2">
				<div className="card">
					<h2 className="title text-xl font-semibold">Version History</h2>
					<ul className="mt-3 space-y-2 text-sm">
						{data.versions.map((v) => (
							<li key={v.version} className="flex items-center justify-between rounded-lg bg-slate-50 p-2">
								<span>
									v{v.version}: {v.action}
								</span>
								<button className="text-cyan-600 underline" onClick={() => rollback(v.version)}>
									Rollback
								</button>
							</li>
						))}
					</ul>
				</div>

				<div className="card">
					<h2 className="title text-xl font-semibold">Feature Engineering Advisor</h2>
					<ul className="mt-3 space-y-2 text-sm">
						{data.featureEngineering.slice(0, 10).map((s, i) => (
							<li key={`${s.type}-${i}`} className="rounded-lg bg-slate-50 p-2">
								<p className="font-semibold">{s.type}</p>
								<p>{s.column || "dataset"}: {s.reason}</p>
							</li>
						))}
					</ul>
				</div>
			</section>

			<ChatPanel datasetId={datasetId} />

			<section className="card">
				<h2 className="title text-xl font-semibold">Export Center</h2>
				<div className="mt-3 flex flex-wrap gap-3 text-sm">
					<a className="rounded-lg border border-slate-300 px-3 py-2" href={`${API_BASE}/datasets/${datasetId}/export/csv`}>
						Download Cleaned CSV
					</a>
					<a className="rounded-lg border border-slate-300 px-3 py-2" href={`${API_BASE}/datasets/${datasetId}/report/html`}>
						Download HTML Report JSON
					</a>
					<a className="rounded-lg border border-slate-300 px-3 py-2" href={`${API_BASE}/datasets/${datasetId}/code`}>
						Download Preprocessing Code JSON
					</a>
				</div>
			</section>
		</main>
	);
}
