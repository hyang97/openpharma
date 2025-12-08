import { Message, Citation } from '@/types/message'
import { useState, useRef } from "react"
import { useLoadingState } from '@/hooks/useLoadingState'
import { useConversationSummary } from './useConversationSummary'
import { useConversationCache } from './useConversationCache'
import { useAnonymousUser } from './useAnonymousUser'

export function useChat(API_URL: string, useStreaming = false) {
    // Hook: Get anonymous user ID
    const userId = useAnonymousUser()

    // Hook: Fetch conversations from backend
    const {
        allConversationSumm,
        fetchConversationSumm, addFirstMessageForConversationSumm
    } = useConversationSummary(API_URL, userId)

    // Hook: Maintain conversation cache
    const {
        conversationCache,
        setConversationCache,  addMessageToCache, removeLastMessageFromCache
    } = useConversationCache()

    // Hook: Manage loading state
    const {
        clearLoading,
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

    const streamResponse = async (requestConversationId: string, user_input: string) => {
        let reader: ReadableStreamDefaultReader<Uint8Array> | null = null
        let timeoutId: NodeJS.Timeout | null = null
        let isTimedOut = false

        // Timing metrics
        const requestStartTime = Date.now()
        let firstTokenTime: number | null = null
        let tokenCount = 0
        let totalInterTokenTime = 0

        try {
            const response = await fetch(`${API_URL}/chat/stream`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    user_message: user_input,
                    user_id: userId,
                    conversation_id: requestConversationId,
                    use_reranker: true,
                    additional_chunks_per_doc: 20
                })
            })

            if (!response.ok) throw new Error(`Stream failed: ${response.status}`)

            reader = response.body!.getReader() // ! is a non-null assert, as response.body is not null since we checked response.ok

            const decoder = new TextDecoder()
            let streamedContent = ''
            let hasStartedStreaming = false
            let lastTokenTime = Date.now()
            
            // Ask browser to set a timer that checks time since last token, and set timeout flag if it's been 2 minutes
            timeoutId = setInterval(() => {
                if (Date.now() - lastTokenTime > 2 * 60 * 1000) {
                    console.error('Stream timeout: no data for 2mins')
                    isTimedOut = true 
                    reader?.cancel() // ? allows reader to be null or undefined without throwing an error
                    clearInterval(timeoutId!)
                }
            }, 5000) // check every 5s

            while (!isTimedOut) {
                const { done, value } = await reader.read()
                if (done) break

                const chunk = decoder.decode(value)
                const lines = chunk.split('\n')

                for (const line of lines) {

                    // SSE format: lines start with "data: " prefix (6 chars), with backend sending "data: {json}\n\n"
                    // Example: "data: {\"type\":\"token\",\"content\":\"What\"}\n\n"
                    if (!line.startsWith('data: ')) continue
                    const data = JSON.parse(line.slice(6)) // Remove "data: " prefix to get JSON

                    if (data.type === 'token') {
                        const now = Date.now()

                        // Track timing metrics
                        if (firstTokenTime === null) {
                            firstTokenTime = now
                            console.log(`Time to first token: ${firstTokenTime - requestStartTime}ms`)
                        } else {
                            const interTokenTime = now - lastTokenTime
                            totalInterTokenTime += interTokenTime
                            tokenCount++
                        }

                        streamedContent += data.content
                        lastTokenTime = now

                        if (requestConversationId === currentConversationRef.current) {
                            // User watching - start/resume streaming state
                            if (!hasStartedStreaming) {
                                setStreaming(requestConversationId)
                                hasStartedStreaming = true

                                // Add empty assistant message if not already present (when resuming after switch)
                                setMessages(prev => {
                                    const lastMsg = prev[prev.length - 1]
                                    if (!lastMsg || lastMsg.role !== 'assistant') {
                                        return [...prev, { role: 'assistant', content: streamedContent }]
                                    }
                                    return prev
                                })
                            }

                            // Update last assistant message with streamed content
                            setMessages(prev => {
                                const updated = [...prev]
                                updated[updated.length - 1] = { role: 'assistant', content: streamedContent }
                                return updated
                            })

                        } else {
                            // User switched away - revert to loading, continue silently
                            if (hasStartedStreaming) {
                                setLoading(requestConversationId)
                                hasStartedStreaming = false
                            }
                            
                        }
                    }

                    if (data.type === 'complete') {
                        // Log streaming performance metrics
                        if (firstTokenTime && tokenCount > 0) {
                            const avgTimePerToken = totalInterTokenTime / tokenCount
                            const totalStreamTime = Date.now() - firstTokenTime
                            const tokensPerSecond = tokenCount / (totalStreamTime / 1000)

                            console.log(`Streaming complete:`)
                            console.log(`  Total tokens: ${tokenCount}`)
                            console.log(`  Avg time per token: ${avgTimePerToken.toFixed(1)}ms`)
                            console.log(`  Total stream time: ${totalStreamTime}ms`)
                            console.log(`  Tokens per second: ${tokensPerSecond.toFixed(1)}`)

                            // Send metrics to backend for logging
                            fetch(`${API_URL}/metrics/streaming`, {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({
                                    conversation_id: requestConversationId,
                                    time_to_first_token: firstTokenTime - requestStartTime,
                                    total_tokens: tokenCount,
                                    avg_time_per_token: avgTimePerToken,
                                    total_stream_time: totalStreamTime,
                                    tokens_per_second: tokensPerSecond
                                })
                            }).catch(err => console.error('Failed to log metrics:', err))
                        }

                        // Backend generation complete, stream will close after this
                        // Show updating citations if user is watching
                        if (requestConversationId === currentConversationRef.current && hasStartedStreaming) {
                            setUpdatingCitations(requestConversationId)
                        }

                        // Refetch conversation using existing resume conversation logic
                        resumeConversation(requestConversationId)

                        // update sidebar
                        fetchConversationSumm()
                    }

                    if (data.type === 'error') {
                        throw new Error(data.message || 'Stream error')
                    }
                }
            }
        } catch (error) {
            console.error('Streaming error:', error)
            setSendError(requestConversationId)

            // Rollback - remove the user message and empty assistant message
            removeLastMessageFromCache(requestConversationId) // empty assistant message
            removeLastMessageFromCache(requestConversationId) // user message 

            // Restore input for retry if user is still on the same conversation
            if (requestConversationId === currentConversationRef.current) {
                setInput(user_input)
            }
            
        } finally {
            // Handle timeout case 
            if (isTimedOut) {
                setSendError(requestConversationId)

                // Rollback - remove the user message and empty assistant message
                removeLastMessageFromCache(requestConversationId) // empty assistant message
                removeLastMessageFromCache(requestConversationId) // user message 

                // Restore input for retry if user is still on the same conversation
                if (requestConversationId === currentConversationRef.current) {
                    setInput(user_input)
                }
            }
            if (timeoutId) clearInterval(timeoutId)
            if (reader) reader.cancel()
        }

    }

    const fetchResponse = (requestConversationId: string, user_input: string) => {
        fetch(`${API_URL}/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_message: user_input,
                user_id: userId,
                use_local: true,
                conversation_id: requestConversationId,
                use_reranker: true,
                additional_chunks_per_doc: 20
            }), 
            signal: AbortSignal.timeout(6 * 60 * 1000) // 6 minute timeout
        })
        .then(chatResponse => {
            if (!chatResponse.ok) {
                throw new Error(`Failed to process message: ${chatResponse.status}`)
            }
            // Received response, remove conversation from loading set
            clearLoading(requestConversationId)

            // Refetch full conversation for updating cache
            return fetch(`${API_URL}/conversations/${requestConversationId}?user_id=${userId}`, {
                signal: AbortSignal.timeout(2 * 60 * 1000) // 2 minute timeout
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

    const processMessage = (useStreamingOverride?: boolean) => {
        // Don't send message if empty input or current loading conversation 
        if (input.trim() === '' || isLoading(currConversationId)) return 

        // Determine streaming mode (parameter overrides hook default)
        const shouldStream = useStreamingOverride ?? useStreaming

        // Check if this is the first message
        const isFirstMessage = messages.length === 0 && window.innerWidth < 768

        // Save user input and clear input 
        const user_input = input 
        setInput('')

        // Add user message to messages array, and also empty assistant message if streaming
        const userMessage = {
            role: 'user',
            content: user_input 
        }
        if (!shouldStream) {
             setMessages([...messages, userMessage])
        } else {
            const emptyAssistantMessage = {
                role: 'assistant',
                content: ''
            }
            setMessages([...messages, userMessage, emptyAssistantMessage])
        }
       
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

        if (shouldStream) {
            streamResponse(requestConversationId, user_input) 
        } else {
            fetchResponse(requestConversationId, user_input)
        }
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
        fetch(`${API_URL}/conversations/${conversationId}?user_id=${userId}`, {
            signal: AbortSignal.timeout(2 * 60 * 1000) // 2 minute timeout
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
            // Clear loading/updating states
            clearLoading(conversationId)
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
        isLoading, isStreaming, hasSendError, hasResumeError, isUpdatingCitations,
        // Actions
        processMessage, resumeConversation, returnHome

    }
}