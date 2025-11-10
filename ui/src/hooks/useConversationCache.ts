import { useState } from 'react'
import { Message, Citation } from '@/types/message'

export function useConversationCache() {
    const [conversationCache, setCache] = useState<Map<string, {messages: Message[], citations: Citation[]}>>(new Map()) 

    // Update conversation by ID with full message array and citation array
    const setConversationCache = (conversationId: string, messages: Message[], citations: Citation[]) => {
        setCache(prev => new Map(prev).set(conversationId, { messages, citations }))
    }

    // Update conversation by ID with a single message
    const addMessageToCache = (conversationId: string, message: Message) => {
        const cached = conversationCache.get(conversationId)
        
        // If conversation not in cache, do nothing
        if (!cached) return 

        const updatedConversation = { 
            messages: [...cached.messages, message], 
            citations: cached.citations
        }
        setCache(prev => new Map(prev).set(conversationId, updatedConversation))
    }

    // Update conversation by ID by removing the last message
    const removeLastMessageFromCache = (conversationId: string) => {
        const cached = conversationCache.get(conversationId)

        // If conversation not in cache or has no messages, do nothing
        if (!cached || cached.messages.length === 0) return  

        const updatedConversation = {
            messages: cached.messages.slice(0, -1),
            citations: cached.citations
        }
        setCache(prev => new Map(prev).set(conversationId, updatedConversation))
    }

    return {
        conversationCache,
        setConversationCache,
        addMessageToCache,
        removeLastMessageFromCache
    }

}