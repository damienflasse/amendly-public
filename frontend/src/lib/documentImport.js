const API_BASE = '/api/organisations'
export const MAX_DOCUMENT_IMPORT_BYTES = 10 * 1024 * 1024
// Abort file uploads that take more than 60 seconds to prevent silent hangs.
const UPLOAD_TIMEOUT_MS = 60_000

/**
 * Validate a client-side document import file before upload.
 *
 * Parameters:
 *   file — Browser File object.
 *   kind — Supported import type: 'pdf' | 'docx'.
 *   t    — Optional translation function.
 *
 * Returns:
 *   Localized error string, or null when the file is valid.
 */
export function validateDocumentImportFile(file, kind, t = null) {
  if (file.size > MAX_DOCUMENT_IMPORT_BYTES) {
    return t?.('document.import_error_too_large') ?? 'Fichier trop volumineux (max 10 Mo).'
  }

  if (kind === 'pdf') {
    const validType = file.type === 'application/pdf' || file.name.endsWith('.pdf')
    if (!validType) {
      return (
        t?.('document.import_error_format_pdf') ??
        'Format non supporte. Veuillez selectionner un fichier PDF.'
      )
    }
  }

  if (kind === 'docx') {
    const validType =
      file.type === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' ||
      file.name.endsWith('.docx')
    if (!validType) {
      return (
        t?.('document.import_error_format_docx') ??
        'Format non supporte. Veuillez selectionner un fichier .docx.'
      )
    }
  }

  return null
}

/**
 * Resolve the document title suggested by an import result.
 *
 * Parameters:
 *   fileName       — Original uploaded file name.
 *   extractedTitle — Optional title extracted from the document.
 *
 * Returns:
 *   Imported title when available, otherwise the file name without extension.
 */
export function resolveImportedDocumentTitle(fileName, extractedTitle) {
  return extractedTitle || fileName.replace(/\.[^/.]+$/, '')
}

/**
 * Upload a file for extraction using XMLHttpRequest so that upload progress
 * events are available.
 *
 * Parameters:
 *   slug       — Organisation slug.
 *   path       — API path segment (e.g. 'extract-docx').
 *   file       — File object to upload.
 *   onProgress — Optional callback(percent: number) called during upload (0–100).
 *
 * Returns:
 *   Promise resolving to the parsed JSON response body.
 *
 * Raises:
 *   Error on network failure, timeout, or non-2xx HTTP response.
 */
function uploadDocumentForExtraction(slug, path, file, { onProgress } = {}) {
  return new Promise((resolve, reject) => {
    const formData = new FormData()
    formData.append('file', file)

    const xhr = new XMLHttpRequest()
    const url = `${API_BASE}/${slug}/documents/${path}`

    // Timeout watchdog — abort if the entire request exceeds the limit.
    const timeoutId = setTimeout(() => {
      xhr.abort()
      reject(new Error('Upload timed out. Please try again with a smaller file.'))
    }, UPLOAD_TIMEOUT_MS)

    // Upload progress
    if (onProgress) {
      xhr.upload.addEventListener('progress', (e) => {
        if (e.lengthComputable) {
          onProgress(Math.round((e.loaded / e.total) * 100))
        }
      })
      // Signal upload complete (backend processing begins)
      xhr.upload.addEventListener('load', () => {
        onProgress(100)
      })
    }

    xhr.addEventListener('load', () => {
      clearTimeout(timeoutId)
      let data = {}
      try {
        data = JSON.parse(xhr.responseText)
      } catch {
        // ignore parse errors — fall through to error check
      }
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(data)
      } else {
        reject(new Error(data?.detail ?? `Request failed with status ${xhr.status}`))
      }
    })

    xhr.addEventListener('error', () => {
      clearTimeout(timeoutId)
      reject(new Error('Network error during upload. Please check your connection.'))
    })

    xhr.addEventListener('abort', () => {
      clearTimeout(timeoutId)
      // Timeout case is already handled above; this covers manual aborts.
      reject(new Error('Upload was cancelled.'))
    })

    xhr.open('POST', url)
    xhr.withCredentials = true

    xhr.send(formData)
  })
}

/**
 * Upload a DOCX file and return extracted HTML.
 *
 * @param {string} slug
 * @param {File} file
 * @param {{ onProgress?: (percent: number) => void }} [options]
 * @returns {Promise<{ html: string; char_count: number; warnings: string[] }>}
 */
export function extractDocxFile(slug, file, options = {}) {
  return uploadDocumentForExtraction(slug, 'extract-docx', file, options)
}

/**
 * Upload a PDF file and return extracted HTML.
 *
 * @param {string} slug
 * @param {File} file
 * @param {{ onProgress?: (percent: number) => void }} [options]
 * @returns {Promise<{ html: string; title?: string | null; char_count: number; warnings: string[] }>}
 */
export function extractPdfFile(slug, file, options = {}) {
  return uploadDocumentForExtraction(slug, 'extract-pdf', file, options)
}
