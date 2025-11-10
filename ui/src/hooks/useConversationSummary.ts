import { useState, useEffect } from 'react'
import { ConversationSummary } from '@/types/message'

export function useConversationSummary(API_URL: string) {
  const [allConversationSumm, setAllConversationSumm] = useState<ConversationSummary[]>([])

  const fetchConversationSumm = async () => {
    try {
      const response = await fetch(`${API_URL}/conversations`)
      const data = await response.json()
      setAllConversationSumm(data)
    } catch (error) {
      console.error('Error fetching conversations:', error)
    }
  }

  const addFirstMessageForConversationSumm = (conversationId: string, firstMessage: string) => {
    setAllConversationSumm(prev => [{
      conversation_id: conversationId,
      first_message: firstMessage.slice(0, 100), // Truncate to 100 chars like backend 
      message_count: 1,
      last_updated: Date.now() / 1000 // Convert to seconds like backend

    }, ...prev])
  }
  
  useEffect(() => {
    fetchConversationSumm()
  }, [])

  return {
    allConversationSumm,
    setAllConversationSumm,
    fetchConversationSumm,
    addFirstMessageForConversationSumm
  }
}