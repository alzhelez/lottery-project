'use client'

import { Component, type ReactNode } from 'react'
import { AlertTriangle, RefreshCw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'

interface ErrorBoundaryProps {
  children: ReactNode
  fallback?: ReactNode
}

interface ErrorBoundaryState {
  hasError: boolean
  error: Error | null
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('[ErrorBoundary] Uncaught error:', error, errorInfo)
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null })
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback

      return (
        <div className="flex items-center justify-center min-h-[50vh] p-4">
          <Card className="border-red-500/30 bg-red-500/5 max-w-md w-full">
            <CardContent className="py-8 flex flex-col items-center gap-4 text-center">
              <div className="h-14 w-14 rounded-full bg-red-500/20 flex items-center justify-center">
                <AlertTriangle className="h-7 w-7 text-red-400" />
              </div>
              <h3 className="text-base font-bold text-red-300">Что-то пошло не так</h3>
              <p className="text-sm text-slate-400">
                Произошла непредвиденная ошибка. Попробуйте обновить страницу.
              </p>
              {this.state.error && (
                <pre className="text-xs text-slate-500 bg-black/20 rounded-lg p-3 max-w-full overflow-x-auto whitespace-pre-wrap">
                  {this.state.error.message}
                </pre>
              )}
              <Button
                onClick={this.handleReset}
                variant="outline"
                className="border-red-500/30 text-red-400 hover:bg-red-500/10"
              >
                <RefreshCw className="h-4 w-4 mr-2" />
                Попробовать снова
              </Button>
            </CardContent>
          </Card>
        </div>
      )
    }

    return this.props.children
  }
}
