type ChatHeaderProps = {
  onReturnHome: () => void
}

export function ChatHeader({ onReturnHome }: ChatHeaderProps) {
  return (
    <div className="bg-slate-900 text-white p-4 shadow-sm border-b border-slate-700">
      <div className="max-w-4xl mx-auto flex items-center justify-between">
        <button onClick={onReturnHome} className="text-left hover:opacity-80 transition-opacity cursor-pointer">
          <h1 className="text-xl font-bold">OpenPharma</h1>
          <p className="text-xs text-slate-400">AI-Powered Research Intelligence</p>
        </button>
        <button
          onClick={onReturnHome}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-semibold transition-colors"
        >
          + New Conversation
        </button>
      </div>
    </div>
  )
}
