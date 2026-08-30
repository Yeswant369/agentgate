import { useEffect, useState } from 'react'

function Stub({ title, coming }: { title: string; coming: string }) {
  return (
    <section>
      <h1>{title}</h1>
      <p className="muted">{coming}</p>
    </section>
  )
}

export function Overview() {
  return (
    <Stub
      title="Overview"
      coming="Live counters land in Phase 6: decisions made, denials by attack class, audit-chain length and integrity."
    />
  )
}

type DecisionRow = {
  audit_id: number
  decision: string
  agent_id: string | null
  transaction_id: string | null
  policy_version: number
  created_at: string
  failed_rules: { rule_id: string; outcome: string; reason: string }[]
}

export function Decisions() {
  const [rows, setRows] = useState<DecisionRow[] | null>(null)
  const [replays, setReplays] = useState<Record<number, string>>({})

  useEffect(() => {
    fetch('/api/decisions?limit=50')
      .then((r) => r.json())
      .then(setRows)
      .catch(() => setRows([]))
  }, [])

  const replay = (id: number) => {
    setReplays((s) => ({ ...s, [id]: '…' }))
    fetch(`/api/decisions/${id}/replay`, { method: 'POST' })
      .then((r) => r.json())
      .then((d) =>
        setReplays((s) => ({
          ...s,
          [id]: d.identical ? '✓ identical' : d.detail ? 'n/a' : '✗ DIVERGED',
        })),
      )
      .catch(() => setReplays((s) => ({ ...s, [id]: 'error' })))
  }

  if (rows === null) return <p className="muted">loading…</p>
  return (
    <section>
      <h1>Decision Explorer</h1>
      <p className="muted">
        Every policy verdict, newest first. Deny-by-default; no LLM in the decision path.
        “Replay” re-runs the recorded inputs through the recorded policy version — determinism
        proven on demand.
      </p>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>decision</th>
              <th>non-passing rules</th>
              <th>policy</th>
              <th>when</th>
              <th>replay</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.audit_id}>
                <td>{r.audit_id}</td>
                <td>
                  <span className={`pill pill-${r.decision}`}>{r.decision}</span>
                </td>
                <td>
                  {r.failed_rules.length === 0
                    ? '—'
                    : r.failed_rules.map((f) => (
                        <div key={f.rule_id} title={f.reason}>
                          <code>{f.rule_id}</code> {f.reason}
                        </div>
                      ))}
                </td>
                <td>v{r.policy_version}</td>
                <td>{new Date(r.created_at).toLocaleString()}</td>
                <td>
                  <button onClick={() => replay(r.audit_id)}>
                    {replays[r.audit_id] ?? 'replay'}
                  </button>
                </td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={6} className="muted">
                  no decisions yet
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  )
}

export function Metrics() {
  return (
    <Stub
      title="Metrics"
      coming="Confusion matrix, per-attack-class detection rates with confidence intervals, and false-positive cost in ₹. Arrives with the eval harness (Phase 5)."
    />
  )
}

type AuditRow = {
  id: number
  decision: string
  transaction_id: string | null
  hash: string
  prev_hash: string
  created_at: string
}

export function AuditChain() {
  const [rows, setRows] = useState<AuditRow[] | null>(null)
  const [verify, setVerify] = useState<string>('')

  useEffect(() => {
    fetch('/api/audit/records?limit=50')
      .then((r) => r.json())
      .then(setRows)
      .catch(() => setRows([]))
  }, [])

  const runVerify = () => {
    setVerify('verifying…')
    fetch('/api/audit/verify')
      .then((r) => r.json())
      .then((v) =>
        setVerify(
          v.intact
            ? `✓ chain intact — ${v.length} records, head ${String(v.head).slice(0, 16)}…`
            : `✗ BROKEN at record ${v.broken_at}: ${v.reason}`,
        ),
      )
      .catch(() => setVerify('verification failed'))
  }

  if (rows === null) return <p className="muted">loading…</p>
  return (
    <section>
      <h1>Audit Chain</h1>
      <p className="muted">
        Hash-chained: each record’s hash covers the previous record’s hash plus its own
        content. Verification recomputes every hash from genesis — an intact result is a
        computation, not a claim.
      </p>
      <p>
        <button onClick={runVerify}>Verify chain now</button>{' '}
        <span className={verify.startsWith('✗') ? 'bad' : 'ok'}>{verify}</span>
      </p>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>decision</th>
              <th>prev_hash</th>
              <th>hash</th>
              <th>when</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id}>
                <td>{r.id}</td>
                <td>
                  <span className={`pill pill-${r.decision}`}>{r.decision}</span>
                </td>
                <td>
                  <code>{r.prev_hash}</code>
                </td>
                <td>
                  <code>{r.hash}</code>
                </td>
                <td>{new Date(r.created_at).toLocaleString()}</td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={5} className="muted">
                  chain is empty
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  )
}

export function Playground() {
  return (
    <Stub
      title="Judge Playground"
      coming="Replay recorded agent sessions — legit purchases and attacks — through the live policy engine. Arrives in Phase 6."
    />
  )
}
