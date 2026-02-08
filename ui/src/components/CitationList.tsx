'use client'

import { useState, useEffect } from 'react'
import { Citation } from '@/types/message'

type CitationListProps = {
  citations: Citation[]
}

export function CitationList({ citations }: CitationListProps) {
  const [showCitations, setShowCitations] = useState(false)

  // Listen for citation click events to auto-expand citations
  useEffect(() => {
    const handleCitationClick = () => {
      setShowCitations(true)
    }

    // Listen for clicks on citation links in messages
    document.addEventListener('citation-clicked', handleCitationClick as EventListener)

    return () => {
      document.removeEventListener('citation-clicked', handleCitationClick as EventListener)
    }
  }, [])

  // Auto-scroll when citations expand
  useEffect(() => {
    if (showCitations) {
      setTimeout(() => {
        const citationSection = document.getElementById('citation-section')
        if (citationSection) {
          citationSection.scrollIntoView({ behavior: 'smooth', block: 'start' })
        }
      }, 100)
    }
  }, [showCitations])

  if (!citations || citations.length === 0) {
    return null
  }

  return (
    <div id="citation-section" className="mt-4 pt-4 border-t border-slate-600 scroll-mt-20">
      <button
        onClick={() => setShowCitations(!showCitations)}
        className="text-sm text-accent-text hover:opacity-80 flex items-center gap-1 mb-3"
      >
        <span>{showCitations ? '▲' : '▼'}</span>
        <span className="uppercase tracking-wide">{showCitations ? 'Hide' : 'Show'} all sources ({citations.length})</span>
      </button>

      <div
        className={`transition-all duration-300 ease-in-out ${
          showCitations ? 'max-h-[2000px] opacity-100' : 'max-h-0 opacity-0'
        }`}
        style={{ overflow: showCitations ? 'visible' : 'hidden' }}
      >
        <div className="space-y-2">
          {citations.map((citation) => (
            <div
              key={citation.number}
              id={`citation-${citation.number}`}
              className="text-xs text-slate-300 bg-slate-700/50 rounded-lg p-3 border border-slate-600 transition-all duration-300 scroll-mt-4"
            >
              <span className="font-semibold text-accent-text">[{citation.number}]</span>{' '}
              <span className="italic">{citation.title}</span>
              <div className="text-slate-400 mt-1">
                {citation.journal} •{' '}
                <a
                  href={`https://www.ncbi.nlm.nih.gov/pmc/articles/PMC${citation.source_id}/`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-accent-text hover:opacity-80 underline"
                >
                  PMC{citation.source_id}
                </a>
              </div>
            </div>
          ))}
        </div>

      </div>
    </div>
  )
}
