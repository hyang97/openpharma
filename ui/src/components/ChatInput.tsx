type ChatInputProps = {
  value: string
  onChange: (value: string) => void
  onSend: () => void
  centered?: boolean
  disabled?: boolean
}

export function ChatInput({ value, onChange, onSend, centered = false, disabled = false }: ChatInputProps) {
  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      onSend()
    }
  }

  return (
    <div className={centered ? "" : "border-t border-slate-700 bg-slate-900 p-3 sm:p-4 sticky bottom-0 z-20"}>
      <div className={`relative ${centered ? "" : "max-w-3xl mx-auto"}`}>
        <textarea
          value={value}
          // textarea component's onChange event → extract text → call parent's onChange prop (which is setInput)
          onChange={(e) => onChange(e.target.value)}
          onKeyPress={handleKeyPress}
          placeholder="Ask a research question..."
          rows={1}
          disabled={disabled}
          className={`w-full bg-slate-800 border border-slate-600 rounded-xl px-4 py-3 sm:px-5 sm:py-4 pr-12 sm:pr-14 text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-accent focus:border-transparent text-base resize-none overflow-hidden shadow-[0_0_20px_rgba(0,0,255,0.15)] hover:shadow-[0_0_25px_rgba(0,0,255,0.25)] focus:shadow-[0_0_30px_rgba(0,0,255,0.4)] transition-all ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
          style={{
            minHeight: '52px',
            maxHeight: '200px',
          }}
          onInput={(e) => {
            const target = e.target as HTMLTextAreaElement
            target.style.height = '52px'
            target.style.height = `${Math.min(target.scrollHeight, 200)}px`
          }}
        />
        {/* button component's onClick event -> call parent's onSend prop (which is handleSend) */}
        <button
          onClick={onSend}
          className="absolute right-2 bottom-3 sm:bottom-4 bg-accent text-white w-9 h-9 sm:w-10 sm:h-10 rounded-full flex items-center justify-center hover:bg-accent-hover transition-colors disabled:bg-slate-700 disabled:cursor-not-allowed"
          disabled={!value.trim() || disabled}
          aria-label="Send message"
        >
          <span className="text-xl">›</span>
        </button>
      </div>

      {/* Disclaimer */}
      <p className="text-center text-[10px] sm:text-xs text-slate-500 mt-2 sm:mt-3 px-2 italic">
        This is currently a personal learning project, use information at personal and professional risk. Enjoy and have fun!
      </p>
    </div>
  )
}
