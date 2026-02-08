'use client'

import { useState } from 'react'

type SuggestedQuestionsProps = {
  onSelectQuestion: (question: string) => void
}

const SUGGESTED_QUESTIONS = [
  {
    category: "Competitive Intelligence",
    questions: [
      "What are the latest findings on statin therapy for primary and secondary prevention of cardiovascular disease?",
      "What mechanisms of resistance to immune checkpoint inhibitors have been identified in cancer research?",
    ]
  },
  {
    category: "R&D Strategy",
    questions: [
      "What neuroprotective mechanisms have been proposed for metformin in recent studies?",
      "What are the emerging approaches to combat antimicrobial resistance?",
    ]
  },
  {
    category: "Clinical Development",
    questions: [
      "How has CRISPR gene editing technology been applied in therapeutic development?",
      "What biomarkers are being used to predict response to cancer immunotherapy?",
    ]
  }
]

export function SuggestedQuestions({ onSelectQuestion }: SuggestedQuestionsProps) {
  const [isExpanded, setIsExpanded] = useState(false)

  return (
    <div className="text-center">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="text-sm text-slate-400 hover:text-slate-300 transition-colors py-2"
      >
        Explore example questions{' '}
        <span
          className="inline-block text-xs transition-transform duration-300"
          style={{ transform: isExpanded ? 'rotate(180deg)' : 'rotate(0deg)' }}
        >
          &#9660;
        </span>
      </button>

      <div
        className="text-left overflow-hidden transition-all duration-300 ease-out"
        style={{
          maxHeight: isExpanded ? '600px' : '0px',
          opacity: isExpanded ? 1 : 0,
        }}
      >
        {SUGGESTED_QUESTIONS.map((section) => (
          <div key={section.category} className="mb-4">
            <div className="text-xs font-semibold uppercase tracking-wide text-slate-400 mb-2 px-1">
              {section.category}
            </div>
            {section.questions.map((question) => (
              <button
                key={question}
                onClick={() => onSelectQuestion(question)}
                className="w-full text-left bg-slate-800 border border-slate-700 rounded-lg px-4 py-3 mb-2
                           text-sm text-slate-300 hover:border-accent hover:bg-slate-800/80
                           transition-colors cursor-pointer relative pr-10"
              >
                {question}
                <span className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 text-sm">
                  &#8599;
                </span>
              </button>
            ))}
          </div>
        ))}
      </div>
    </div>
  )
}
