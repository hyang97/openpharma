import { useEffect, useState } from 'react'

type StatusIndicatorProps = {
  apiUrl: string
  isBackendActive?: boolean // True when streaming or loading
}

export function StatusIndicator({ apiUrl, isBackendActive = false }: StatusIndicatorProps) {
  const [isOnline, setIsOnline] = useState<boolean | null>(null)

  useEffect(() => {
    const checkHealth = async () => {
      try {
        const response = await fetch(`${apiUrl}/health`, {
          method: 'GET',
          signal: AbortSignal.timeout(5000) // 5 second timeout
        })
        setIsOnline(response.ok)
      } catch {
        setIsOnline(false)
      }
    }

    checkHealth()
    const interval = setInterval(checkHealth, 30000) // Check every 30 seconds

    return () => clearInterval(interval)
  }, [apiUrl])

  // Don't show if backend is actively working (streaming/loading)
  if (isBackendActive) {
    return null
  }

  // Only show when offline
  if (isOnline !== false) {
    return null
  }

  return (
    <div className="flex items-center gap-2 text-xs">
      <div className="w-2 h-2 rounded-full bg-red-500" />
      <span className="text-slate-400">
        Backend Offline
      </span>
    </div>
  )
}
