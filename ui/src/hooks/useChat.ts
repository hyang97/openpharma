import { Message, Citation } from '@/types/message'
import { useState, useEffect, useRef } from "react"
import { useLoadingState } from '@/hooks/useLoadingState'
import { useConversationSummary } from './useConversationSummary'
import { useConversationCache } from './useConversationCache'

export function useChat(API_URL: string) {
    // Hook: Fetch conversations from backend
    const { 
        allConversationSumm, 
        setAllConversationSumm, fetchConversationSumm, addFirstMessageForConversationSumm 
    } = useConversationSummary(API_URL)
    
    // Hook: Maintain conversation cache
    const {
        conversationCache, 
        setConversationCache,  addMessageToCache, removeLastMessageFromCache 
    } = useConversationCache()
    
    // Hook: Manage loading state
    const {
        loadingConversations, clearLoading,
        setLoading, setStreaming, setUpdatingCitations, setSendError, setResumeError,
        isLoading, isStreaming, isUpdatingCitations, hasSendError, hasResumeError
    } = useLoadingState()

    // Coordination state (active conversation)
    const [currConversationId, setCurrConversationId] = useState<string | null>(null) // State: current conversation
    const currentConversationRef = useRef<string | null>(null) // Ref: Track current conversation ID synchronously to ensure correct state updates
    const [isFetchingConversation, setIsFetchingConversation] = useState(false)

    // Display state
    const [messages, setMessages] = useState<Message[]>([]) // State: messages array to store chat history
    const [currCitations, setCurrCitations] = useState<Citation[]>([]) // State: citations for current conversation
    const [input, setInput] = useState('') // State: current input value

    const processMessage = () => {
        // Don't send message if empty input or current loading conversation 
        if (input.trim() === '' || isLoading(currConversationId)) return 

        // Check if this is the first message
        const isFirstMessage = messages.length === 0 && window.innerWidth < 768

        // Save user input and clear input 
        const user_input = input 
        setInput('')

        // Add user message to messages array
        const userMessage = {
            role: 'user',
            content: user_input 
        }
        setMessages([...messages, userMessage])

        // Scroll to header height when first message is sent 
        if (isFirstMessage) {
            setTimeout(() => {
                const header = document.querySelector('header') || document.querySelector('[class*="sticky"]')
                const headerHeight = header?.getBoundingClientRect().height || 60
                window.scrollTo({ top: headerHeight, behavior: 'smooth' })
            }, 100)
        }

        // Set conversation for request
        let requestConversationId = currConversationId
        if (requestConversationId) {
            // We have a current conversation, add user message to cache while loading 
            addMessageToCache(requestConversationId, userMessage)
        
        } else {
            // We do not have a conversation ID, create a new conversation
            requestConversationId = crypto.randomUUID()
            setCurrConversationId(requestConversationId)
            currentConversationRef.current = requestConversationId

            // Initialize empty cache entry 
            setConversationCache(requestConversationId, [userMessage], [])

            // Optimistically add to sidebar, will be replaced by real data when backend responds
            addFirstMessageForConversationSumm(requestConversationId, user_input)
        }

        // Mark conversation as loading
        setLoading(requestConversationId)

        // Non-blocking request with .then() (instead of await)
        fetch(`${API_URL}/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_message: user_input,
                use_local: true,
                conversation_id: requestConversationId,
                use_reranker: true
            }), 
            signal: AbortSignal.timeout(360000) // 6 minute timeout
        })
        .then(chatResponse => {
            if (!chatResponse.ok) {
                throw new Error(`Failed to process message: ${chatResponse.status}`)
            }
            // Received response, remove conversation from loading set
            clearLoading(requestConversationId)

            // Refetch full conversation for updating cache
            return fetch(`${API_URL}/conversations/${requestConversationId}`, {
                signal: AbortSignal.timeout(120000) // 2 minute timeout
            })
        })
        .then(convResponse => convResponse.json())
        .then(convData => {
            // Update conversation cache
            setConversationCache(requestConversationId, convData.messages, convData.citations)

            // If user is still on this conversation, update UI with latest conversation
            if (requestConversationId === currentConversationRef.current) {
                setMessages(convData.messages)
                setCurrCitations(convData.citations)
            }
            
            // Update sidebar
            fetchConversationSumm()
        })
        .catch(error => {
            if (error.name === 'TimeoutError' || error.name === 'AbortError'){
                console.error('Request timeout for /chat:', error)
            } else {
                console.error('Error processing message with /chat:', error)
            }

            // Mark conversation as error
            setSendError(requestConversationId)

            // Rollback - remove the user message from conversation cache (initially added optimistically while loading)
            removeLastMessageFromCache(requestConversationId)

            // Check if user is still on the same conversation 
            if (requestConversationId === currentConversationRef.current) {
                // Still on same conversation, restore input
                setInput(user_input)
            } else {
                // User switched away, log the error
                console.log('Process message failed in background conversation', requestConversationId)
            }
        })
    }

    const resumeConversation = (conversationId: string) => {
        // Update conversation ID
        setCurrConversationId(conversationId)
        currentConversationRef.current = conversationId

        // Check cache
        const cached = conversationCache.get(conversationId)
        if (cached) {
            // Cache hit: show immediately 
            setMessages(cached.messages)
            setCurrCitations(cached.citations)
            setIsFetchingConversation(false)
        } else {
            setMessages([])
            setCurrCitations([])
            setIsFetchingConversation(true)
        }

        // Fetch from backend (always runs to ensure fresh data)
        fetch(`${API_URL}/conversations/${conversationId}`, {
            signal: AbortSignal.timeout(120000) // 2 minute timeout
        })
        .then(response => response.json())
        .then(data => {
            // Only update UI if still on this conversation
            if (conversationId === currentConversationRef.current) {
                setMessages(data.messages)
                setCurrCitations(data.citations)
                setIsFetchingConversation(false)
            }
            // Always update cache even if switched away 
            setConversationCache(conversationId, data.messages, data.citations)
        })
        .catch(error => {
            if (error.name === 'TimeoutError' || error.name === 'AbortError'){
                console.error('Request timeout for /conversations/conversationId:', error)
            } else {
                console.error('Error fetching conversation from /conversations/conversationId:', error)
            }
            // Only clear loading state if still on this conversation
            if (conversationId === currentConversationRef.current) {
                setIsFetchingConversation(false)
            }
            setResumeError(conversationId)
        })
    }

    const returnHome = () => {
        setMessages([])
        setInput('')
        setCurrConversationId(null)
        currentConversationRef.current = null 
        setCurrCitations([])
    }

    return {
        // State
        currConversationId, messages, currCitations, input, allConversationSumm, isFetchingConversation,
        // State setters
        setCurrConversationId, setMessages, setCurrCitations, setInput, clearLoading,
        // State getters
        isLoading, hasSendError, hasResumeError,
        // Actions
        processMessage, resumeConversation, returnHome

    }
}