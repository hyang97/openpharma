import { Citation } from '@/types/message'

type CitationListProps = {
  citations: Citation[]
}

export function CitationList({ citations }: CitationListProps) {
  if (!citations || citations.length === 0) {
    return null
  }

  return (
    <div className="mt-4 pt-4 border-t border-slate-600">
      <div className="text-xs font-semibold text-slate-300 mb-3 uppercase tracking-wide">Sources:</div>
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
    </div>
  )
}
