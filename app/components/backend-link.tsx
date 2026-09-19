"use client";
import { useEffect, useState } from "react";
const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
export function BackendLink({ href, children, className = "" }: { href: string; children: React.ReactNode; className?: string }) {
  const [online, setOnline] = useState(false);
  useEffect(() => { let active = true; fetch(`${API}/health`, { signal: AbortSignal.timeout(5000) }).then((r) => active && setOnline(r.ok)).catch(() => active && setOnline(false)); return () => { active = false; }; }, []);
  return <a className={`${className} ${!online ? "backend-disabled" : ""}`} href={online ? href : undefined} aria-disabled={!online} onClick={(e) => { if (!online) e.preventDefault(); }}>{children}{!online && <small>API offline</small>}</a>;
}
