'use client'

import { useState } from 'react'
import { ConversationSummary } from '@/types/message'

type ConversationSidebarProps = {
  conversations: ConversationSummary[]
  currentConversationId: string | null
  onSelectConversation: (conversationId: string) => void
}

export function ConversationSidebar({
  conversations,
  currentConversationId,
  onSelectConversation
}: ConversationSidebarProps) {
  const [isExpanded, setIsExpanded] = useState(false)

  if (!isExpanded) {
    return (
      <div className="w-12 bg-slate-800 border-r border-slate-700 flex items-start p-2">
        <button
          onClick={() => setIsExpanded(true)}
          className="p-2 hover:bg-slate-700 rounded transition-colors"
          title="Expand sidebar"
        >
          <span className="text-slate-400">☰</span>
        </button>
      </div>
    )
  }

  return (
    <div className="w-64 bg-slate-800 border-r border-slate-700 flex flex-col">
      <div className="p-4 border-b border-slate-700 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wide">Conversations</h2>
        <button
          onClick={() => setIsExpanded(false)}
          className="p-1 hover:bg-slate-700 rounded transition-colors"
          title="Collapse sidebar"
        >
          <span className="text-slate-400">‹</span>
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        {conversations.length === 0 ? (
          <div className="text-sm text-slate-400">No conversations yet</div>
        ) : (
          <div className="space-y-2">
            {conversations.map((conv) => (
              <button
                key={conv.conversation_id}
                onClick={() => onSelectConversation(conv.conversation_id)}
                className={`w-full text-left p-3 rounded-lg transition-colors ${
                  currentConversationId === conv.conversation_id
                    ? 'bg-slate-700 border border-blue-500'
                    : 'bg-slate-900 border border-slate-700 hover:bg-slate-700'
                }`}
              >
                <div className="text-sm text-slate-200 truncate mb-1">
                  {conv.first_message || 'New conversation'}
                </div>
                <div className="text-xs text-slate-400">
                  {conv.message_count} message{conv.message_count !== 1 ? 's' : ''}
                </div>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
