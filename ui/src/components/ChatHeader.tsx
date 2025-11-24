import { StatusIndicator } from './StatusIndicator'

type ChatHeaderProps = {
  onReturnHome: () => void
  onToggleSidebar?: () => void
  apiUrl: string
}

export function ChatHeader({ onReturnHome, onToggleSidebar, apiUrl }: ChatHeaderProps) {
  return (
    <div className="bg-slate-900 text-white py-3 md:py-4 px-4 shadow-sm border-b border-slate-700 sticky top-0 z-20">
      <div className="max-w-4xl mx-auto flex items-center justify-between gap-3 min-h-[40px]">
        {/* Hamburger menu - only visible on mobile */}
        {onToggleSidebar && (
          <button
            onClick={onToggleSidebar}
            className="md:hidden p-2 flex items-center justify-center hover:bg-slate-800 rounded-lg transition-colors flex-shrink-0 -mt-1"
            aria-label="Toggle sidebar"
          >
            <span className="text-2xl text-slate-300 leading-none">☰</span>
          </button>
        )}

        <div className="flex-1 md:flex-none self-center">
          <button onClick={onReturnHome} className="text-left hover:opacity-80 transition-opacity cursor-pointer block">
            <h1 className="text-base md:text-xl font-bold leading-tight" style={{ fontFamily: 'var(--font-noto-sans-jp)' }}>OpenPharma</h1>
            <p className="text-[10px] md:text-xs text-slate-400 hidden sm:block leading-tight">AI-Powered Research Intelligence</p>
          </button>
        </div>

        <div className="flex items-center gap-3">
          <StatusIndicator apiUrl={apiUrl} />
          <button
            onClick={onReturnHome}
            className="px-3 py-1.5 md:px-4 md:py-2 bg-accent hover:bg-accent-hover text-white rounded-lg text-xs md:text-sm font-semibold transition-colors whitespace-nowrap flex-shrink-0 self-center"
          >
            <span className="hidden sm:inline">+ New Conversation</span>
            <span className="sm:hidden">+ New</span>
          </button>
        </div>
      </div>
    </div>
  )
}
