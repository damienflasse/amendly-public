import React from 'react'

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  componentDidCatch(error, errorInfo) {
    console.error('ErrorBoundary caught an error:', error, errorInfo)
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen flex items-center justify-center bg-surface-container-low p-4 font-body">
          <div className="bg-white p-8 rounded-xl shadow-lg max-w-lg w-full text-center space-y-4 border border-outline-variant">
            <h1 className="text-2xl font-display font-bold text-on-surface">Something went wrong</h1>
            <p className="text-on-surface-variant">
              An unexpected error prevented this page from loading.
            </p>
            {this.state.error && (
              <div className="bg-surface-container p-4 rounded text-left text-sm text-error font-mono overflow-auto max-h-40">
                {this.state.error.toString()}
              </div>
            )}
            <button
              onClick={() => window.location.replace('/')}
              className="mt-4 px-6 py-2.5 bg-amendly-blue text-on-primary rounded-lg font-semibold hover:opacity-90 transition-opacity"
            >
              Back to home
            </button>
          </div>
        </div>
      )
    }

    return this.props.children
  }
}
