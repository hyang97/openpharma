import { Message } from '@/types/message'

type MessageBubbleProps = {
  message: Message
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === 'user'

  // Parse inline citations and make them clickable
  const renderContentWithCitations = (content: string) => {
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
          className="text-blue-400 hover:text-blue-300 hover:underline font-semibold cursor-pointer transition-colors"
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
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} animate-fade-in`}>
      <div className={`max-w-3xl rounded-xl px-5 py-4 ${
        isUser
          ? 'bg-slate-700 text-white'
          : 'bg-slate-800 border border-slate-700'
      }`}>
        <div className={`text-xs font-semibold mb-2 uppercase tracking-wide ${isUser ? 'text-slate-300' : 'text-slate-400'}`}>
          {isUser ? 'You' : 'OpenPharma'}
        </div>
        <div className={`text-base leading-relaxed whitespace-pre-wrap ${isUser ? 'text-white' : 'text-slate-100'}`}>
          {isUser ? message.content : renderContentWithCitations(message.content)}
        </div>
      </div>
    </div>
  )
}
