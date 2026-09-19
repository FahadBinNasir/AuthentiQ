"use client";
import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
type Report = { candidate_name: string; title: string; status: string; summary: { total_events: number; human_review_required: boolean }; timeline: { id: string; type: string; timestamp: string; severity: string; confidence: number | null }[] };
function ReportsContent() {
  const params = useSearchParams(); const id = params.get("id"); const [report, setReport] = useState<Report | null>(null); const [error, setError] = useState("");
  useEffect(() => { if (!id) return; fetch(`${API}/api/v1/interviews/${id}/report`, { headers: { Authorization: `Bearer ${localStorage.getItem("authentiq_session") ?? ""}` } }).then(async (r) => { const d = await r.json(); if (!r.ok) throw Error(d.detail); setReport(d); }).catch((e) => setError(e.message)); }, [id]);
  if (error) return <main className="simple-page"><a className="back-link" href="/dashboard">← Back to dashboard</a><p className="eyebrow red">WORKSPACE / EVIDENCE REPORT</p><h1>Report unavailable</h1><div className="auth-error">{error}</div></main>;
  if (!report) return <main className="simple-page"><h1>Integrity report</h1><p className="page-intro">Loading evidence…</p></main>;
  return <main className="simple-page"><a className="back-link" href="/dashboard">← Back to dashboard</a><p className="eyebrow red">WORKSPACE / EVIDENCE REPORT</p><h1>{report.candidate_name}</h1><p className="page-intro">{report.title} · {report.status}</p><div className="metrics"><div className="metric"><p>Total events</p><strong>{report.summary.total_events}</strong></div><div className="metric"><p>Review status</p><strong>{report.summary.human_review_required ? "Review" : "Clear"}</strong></div></div><section className="simple-list"><h2>Evidence timeline</h2>{report.timeline.length === 0 ? <div className="data-state">No integrity events recorded.</div> : report.timeline.map((event) => <div className="simple-row" key={event.id}><span className="candidate-avatar">!</span><span><strong>{event.type}</strong><small>{event.severity} · confidence {event.confidence == null ? "—" : `${Math.round(event.confidence * 100)}%`}</small></span><time>{new Date(event.timestamp).toLocaleString()}</time></div>)}</section></main>;
}

export default function ReportsPage() { return <Suspense fallback={<main className="simple-page"><h1>Integrity report</h1><p>Loading evidence…</p></main>}><ReportsContent /></Suspense>; }
