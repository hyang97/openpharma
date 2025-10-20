export type Message = {
  role: string
  content: string
}

export type Citation = {
  number: number
  title: string
  journal: string
  source_id: string
}

export type ConversationSummary = {
  conversation_id: string
  first_message: string
  message_count: number
  last_updated: string
}
