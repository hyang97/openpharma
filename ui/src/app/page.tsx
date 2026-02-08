'use client'

import { useState } from "react"
import { ChatHeader } from "@/components/ChatHeader"
import { MessageList } from "@/components/MessageList"
import { ChatInput } from "@/components/ChatInput"
import { CitationList } from "@/components/CitationList"
import { ConversationSidebar } from "@/components/ConversationSidebar"
import { StatusIndicator } from "@/components/StatusIndicator"
import { SuggestedQuestions } from "@/components/SuggestedQuestions"
import { useChat } from "@/hooks/useChat"

export default function Chat() {
  const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
  
  // UI state
  const [isSidebarOpen, setIsSidebarOpen] = useState(false) // State: sidebar open/closed on mobile

  // Chat hook
  const chat = useChat(API_URL, true)

  const handleReturnHome = () => {
    chat.returnHome()
  }

  const handleSend = () => {
    chat.processMessage()
  }

  const handleSuggestedQuestion = (question: string) => {
    chat.setInput(question)
    chat.processMessage(undefined, question)
  }

  const handleResumeConversation = (conversationId: string) => {
    chat.resumeConversation(conversationId)
    setIsSidebarOpen(false)
  }

  return (
    <div className="flex h-screen bg-slate-900">
      {/* Sidebar */}
      <ConversationSidebar
        conversations={chat.allConversationSumm}
        currentConversationId={chat.currConversationId}
        onSelectConversation={handleResumeConversation}
        isOpen={isSidebarOpen}
        onToggle={() => setIsSidebarOpen(!isSidebarOpen)}
      />

      {/* Main content area */}
      <div className="flex flex-col flex-1">
        {chat.messages.length === 0 && !chat.currConversationId ? (
          // Empty state: centered input
          <div className="flex-1 flex flex-col items-center justify-center px-4">
            {/* Mobile hamburger menu for landing page */}
            <button
              onClick={() => setIsSidebarOpen(!isSidebarOpen)}
              className="md:hidden fixed top-4 left-4 w-10 h-10 flex items-center justify-center bg-slate-800 hover:bg-slate-700 rounded-lg transition-colors z-30 shadow-lg"
              aria-label="Toggle sidebar"
            >
              <span className="text-2xl text-slate-300">☰</span>
            </button>

            <h1 className="text-4xl sm:text-5xl md:text-6xl font-bold mb-4 text-white text-center" style={{ fontFamily: 'var(--font-noto-sans-jp)' }}>OpenPharma</h1>
            <p className="text-base sm:text-lg mb-4 text-center leading-relaxed">
              <span className="bg-accent text-white px-2 py-1 rounded" style={{ boxDecorationBreak: 'clone', WebkitBoxDecorationBreak: 'clone' }}>Your on-demand pharmaceutical research analyst</span>
            </p>
            <div className="mb-8 sm:mb-12">
              <StatusIndicator apiUrl={API_URL} />
            </div>
            <div className="w-full max-w-3xl">
              <ChatInput value={chat.input} onChange={chat.setInput} onSend={handleSend} centered={true} disabled={chat.isLoading(chat.currConversationId)} />
            </div>
            <div className="w-full max-w-3xl mt-4">
              <SuggestedQuestions onSelectQuestion={handleSuggestedQuestion} />
            </div>
          </div>
        ) : (
          // Messages exist: normal layout with input at bottom
          <>
            <ChatHeader
              onReturnHome={handleReturnHome}
              onToggleSidebar={() => setIsSidebarOpen(!isSidebarOpen)}
              apiUrl={API_URL}
              isBackendActive={chat.isLoading(chat.currConversationId) || chat.isStreaming(chat.currConversationId)}
            />
            {/* Send Error banner - fixed position, always visible */}
            {chat.hasSendError(chat.currConversationId) && (
              <div className="bg-red-900 text-red-200 p-3 flex justify-between items-center mx-4 sm:mx-6 mt-2 rounded">
                <span>Unable to reach backend. Please check that the API is running and try again.</span>
                <button
                  onClick={() => chat.currConversationId && chat.clearLoading(chat.currConversationId)}
                  className="text-red-200 hover:text-white ml-4">×</button>
              </div>
            )}

            {/* Resume Conversation Error banner - fixed position, always visible */}
            {chat.hasResumeError(chat.currConversationId) && (
              <div className="bg-red-900 text-red-200 p-3 flex justify-between items-center mx-4 sm:mx-6 mt-2 rounded">
                <div className="flex items-center gap-4">
                  <span>Failed to load conversation. Please try again later.</span>
                  <button
                    onClick={() => chat.currConversationId && handleResumeConversation(chat.currConversationId)}
                    className="bg-red-800 hover:bg-red-700 px-3 py-1 rounded text-sm">
                    Retry
                  </button>
                </div>
                <button onClick={() => chat.currConversationId && chat.clearLoading(chat.currConversationId)}
                        className="text-red-200 hover:text-white ml-4">×</button>
              </div>
            )}

            <div className="flex-1 overflow-y-auto">
              <div className="max-w-4xl mx-auto px-4 sm:px-6">
                <MessageList 
                  messages={chat.messages} 
                  isLoading={chat.isLoading(chat.currConversationId)} 
                  isFetching={chat.isFetchingConversation}
                  isStreaming={chat.isStreaming(chat.currConversationId)}
                  isUpdatingCitations={chat.isUpdatingCitations(chat.currConversationId)}
                />
                <CitationList citations={chat.currCitations} />
              </div>
            </div>
            <ChatInput value={chat.input} onChange={chat.setInput} onSend={handleSend} disabled={chat.isLoading(chat.currConversationId) || chat.isFetchingConversation}/>
          </>
        )}
      </div>
    </div>
  )
}