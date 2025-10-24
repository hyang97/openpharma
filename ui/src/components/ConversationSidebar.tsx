'use client'

import { useState, useEffect } from 'react'
import { ConversationSummary } from '@/types/message'

type ConversationSidebarProps = {
  conversations: ConversationSummary[]
  currentConversationId: string | null
  onSelectConversation: (conversationId: string) => void
  isOpen: boolean
  onToggle: () => void
}

export function ConversationSidebar({
  conversations,
  currentConversationId,
  onSelectConversation,
  isOpen,
  onToggle
}: ConversationSidebarProps) {
  const [isExpanded, setIsExpanded] = useState(false)

  // Auto-expand on mobile when sidebar opens
  useEffect(() => {
    if (isOpen && window.innerWidth < 768) {
      setIsExpanded(true)
    }
  }, [isOpen])

  return (
    <>
      {/* Mobile overlay backdrop */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black bg-opacity-50 z-40 md:hidden"
          onClick={onToggle}
        />
      )}

      {/* Sidebar */}
      <div
        className={`bg-slate-800 border-r border-slate-700 flex flex-col transition-all duration-300 ease-in-out
          fixed md:static inset-y-0 left-0 z-50
          ${isOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}
          ${isExpanded ? 'w-64' : 'w-64 md:w-12'}
        `}
      >
      {/* Header/Toggle Button */}
      <div className={`py-3 md:py-4 flex items-center ${isExpanded ? 'px-4 justify-between' : 'justify-center'}`}>
        {!isExpanded ? (
          <button
            onClick={() => setIsExpanded(true)}
            className="hidden md:flex hover:bg-slate-700 rounded-lg transition-colors w-8 h-8 items-center justify-center flex-shrink-0"
            title="Expand sidebar"
          >
            <span className="text-slate-400 text-lg leading-none">☰</span>
          </button>
        ) : (
          <>
            <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wide whitespace-nowrap">
              Conversations
            </h2>
            {/* Close/collapse button - closes on mobile, collapses on desktop */}
            <button
              onClick={() => {
                if (window.innerWidth < 768) {
                  onToggle() // Close on mobile
                } else {
                  setIsExpanded(false) // Collapse on desktop
                }
              }}
              className="w-8 h-8 hover:bg-slate-700 rounded-lg transition-colors flex items-center justify-center flex-shrink-0"
              title="Close sidebar"
            >
              <span className="text-slate-400 text-lg leading-none">‹</span>
            </button>
          </>
        )}
      </div>

      {/* Conversation List */}
      <div
        className={`flex-1 overflow-y-auto p-4 transition-opacity duration-300
          ${isExpanded ? 'opacity-100' : 'md:opacity-0 md:pointer-events-none'}
        `}
      >
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
    </>
  )
}
