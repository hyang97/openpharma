import { MessageBubble } from './MessageBubble'
import { Message } from '@/types/message'
import { useEffect, useRef } from 'react'

type MessageListProps = {
  messages: Message[]
  isLoading: boolean
  isFetching: boolean
  isStreaming: boolean
  isUpdatingCitations: boolean
}

export function MessageList({ messages, isLoading, isFetching, isStreaming, isUpdatingCitations }: MessageListProps) {
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to bottom when messages change or loading state changes
  // Don't auto-scroll during streaming to allow user to scroll freely
  useEffect(() => {
    if (isStreaming) return

    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading, isStreaming])

  return (
    <div className="space-y-6 p-6 scroll-mt-20 md:scroll-mt-0">
      {/* Skeleton loading for fetching conversation */}
      {isFetching && messages.length === 0 && (
        <>
          {/* Loading text */}
          <div className="flex items-center justify-center gap-2 text-slate-400 text-sm mb-4">
            <div className="flex gap-1">
              <span className="animate-bounce" style={{ animationDelay: '0ms' }}>●</span>
              <span className="animate-bounce" style={{ animationDelay: '150ms' }}>●</span>
              <span className="animate-bounce" style={{ animationDelay: '300ms' }}>●</span>
            </div>
            <span>Loading conversation...</span>
          </div>

          {/* User message skeleton */}
          <div className="flex justify-end">
            <div className="max-w-2xl rounded-xl px-5 py-4 bg-slate-700/50 border border-slate-600/50 animate-pulse">
              <div className="h-4 bg-slate-600/50 rounded w-48 mb-2"></div>
              <div className="h-4 bg-slate-600/50 rounded w-32"></div>
            </div>
          </div>

          {/* Assistant message skeleton */}
          <div className="flex justify-start">
            <div className="max-w-3xl rounded-xl px-5 py-4 bg-slate-800/50 border border-slate-700/50 animate-pulse">
              <div className="h-3 bg-slate-700/50 rounded w-24 mb-3"></div>
              <div className="space-y-2">
                <div className="h-4 bg-slate-700/50 rounded w-full"></div>
                <div className="h-4 bg-slate-700/50 rounded w-5/6"></div>
                <div className="h-4 bg-slate-700/50 rounded w-4/6"></div>
              </div>
            </div>
          </div>
        </>
      )}

      {/* Actual messages */}
      {messages.map((msg, index) => {
        // Skip empty assistant messages (used as placeholder during streaming)
        if (msg.role === 'assistant' && msg.content.trim() === '') {
          return null
        }
        const isLastMessage = index === messages.length - 1
        const isLastAssistant = isLastMessage && msg.role === 'assistant'
        return <MessageBubble key={index} message={msg} isStreaming={isLastAssistant && isStreaming} />
      })}

      {/* Loading indicator for LLM generation */}
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

      {/* Updating citations indicator */}
      {isUpdatingCitations && (
        <div className="flex justify-start mt-4">
          <div className="text-xs text-slate-400 flex items-center gap-2">
            <div className="flex gap-1">
              <span className="animate-bounce" style={{ animationDelay: '0ms' }}>●</span>
              <span className="animate-bounce" style={{ animationDelay: '150ms' }}>●</span>
              <span className="animate-bounce" style={{ animationDelay: '300ms' }}>●</span>
            </div>
            <span>Formatting citations...</span>
          </div>
        </div>
      )}


      {/* Invisible div at bottom for auto-scroll */}
      <div ref={messagesEndRef} />
    </div>
  )
}
