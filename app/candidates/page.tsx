const candidates = [
  ["AR", "Ayesha Rahman", "Senior Product Designer", "3 interviews", "Verified"],
  ["MK", "Mikael Khan", "Backend Engineer", "1 interview", "Invited"],
  ["SN", "Sara Noor", "Frontend Intern", "2 interviews", "Needs review"],
  ["HA", "Hamza Ali", "Software Engineer", "4 interviews", "Verified"],
];

export default function CandidatesPage() {
  return <main className="simple-page"><a className="back-link" href="/">← Back to overview</a><p className="eyebrow red">WORKSPACE / CANDIDATES</p><h1>Candidates</h1><p className="page-intro">A clear view of candidate verification history and interview activity.</p><div className="candidate-page-card"><div className="candidate-page-head"><div><p className="eyebrow">96 TOTAL CANDIDATES</p><h2>Candidate directory</h2></div><a className="primary-button" href="/interviews/new">＋ New interview</a></div><div className="candidate-table">{candidates.map(([initials, name, role, interviews, status]) => <a className="simple-row" href="/reports" key={name}><span className="candidate-avatar">{initials}</span><span><strong>{name}</strong><small>{role}</small></span><time>{interviews}</time><em className={status === "Verified" ? "verified" : status === "Needs review" ? "needs-review" : "invited"}>{status}</em><span>↗</span></a>)}</div></div></main>;
}
