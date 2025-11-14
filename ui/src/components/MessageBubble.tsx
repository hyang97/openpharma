import { Message } from '@/types/message'

type MessageBubbleProps = {
  message: Message
  isStreaming?: boolean
}

export function MessageBubble({ message, isStreaming = false }: MessageBubbleProps) {
  const isUser = message.role === 'user'

  // Parse inline citations and make them clickable
  const renderContentWithCitations = (content: string) => {

    // First, handle raw PMC citations (during streaming)
    const pmcPattern = /(\[PMC\d+\])/g
    const hasPmcCitations = pmcPattern.test(content)

    if (hasPmcCitations) {
      // During streaming: render PMC IDs with reduced opacity
      return content.split(pmcPattern).map((part, i) => {
        if (pmcPattern.test(part)) {
          return <span key={i} className="opacity-50 text-slate-400">{part}</span>
        }
        return part
      })
    }

    // After refetch: render numbered citations as clickable (existing logic)
    // Regex to match citation patterns: [1], [2, 3], [1,2], etc.
    const citationPattern = /\[(\d+(?:\s*,\s*\d+)*)\]/g
    const parts: (string | React.ReactNode)[] = []
    let lastIndex = 0
    let match

    while ((match = citationPattern.exec(content)) !== null) {
      // Add text before citation
      if (match.index > lastIndex) {
        parts.push(content.substring(lastIndex, match.index))
      }

      // Parse citation numbers (handles comma-separated like [1, 2, 3])
      const citationText = match[1]
      const citationNumbers = citationText.split(',').map(n => n.trim())

      // Add clickable citation link
      parts.push(
        <button
          key={match.index}
          onClick={() => {
            // Dispatch event to auto-expand citation list if collapsed
            document.dispatchEvent(new CustomEvent('citation-clicked'))

            // Scroll to citation in the citation list after a short delay (to allow expansion)
            const firstCitationNum = citationNumbers[0]
            setTimeout(() => {
              const citationElement = document.getElementById(`citation-${firstCitationNum}`)
              if (citationElement) {
                citationElement.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
                // Highlight effect with smooth shadow
                citationElement.style.boxShadow = '0 0 0 2px rgba(96, 165, 250, 0.8)'
                setTimeout(() => {
                  citationElement.style.boxShadow = ''
                }, 2000)
              }
            }, 350)
          }}
          className="text-accent-text hover:opacity-80 hover:underline font-semibold cursor-pointer transition-all"
        >
          [{match[1]}]
        </button>
      )

      lastIndex = match.index + match[0].length
    }

    // Add remaining text
    if (lastIndex < content.length) {
      parts.push(content.substring(lastIndex))
    }

    return parts.length > 0 ? parts : content
  }

  return (
    <div className="animate-fade-in">
      {isUser ? (
        // User message: bubble on the right with blue outline
        <div className="flex justify-end mb-6">
          <div className="max-w-3xl rounded-xl px-5 py-4 bg-accent/15 border-2 border-accent text-white">
            <div className="text-xs font-semibold mb-2 uppercase tracking-wide text-slate-300">
              You
            </div>
            <div className="text-base leading-relaxed whitespace-pre-wrap text-white">
              {message.content}
            </div>
          </div>
        </div>
      ) : (
        // Assistant message: no bubble, full width
        <div className="mb-6">
          <div className="text-xs font-semibold mb-3 uppercase tracking-wide text-slate-400">
            OpenPharma
          </div>
          <div className="text-base leading-relaxed whitespace-pre-wrap text-slate-100">
            {renderContentWithCitations(message.content)}
            {/* Blinking cursor during streaming */}
            {isStreaming && (
              <span className="inline-block w-2 h-5 bg-accent ml-1 animate-pulse" />
            )}
          </div>
        </div>
      )}
    </div>
  )
}
