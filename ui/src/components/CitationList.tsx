'use client'

import { useState } from 'react'
import { Citation } from '@/types/message'

type CitationListProps = {
  citations: Citation[]
}

export function CitationList({ citations }: CitationListProps) {
  const [showCitations, setShowCitations] = useState(false)

  if (!citations || citations.length === 0) {
    return null
  }

  return (
    <div className="mt-4 pt-4 border-t border-slate-600">
      <button
        onClick={() => setShowCitations(!showCitations)}
        className="text-sm text-blue-400 hover:text-blue-300 flex items-center gap-1 mb-3"
      >
        <span>{showCitations ? '▲' : '▼'}</span>
        <span className="uppercase tracking-wide">{showCitations ? 'Hide' : 'Show'} all sources ({citations.length})</span>
      </button>

      {showCitations && (
        <div className="space-y-2">
          {citations.map((citation) => (
            <div key={citation.number} className="text-xs text-slate-300 bg-slate-700/50 rounded-lg p-3 border border-slate-600">
              <span className="font-semibold text-blue-400">[{citation.number}]</span>{' '}
              <span className="italic">{citation.title}</span>
              <div className="text-slate-400 mt-1">
                {citation.journal} • PMC{citation.source_id}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
