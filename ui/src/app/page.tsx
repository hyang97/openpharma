'use client'

import { useState, useEffect, useRef } from "react"
import { ChatHeader } from "@/components/ChatHeader"
import { MessageList } from "@/components/MessageList"
import { ChatInput } from "@/components/ChatInput"
import { CitationList } from "@/components/CitationList"
import { ConversationSidebar } from "@/components/ConversationSidebar"
import { Message, Citation, ConversationSummary } from "@/types/message"
import { request } from "http"

export default function Chat() {
  const [messages, setMessages] = useState<Message[]>([]) // State: messages array to store chat history
  const [input, setInput] = useState('') // State: current input value
  const [allConversationSumm, setAllConversationSumm] = useState<ConversationSummary[]>([]) // State: summary for all conversations for sidebar
  const [currCitations, setCurrCitations] = useState<Citation[]>([]) // State: citations for current conversation
  const [isSidebarOpen, setIsSidebarOpen] = useState(false) // State: sidebar open/closed on mobile

  // Track current conversation selected by the user
  const [currConversationId, setCurrConversationId] = useState<string | null>(null) // State: current conversation
  const currentConversationRef = useRef<string | null>(null) // Ref: Track current conversation ID synchronously to ensure correct state updates

  // Track loading conversations
  type loadingStatus = 'loading' | 'error'
  const [loadingConversations, setLoadingConversations] = useState<Map<string, loadingStatus>>(new Map()) // State: set of loading conversations + status

  // Cache and/or fetch conversations
  const [conversationCache, setConversationCache] = useState<Map<string, {messages: Message[], citations: Citation[]}>>(new Map()) 
  const [isFetchingConversation, setIsFetchingConversation] = useState(false)

  // Derived values
  const isLoading = Boolean(currConversationId && loadingConversations.get(currConversationId) === 'loading')
  const hasError = Boolean(currConversationId && loadingConversations.get(currConversationId) === 'error')

  const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

  // Fetch conversations from backend
  const fetchConversations = async () => {
    try {
      const response = await fetch(`${API_URL}/conversations`)
      const data = await response.json()
      setAllConversationSumm(data)
    } catch (error) {
      console.error('Error fetching conversations:', error)
    }
  }

  // Fetch conversations on mount
  useEffect(() => {
    fetchConversations()
  }, [])

  const handleResumeConversation = (conversationId: string) => {
    // Update conversation ID 
    setCurrConversationId(conversationId)
    currentConversationRef.current = conversationId
    setIsSidebarOpen(false)

    // Check cache
    const cached = conversationCache.get(conversationId)
    if (cached) {
      // Cache hit: show immediately
      setMessages(cached.messages)
      setCurrCitations(cached.citations)
      setIsFetchingConversation(false)
    } else {
      // Cache miss: clear messages and show loading
      setMessages([])
      setCurrCitations([])
      setIsFetchingConversation(true)
    }

    fetch(`${API_URL}/conversations/${conversationId}`)
    .then(response => response.json())
    .then(data => {
      if (conversationId === currentConversationRef.current) {
        // Update state from backend
        setMessages(data.messages)
        setCurrCitations(data.citations)
        setIsFetchingConversation(false)
      } 

      // Update conversation cache
      setConversationCache(prev => new Map(prev).set(conversationId, {
        messages: data.messages, 
        citations: data.citations
      }))
    })
    .catch(error => {
      console.error('Error resuming conversation:', error)
      setIsFetchingConversation(false)
    })
  }

  const handleReturnHome = () => {
    setMessages([])
    setInput('')
    setCurrConversationId(null)
    currentConversationRef.current = null
    setCurrCitations([])
  }

  // Implement send button
  const handleSend = () => {
    if (input.trim() === '' || isLoading) return // don't send empty messages or if currently loading

    // Save user input and clear input
    const user_input = input
    setInput('') 

    // Add user message to messages array immediately
    const userMessage = {
      role: 'user',
      content: user_input
    }
    setMessages([...messages, userMessage])

    // Scroll to header height when first message is sent (mobile only)
    if (messages.length === 0 && window.innerWidth < 768) {
      setTimeout(() => {
        const header = document.querySelector('header') || document.querySelector('[class*="sticky"]')
        const headerHeight = header?.getBoundingClientRect().height || 60
        window.scrollTo({ top: headerHeight, behavior: 'smooth' })
      }, 100)
    }

    // Get existing conversation or create a new conversation (generating UUID client-side)
    let requestConversationId = currConversationId
    if (!requestConversationId) {
      requestConversationId = crypto.randomUUID()
      setCurrConversationId(requestConversationId)
      currentConversationRef.current = requestConversationId

      // Optimistically add to sidebar (will be replaced by real data when backend responds)
      setAllConversationSumm(prev => [{
        conversation_id: requestConversationId as string,  // Safe: we just assigned it above
        first_message: user_input.slice(0, 100),  // Truncate to 100 chars like backend
        message_count: 1,
        last_updated: Date.now() / 1000 // Convert to seconds (backend uses seconds)
      }, ...prev])
    }

    // Mark conversation as loading
    setLoadingConversations(prev => new Map(prev).set(requestConversationId, 'loading'))

    // Non-blocking request with .then() (instead of await)
    fetch(`${API_URL}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_message: user_input,
        use_local: true,
        conversation_id: requestConversationId,
        use_reranker: true
      })
    })
    .then(response => response.json())
    .then(data => {
      // Remove from loading set
      setLoadingConversations(prev => {
        const next = new Map(prev)
        next.delete(requestConversationId)
        return next
      })
      // Check if still on same conversation
      if (requestConversationId !== currentConversationRef.current) {
        // User switched away, just update sidebar
        fetchConversations()
        return // (user switched away) returns NULL value for convResponse
      }
      else {
        // User still on same conversation, refetch full conversation from backend
        return fetch(`${API_URL}/conversations/${requestConversationId}`)
      }
    })
    .then(convResponse => {
      if (!convResponse) return // (user switched away) return null value for convData
      return convResponse.json()
    })
    .then(convData => {
      if (!convData) return 
      
      // Update state from backend
      setMessages(convData.messages)
      setCurrCitations(convData.citations)

      // Update conversation cache
      setConversationCache(prev => new Map(prev).set(requestConversationId, {
        messages: convData.messages, 
        citations: convData.citations
      }))

      // Update sidebar
      fetchConversations()
    })
    .catch(error => {
      console.error('Error calling API:', error)

      // Mark conversation as error
      setLoadingConversations(prev => new Map(prev).set(requestConversationId, 'error'))

      // Check is user is still on the same conversation
      if (requestConversationId === currentConversationRef.current) {
        // Still on same conversation, restore input
        setInput(user_input) 
      } else {
        // User switched away, just log it
        console.log('Message failed in background conversation:', requestConversationId)
      }
    })
  }

  return (
    <div className="flex h-screen bg-slate-900">
      {/* Sidebar */}
      <ConversationSidebar
        conversations={allConversationSumm}
        currentConversationId={currConversationId}
        onSelectConversation={handleResumeConversation}
        isOpen={isSidebarOpen}
        onToggle={() => setIsSidebarOpen(!isSidebarOpen)}
      />

      {/* Main content area */}
      <div className="flex flex-col flex-1">
        {messages.length === 0 && !currConversationId ? (
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
            <p className="text-base sm:text-lg mb-8 sm:mb-12 text-center leading-relaxed">
              <span className="bg-accent text-white px-2 py-1 rounded" style={{ boxDecorationBreak: 'clone', WebkitBoxDecorationBreak: 'clone' }}>Your on-demand pharmaceutical research analyst</span>
            </p>
            <div className="w-full max-w-3xl">
              <ChatInput value={input} onChange={setInput} onSend={handleSend} centered={true} disabled={isLoading} />
            </div>
          </div>
        ) : (
          // Messages exist: normal layout with input at bottom
          <>
            <ChatHeader
              onReturnHome={handleReturnHome}
              onToggleSidebar={() => setIsSidebarOpen(!isSidebarOpen)}
            />
            {/* Error banner - fixed position, always visible */}
            {hasError && (
              <div className="bg-red-900 text-red-200 p-3 flex justify-between items-center mx-4 sm:mx-6 mt-2 rounded">
                <span>Previous message failed to send. Please try again.</span>
                <button
                  onClick={() => {
                    if (currConversationId) {
                      setLoadingConversations(prev => {
                        const next = new Map(prev)
                        next.delete(currConversationId)
                        return next
                      })
                    }
                  }}
                  className="text-red-200 hover:text-white ml-4"
                >
                  ×
                </button>
              </div>
            )}
            <div className="flex-1 overflow-y-auto">
              <div className="max-w-4xl mx-auto px-4 sm:px-6">
                <MessageList messages={messages} isLoading={isLoading} isFetching={isFetchingConversation}/>
                <CitationList citations={currCitations} />
              </div>
            </div>
            <ChatInput value={input} onChange={setInput} onSend={handleSend} disabled={isLoading || isFetchingConversation}/>
          </>
        )}
      </div>
    </div>
  )
}