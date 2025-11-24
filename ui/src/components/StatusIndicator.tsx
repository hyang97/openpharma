import { useEffect, useState } from 'react'

type StatusIndicatorProps = {
  apiUrl: string
}

export function StatusIndicator({ apiUrl }: StatusIndicatorProps) {
  const [isOnline, setIsOnline] = useState<boolean | null>(null)

  useEffect(() => {
    const checkHealth = async () => {
      try {
        const response = await fetch(`${apiUrl}/health`, {
          method: 'GET',
          signal: AbortSignal.timeout(5000) // 5 second timeout
        })
        setIsOnline(response.ok)
      } catch (error) {
        setIsOnline(false)
      }
    }

    checkHealth()
    const interval = setInterval(checkHealth, 30000) // Check every 30 seconds

    return () => clearInterval(interval)
  }, [apiUrl])

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
