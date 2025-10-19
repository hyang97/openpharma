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
    <div className={centered ? "" : "border-t border-slate-700 bg-slate-900 p-6"}>
      <div className={`flex gap-3 ${centered ? "" : "max-w-3xl mx-auto"}`}>
        <input
          value={value}
          // input component's onChange event → extract text → call parent's onChange prop (which is setInput)
          onChange={(e) => onChange(e.target.value)}
          onKeyPress={handleKeyPress}
          placeholder="Ask a research question..."
          className="flex-1 bg-slate-800 border border-slate-600 rounded-xl px-5 py-4 text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent text-base"
        />
        {/* button component's onClick event -> call parent's onSend prop (which is handleSend) */}
        <button
          onClick={onSend}
          className="bg-blue-600 text-white px-8 py-4 rounded-xl font-medium hover:bg-blue-700 transition-colors disabled:bg-slate-700 disabled:cursor-not-allowed disabled:text-slate-500"
          disabled={!value.trim()}
        >
          Send
        </button>
      </div>
    </div>
  )
}
