import { useEffect, useState } from 'react'

type OverviewData = {
  total_decisions: number
  by_decision: Record<string, number>
  denials_by_rule: Record<string, number>
  chain: { intact: boolean; length: number }
}

export function Overview() {
  const [data, setData] = useState<OverviewData | null>(null)

  useEffect(() => {
    fetch('/api/overview')
      .then((r) => r.json())
      .then(setData)
      .catch(() => setData(null))
  }, [])

  return (
    <section>
      <h1>AgentGate</h1>
      <p className="lede">
        AI agents are starting to spend real money. AgentGate is the deterministic policy
        engine between an AI buyer agent and the payment rails — every money action{' '}
        <b>explainable, bounded and gated</b>, even when the agent itself is manipulated.
      </p>
      <p className="muted" style={{ marginTop: '0.5rem' }}>
        The gateway assumes the agent is already compromised. Prompt engineering is not the
        security boundary — this engine is. No LLM sits in the decision path.
      </p>

      {data && (
        <>
          <div className="stat-row" style={{ marginTop: '1.5rem' }}>
            <div className="stat">
              <span className="stat-label">decisions made</span>
              <span className="stat-val">{data.total_decisions.toLocaleString('en-IN')}</span>
            </div>
            <div className="stat">
              <span className="stat-label">allowed</span>
              <span className="stat-val" style={{ color: 'var(--ok)' }}>
                {data.by_decision.allow ?? 0}
              </span>
            </div>
            <div className="stat">
              <span className="stat-label">denied</span>
              <span className="stat-val" style={{ color: 'var(--bad)' }}>
                {data.by_decision.deny ?? 0}
              </span>
            </div>
            <div className="stat">
              <span className="stat-label">audit chain</span>
              <span className="stat-val" style={{ color: data.chain.intact ? 'var(--ok)' : 'var(--bad)' }}>
                {data.chain.intact ? `✓ ${data.chain.length} intact` : '✗ broken'}
              </span>
            </div>
          </div>

          <h2 style={{ fontSize: '1rem', marginTop: '1.5rem' }}>Denials by rule</h2>
          <div className="table-wrap" style={{ maxWidth: '32rem' }}>
            <table>
              <tbody>
                {Object.entries(data.denials_by_rule).map(([rule, n]) => (
                  <tr key={rule}>
                    <td>
                      <code>{rule}</code>
                    </td>
                    <td style={{ textAlign: 'right' }}>{n}</td>
                  </tr>
                ))}
                {Object.keys(data.denials_by_rule).length === 0 && (
                  <tr>
                    <td className="muted">no denials yet</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
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

type Interval = { point: number; lo: number; hi: number; n: number }
type MetricsData = {
  available: boolean
  ran_at?: string
  scenario_count?: number
  metrics?: {
    confusion_matrix: {
      tp: number; fn: number; tn: number; fp: number
      held_for_approval: number; system_errors: number
      precision: Interval; recall: Interval; fpr: Interval; fnr: Interval
      f1: number; fp_cost_rupees_per_lakh: number
    }
    per_class: Record<string, Record<string, unknown>>
    mutation_testing: { mutations_run: number; all_caught: boolean; surviving: string[] }
  }
}

const ci = (i?: Interval) =>
  !i || i.n === 0
    ? 'n/a'
    : `${(i.point * 100).toFixed(0)}% [${(i.lo * 100).toFixed(0)}–${(i.hi * 100).toFixed(0)}%]`

export function Metrics() {
  const [data, setData] = useState<MetricsData | null>(null)

  useEffect(() => {
    fetch('/api/metrics')
      .then((r) => r.json())
      .then(setData)
      .catch(() => setData({ available: false }))
  }, [])

  if (data === null) return <p className="muted">loading…</p>
  if (!data.available || !data.metrics)
    return (
      <section>
        <h1>Metrics</h1>
        <p className="muted">
          No eval run recorded yet. Run <code>make eval</code> to generate metrics.
        </p>
      </section>
    )

  const m = data.metrics
  const cm = m.confusion_matrix
  return (
    <section>
      <h1>Metrics</h1>
      <p className="muted">
        From {data.scenario_count} seeded scenarios (40 legit, 40 attacks), reproducible via{' '}
        <code>make eval</code>. Positive class = attack that should be blocked. Wilson 95%
        confidence intervals — with small per-class n, the interval is the honest number.
      </p>

      <h2 style={{ fontSize: '1rem', marginTop: '1.5rem' }}>Confusion matrix</h2>
      <div className="cm-grid">
        <div className="cm-cell cm-good">
          <span className="cm-n">{cm.tp}</span>TP · attacks blocked
        </div>
        <div className="cm-cell cm-bad">
          <span className="cm-n">{cm.fn}</span>FN · attacks MISSED
        </div>
        <div className="cm-cell cm-bad">
          <span className="cm-n">{cm.fp}</span>FP · legit BLOCKED
        </div>
        <div className="cm-cell cm-good">
          <span className="cm-n">{cm.tn}</span>TN · legit allowed
        </div>
      </div>
      <p className="muted" style={{ fontSize: '0.8rem' }}>
        held for approval: {cm.held_for_approval} · system-error denials:{' '}
        {cm.system_errors} (not counted as catches)
      </p>

      <div className="stat-row">
        <div className="stat">
          <span className="stat-label">recall (detection)</span>
          <span className="stat-val">{ci(cm.recall)}</span>
        </div>
        <div className="stat">
          <span className="stat-label">precision</span>
          <span className="stat-val">{ci(cm.precision)}</span>
        </div>
        <div className="stat">
          <span className="stat-label">F1</span>
          <span className="stat-val">{cm.f1.toFixed(3)}</span>
        </div>
        <div className="stat">
          <span className="stat-label">false-positive rate</span>
          <span className="stat-val">{ci(cm.fpr)}</span>
        </div>
      </div>

      <div className="fp-cost">
        False-positive cost: <b>≈ ₹{cm.fp_cost_rupees_per_lakh.toLocaleString('en-IN')}</b> of
        legitimate commerce blocked per ₹1,00,000 of legitimate agent commerce. Every false
        positive is a real customer turned away — we measure it instead of hiding it.
      </div>

      <h2 style={{ fontSize: '1rem', marginTop: '1.5rem' }}>Per-class detection (95% CI)</h2>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>class</th>
              <th>n</th>
              <th>detection / correct-allow</th>
              <th>misses / FPs</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(m.per_class).map(([klass, r]) => {
              const isLegit = klass === 'legit'
              const rate = (isLegit ? r.correct_allow : r.detection) as Interval
              return (
                <tr key={klass}>
                  <td>{isLegit ? <b>{klass}</b> : klass}</td>
                  <td>{r.n as number}</td>
                  <td>{ci(rate)}</td>
                  <td>
                    {isLegit
                      ? `FP=${r.false_positives} held=${r.held_for_approval}`
                      : `missed=${r.missed}`}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      <div
        className={m.mutation_testing.all_caught ? 'mutation ok' : 'mutation bad'}
        style={{ marginTop: '1.25rem' }}
      >
        Mutation testing: {m.mutation_testing.mutations_run} weakened rules tested —{' '}
        {m.mutation_testing.all_caught
          ? 'all regressions caught by the suite ✓'
          : `SURVIVING: ${m.mutation_testing.surviving.join(', ')}`}
      </div>
    </section>
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
  const [replays, setReplays] = useState<Record<number, string>>({})

  useEffect(() => {
    fetch('/api/audit/records?limit=50')
      .then((r) => r.json())
      .then(setRows)
      .catch(() => setRows([]))
  }, [])

  const replayDecision = (id: number) => {
    setReplays((s) => ({ ...s, [id]: '…' }))
    fetch(`/api/decisions/${id}/replay`, { method: 'POST' })
      .then((r) => r.json())
      .then((d) =>
        setReplays((s) => ({
          ...s,
          [id]: d.identical ? '✓ identical' : d.detail ? 'n/a' : '✗ diverged',
        })),
      )
      .catch(() => setReplays((s) => ({ ...s, [id]: 'error' })))
  }

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
              <th>replay</th>
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
                <td>
                  <button onClick={() => replayDecision(r.id)}>
                    {replays[r.id] ?? 'replay'}
                  </button>
                </td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={6} className="muted">
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

type PlaygroundScenario = { id: string; title: string; story: string; expected: string }
type ReplayResult = {
  decision: string
  expected: string
  matches_expected: boolean
  note: string
  rules: { rule_id: string; reason: string }[]
  rate_limit_remaining: number
}

export function Playground() {
  const [scenarios, setScenarios] = useState<PlaygroundScenario[] | null>(null)
  const [results, setResults] = useState<Record<string, ReplayResult | 'running' | 'limited'>>({})

  useEffect(() => {
    fetch('/api/playground/scenarios')
      .then((r) => r.json())
      .then(setScenarios)
      .catch(() => setScenarios([]))
  }, [])

  const run = (id: string) => {
    setResults((s) => ({ ...s, [id]: 'running' }))
    fetch(`/api/playground/replay/${id}`, { method: 'POST' })
      .then((r) => {
        if (r.status === 429) {
          setResults((s) => ({ ...s, [id]: 'limited' }))
          return null
        }
        return r.json()
      })
      .then((body) => {
        if (body) setResults((s) => ({ ...s, [id]: body }))
      })
      .catch(() => setResults((s) => ({ ...s, [id]: 'limited' })))
  }

  if (scenarios === null) return <p className="muted">loading…</p>
  return (
    <section>
      <h1>Judge Playground</h1>
      <p className="muted">
        Click any scenario to re-fire a recorded agent session through the <b>live</b> policy
        engine. The agent's shopping is pre-recorded; the gateway's decision is computed fresh
        on your click. Rate-limited to 20 replays/minute per IP — the demo being bounded and
        gated is itself the thesis. Nothing here can spend money.
      </p>
      <div className="pg-grid">
        {scenarios.map((s) => {
          const res = results[s.id]
          return (
            <div key={s.id} className="pg-card">
              <div className="pg-head">
                <b>{s.title}</b>
                <span className={`pill pill-${s.expected}`}>{s.expected}</span>
              </div>
              <p className="muted" style={{ fontSize: '0.8rem', margin: '0.4rem 0 0.7rem' }}>
                {s.story}
              </p>
              <button onClick={() => run(s.id)} disabled={res === 'running'}>
                {res === 'running' ? 'running…' : '▶ Replay live'}
              </button>
              {res === 'limited' && (
                <p className="bad" style={{ fontSize: '0.8rem' }}>
                  rate limited — wait a minute (the demo is bounded too)
                </p>
              )}
              {res && res !== 'running' && res !== 'limited' && (
                <div className="pg-result">
                  <span className={`pill pill-${res.decision}`}>
                    gateway: {res.decision}
                  </span>{' '}
                  {res.matches_expected ? (
                    <span className="ok">✓ as expected</span>
                  ) : (
                    <span className="bad">✗ unexpected</span>
                  )}
                  {res.rules.length > 0 && (
                    <ul className="pg-rules">
                      {res.rules.map((r) => (
                        <li key={r.rule_id}>
                          <code>{r.rule_id}</code>: {r.reason}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </section>
  )
}
