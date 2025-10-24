type ChatInputProps = {
  value: string
  onChange: (value: string) => void
  onSend: () => void
  centered?: boolean
}

export function ChatInput({ value, onChange, onSend, centered = false }: ChatInputProps) {
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
          className="w-full bg-slate-800 border border-slate-600 rounded-xl px-4 py-3 sm:px-5 sm:py-4 pr-12 sm:pr-14 text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent text-base resize-none overflow-hidden"
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
          className="absolute right-2 bottom-3 sm:bottom-4 bg-blue-500 text-white w-9 h-9 sm:w-10 sm:h-10 rounded-full flex items-center justify-center hover:bg-blue-600 transition-colors disabled:bg-slate-700 disabled:cursor-not-allowed"
          disabled={!value.trim()}
          aria-label="Send message"
        >
          <span className="text-xl">›</span>
        </button>
      </div>
    </div>
  )
}
