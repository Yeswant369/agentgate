import { useEffect, useState } from 'react'

type HealthState = 'checking' | 'ready' | 'down'

export function HealthBadge() {
  const [state, setState] = useState<HealthState>('checking')

  useEffect(() => {
    let cancelled = false
    fetch('/api/health/ready')
      .then((r) => {
        if (!cancelled) setState(r.ok ? 'ready' : 'down')
      })
      .catch(() => {
        if (!cancelled) setState('down')
      })
    return () => {
      cancelled = true
    }
  }, [])

  const label = { checking: 'checking…', ready: 'gateway ready', down: 'gateway not ready' }[state]
  return <span className={`badge badge-${state}`}>{label}</span>
}
