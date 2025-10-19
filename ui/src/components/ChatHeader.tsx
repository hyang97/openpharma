type ChatHeaderProps = { 
  onReturnHome: () => void 
}

export function ChatHeader({ onReturnHome }: ChatHeaderProps) {
  return (
    <div className="bg-slate-900 text-white p-4 shadow-sm border-b border-slate-700">
      <div className="max-w-4xl mx-auto">
        <button onClick={onReturnHome} className="text-left hover:opacity-80 transition-opacity cursor-pointer">
          <h1 className="text-xl font-bold">OpenPharma</h1>
          <p className="text-xs text-slate-400">AI-Powered Research Intelligence</p>
        </button>
      </div>
    </div>
  )
}
