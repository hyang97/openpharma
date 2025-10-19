import { MessageBubble } from './MessageBubble'
import { Message } from '@/types/message'

type MessageListProps = {
  messages: Message[]
  isLoading: boolean
}

export function MessageList({ messages, isLoading }: MessageListProps) {
  return (
    <div className="space-y-6 p-6">
      {messages.map((msg, index) => (
        <MessageBubble key={index} message={msg} />
      ))}

      {/* Loading indicator */}
      {isLoading && (
        <div className="flex justify-start">
          <div className="max-w-3xl rounded-xl px-5 py-4 bg-slate-800 border border-slate-700">
            <div className="text-xs font-semibold mb-2 uppercase tracking-wide text-slate-400">
              OpenPharma
            </div>
            <div className="flex items-center gap-2 text-slate-300">
              <div className="flex gap-1">
                <span className="animate-bounce" style={{ animationDelay: '0ms' }}>●</span>
                <span className="animate-bounce" style={{ animationDelay: '150ms' }}>●</span>
                <span className="animate-bounce" style={{ animationDelay: '300ms' }}>●</span>
              </div>
              <span className="text-sm">Thinking...</span>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
