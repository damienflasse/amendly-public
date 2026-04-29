export function getErrorMessage(error) {
  if (!error) return ''
  if (typeof error === 'string') return error
  return error.detail ?? error.message ?? ''
}

export function isDocumentLimitError(error) {
  const message = getErrorMessage(error).toLowerCase()
  return (
    message.includes('upgrade your plan') ||
    (message.includes('active document') && message.includes('limited to'))
  )
}

export function isSeatBillingError(error) {
  const message = getErrorMessage(error).toLowerCase()
  return (
    error?.status === 402 ||
    message.includes('active paid subscription') ||
    message.includes('resolve billing first') ||
    message.includes('update billing before adding members') ||
    message.includes('adding paid seats') ||
    message.includes('seat count for this organisation') ||
    message.includes('billable item for the') ||
    message.includes('no active paid subscription')
  )
}
