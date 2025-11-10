/*
  States:
  1. 'loading' - "● ● ● Thinking..." (before first token OR user switched away)
  2. 'streaming' - Tokens actively appearing (user watching)
  3. 'updating_citations' - "● ● ● Updating citations..." (stream done, refetching)
  4. 'send_error' - Message send failed
  5. 'resume_error' - Conversation load failed
*/

import { useState } from 'react'

type LoadingStatus = 'loading' | 'streaming' | 'updating_citations' | 'send_error' | 'resume_error'

export function useLoadingState() {
    const [loadingConversations, setLoadingConversations] = useState<Map<string, LoadingStatus>>(new Map()) 

    const setLoading = (conversationId: string) => {
        setLoadingConversations(prev => new Map(prev).set(conversationId, 'loading'))
    }

    const setStreaming = (conversationId: string) => {
        setLoadingConversations(prev => new Map(prev).set(conversationId, 'streaming'))
    }

    const setUpdatingCitations = (conversationId: string) => {
        setLoadingConversations(prev => new Map(prev).set(conversationId, 'updating_citations'))
    }

    const setSendError = (conversationId: string) => {
        setLoadingConversations(prev => new Map(prev).set(conversationId, 'send_error'))
    }

    const setResumeError = (conversationId: string) => {
        setLoadingConversations(prev => new Map(prev).set(conversationId, 'resume_error'))
    }

    const clearLoading = (conversationId: string) => {
        setLoadingConversations(prev => {
            const next = new Map(prev)
            next.delete(conversationId)
            return next
        })
    }

    const isLoading = (conversationId: string | null) => {
        return Boolean(conversationId && loadingConversations.get(conversationId) === 'loading')
    }

    const isStreaming = (conversationId: string | null) => {
        return Boolean(conversationId && loadingConversations.get(conversationId) === 'streaming')
    }

    const isUpdatingCitations = (conversationId: string | null) => {
        return Boolean(conversationId && loadingConversations.get(conversationId) === 'updating_citations')
    }

    const hasSendError = (conversationId: string | null) => {
        return Boolean(conversationId && loadingConversations.get(conversationId) === 'send_error')
    }

    const hasResumeError = (conversationId: string | null) => {
        return Boolean(conversationId && loadingConversations.get(conversationId) === 'resume_error')
    }

    return {
        loadingConversations, clearLoading,
        setLoading, setStreaming, setUpdatingCitations, setSendError, setResumeError,
        isLoading, isStreaming, isUpdatingCitations, hasSendError, hasResumeError
    }
}