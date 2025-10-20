import { Message } from '@/types/message'

type MessageBubbleProps = {
  message: Message
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === 'user'

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div className={`max-w-3xl rounded-xl px-5 py-4 ${
        isUser
          ? 'bg-slate-700 text-white'
          : 'bg-slate-800 border border-slate-700'
      }`}>
        <div className={`text-xs font-semibold mb-2 uppercase tracking-wide ${isUser ? 'text-slate-300' : 'text-slate-400'}`}>
          {isUser ? 'You' : 'OpenPharma'}
        </div>
        <div className={`text-base leading-relaxed whitespace-pre-wrap ${isUser ? 'text-white' : 'text-slate-100'}`}>
          {message.content}
        </div>
      </div>
    </div>
  )
}
