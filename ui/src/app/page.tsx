'use client'

import { useState, useEffect } from "react"
import { ChatHeader } from "@/components/ChatHeader"
import { MessageList } from "@/components/MessageList"
import { ChatInput } from "@/components/ChatInput"
import { CitationList } from "@/components/CitationList"
import { ConversationSidebar } from "@/components/ConversationSidebar"
import { Message, Citation, ConversationSummary } from "@/types/message"

export default function Chat() {
  const [messages, setMessages] = useState<Message[]>([]) // State: messages array to store chat history
  const [input, setInput] = useState('') // State: current input value
  const [isLoading, setIsLoading] = useState(false) // State: loading indicator
  const [currConversationId, setCurrConversationId] = useState<string | null>(null) // State: current conversation, initialized to NULL to disallow ''
  const [allConversationSumm, setAllConversationSumm] = useState<ConversationSummary[]>([])
  const [currCitations, setCurrCitations] = useState<Citation[]>([])
  

  // Fetch conversations from backend
  const fetchConversations = async () => {
    try {
      const response = await fetch('http://localhost:8000/conversations')
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

  const handleResumeConversation = async (conversationId: string) => {
    try {
      const response = await fetch(`http://localhost:8000/conversations/${conversationId}`)
      const data = await response.json()

      // Set conversation ID
      setCurrConversationId(data.conversation_id)

      // Set messages from backend
      setMessages(data.messages)

      // Set conversation-wide citations
      setCurrCitations(data.citations)
    } catch (error) {
      console.error('Error resuming conversation:', error)
    }
  }

  const handleReturnHome = () => {
    setMessages([])
    setInput('')
    setIsLoading(false)
    setCurrConversationId(null)
    setCurrCitations([])
  }

  // Implement send button
  const handleSend = async () => {
    if (input.trim() === '') return // don't send empty messages

    // Save user input and clear input
    const user_input = input
    setInput('')

    // Add user message to messages array immediately
    const userMessage = {
      role: 'user',
      content: user_input
    }
    setMessages([...messages, userMessage])

    // Call FastAPI endpoint
    setIsLoading(true)
    try {
      const response = await fetch('http://localhost:8000/chat', {
        method: 'POST',
        headers:{
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          user_message: user_input,
          use_local: true,
          conversation_id: currConversationId
        })
      })
      const data = await response.json()
      
      // Save conversation_id from response
      if (data.conversation_id) {
        setCurrConversationId(data.conversation_id)
      }

      // Update conversation-wide citations from backend
      setCurrCitations(data.conversation_citations)

      // Add LLM response
      const llmMessage = {
        role: 'assistant',
        content: data.generated_response
      }

      setMessages(prev => [...prev, llmMessage])

      // Refetch conversations to update sidebar
      await fetchConversations()

    } catch (error) {
      console.error('Error calling API:', error)
      const errorMessage = {
        role: 'assistant',
        content: 'Sorry, there was an error. Please try again.'
      }

      setMessages(prev => [...prev, errorMessage])
    }
    setIsLoading(false)
  }

  return (
    <div className="flex h-screen bg-slate-900">
      {/* Sidebar - always visible */}
      <ConversationSidebar
        conversations={allConversationSumm}
        currentConversationId={currConversationId}
        onSelectConversation={handleResumeConversation}
      />

      {/* Main content area */}
      <div className="flex flex-col flex-1">
        {messages.length === 0 ? (
          // Empty state: centered input
          <div className="flex-1 flex flex-col items-center justify-center px-4">
            <h1 className="text-6xl font-bold mb-4 text-white">OpenPharma</h1>
            <p className="text-lg text-slate-400 mb-12">Your on-demand pharmaceutical research analyst</p>
            <div className="w-full max-w-3xl">
              <ChatInput value={input} onChange={setInput} onSend={handleSend} centered={true} />
            </div>
          </div>
        ) : (
          // Messages exist: normal layout with input at bottom
          <>
            <ChatHeader onReturnHome={handleReturnHome} />
            <div className="flex-1 overflow-y-auto">
              <div className="max-w-4xl mx-auto">
                <MessageList messages={messages} isLoading={isLoading}/>
                <CitationList citations={currCitations} />
              </div>
            </div>
            <ChatInput value={input} onChange={setInput} onSend={handleSend} />
          </>
        )}
      </div>
    </div>
  )
}