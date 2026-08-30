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

export function Decisions() {
  return (
    <Stub
      title="Decision Explorer"
      coming="Every gateway decision with its rule-by-rule verdict, evidence and policy version. Arrives with the policy engine (Phase 3)."
    />
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

export function AuditChain() {
  return (
    <Stub
      title="Audit Chain"
      coming="Hash-chained audit log with live chain verification and per-decision deterministic replay. Arrives in Phase 3."
    />
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
