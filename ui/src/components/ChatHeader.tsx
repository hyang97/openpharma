type ChatHeaderProps = {
  onReturnHome: () => void
  onToggleSidebar?: () => void
}

export function ChatHeader({ onReturnHome, onToggleSidebar }: ChatHeaderProps) {
  return (
    <div className="bg-slate-900 text-white p-4 shadow-sm border-b border-slate-700">
      <div className="max-w-4xl mx-auto flex items-center justify-between gap-3">
        {/* Hamburger menu - only visible on mobile */}
        {onToggleSidebar && (
          <button
            onClick={onToggleSidebar}
            className="md:hidden p-2 hover:bg-slate-800 rounded transition-colors"
            aria-label="Toggle sidebar"
          >
            <span className="text-2xl text-slate-300">☰</span>
          </button>
        )}

        <button onClick={onReturnHome} className="text-left hover:opacity-80 transition-opacity cursor-pointer flex-1 md:flex-none">
          <h1 className="text-lg md:text-xl font-bold">OpenPharma</h1>
          <p className="text-xs text-slate-400 hidden sm:block">AI-Powered Research Intelligence</p>
        </button>

        <button
          onClick={onReturnHome}
          className="px-3 py-2 md:px-4 md:py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs md:text-sm font-semibold transition-colors whitespace-nowrap"
        >
          <span className="hidden sm:inline">+ New Conversation</span>
          <span className="sm:hidden">+ New</span>
        </button>
      </div>
    </div>
  )
}
