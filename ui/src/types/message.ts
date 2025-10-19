export type Message = {
  role: string
  content: string
  citations?: Citation[]
}

export type Citation = {
  number: number
  title: string
  journal: string
  source_id: string
}
