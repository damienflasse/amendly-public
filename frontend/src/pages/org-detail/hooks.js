import { useMemo } from 'react'

export function useFilteredDocuments(documents, search, sortBy) {
  return useMemo(() => {
    const q = search.trim().toLowerCase()
    let result = q
      ? documents.filter((doc) => doc.title.toLowerCase().includes(q))
      : documents

    switch (sortBy) {
      case 'oldest':
        result = [...result].sort((a, b) => new Date(a.created_at) - new Date(b.created_at))
        break
      case 'title_az':
        result = [...result].sort((a, b) => a.title.localeCompare(b.title))
        break
      case 'title_za':
        result = [...result].sort((a, b) => b.title.localeCompare(a.title))
        break
      case 'status':
        result = [...result].sort((a, b) => a.status.localeCompare(b.status))
        break
      case 'newest':
      default:
        result = [...result].sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
    }

    return result
  }, [documents, search, sortBy])
}
