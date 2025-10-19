'use client'

import { useState } from "react"
import { ChatHeader } from "@/components/ChatHeader"
import { MessageList } from "@/components/MessageList"
import { ChatInput } from "@/components/ChatInput"
import { Message } from "@/types/message"

export default function Chat() {
  const [messages, setMessages] = useState<Message[]>([]) // State: messages array to store chat history
  const [input, setInput] = useState('') // State: current input value
  const [isLoading, setIsLoading] = useState(false) // State: loading indicator

  const handleReturnHome = () => {
    setMessages([])
    setInput('')
    setIsLoading(false)
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
      const response = await fetch('http://localhost:8000/ask', {
        method: 'POST',
        headers:{
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          question: user_input,
          use_local: true
        })
      })

      const data = await response.json()

      // Add LLM response with citations 
      const llmMessage = {
        role: 'assistant',
        content: data.answer,
        citations: data.citations
      }
      
      setMessages(prev => [...prev, llmMessage])

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
    <div className="flex flex-col h-screen bg-slate-900">
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
            </div>
          </div>
          <ChatInput value={input} onChange={setInput} onSend={handleSend} />
        </>
      )}
    </div>
  )
}