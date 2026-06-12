'use client'

import { type ReactNode } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { LucideIcon } from 'lucide-react'

interface SectionCardProps {
  icon?: LucideIcon
  iconColor?: string
  title: string
  titleBadge?: ReactNode
  children: ReactNode
  className?: string
  gradient?: boolean
}

/**
 * Reusable section card used across Step3Predict and Step4Pipeline.
 * Eliminates repetition of Card > CardHeader(icon + title) > CardContent pattern.
 */
export function SectionCard({
  icon: Icon,
  iconColor = 'text-blue-400',
  title,
  titleBadge,
  children,
  className = '',
  gradient = false,
}: SectionCardProps) {
  return (
    <Card className={`border-white/10 bg-white/5 backdrop-blur-sm ${className}`}>
      <CardHeader className="pb-2">
        <CardTitle className="text-xs flex items-center gap-2">
          {Icon && <Icon className={`h-3.5 w-3.5 ${iconColor}`} />}
          {title}
          {titleBadge}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {children}
      </CardContent>
    </Card>
  )
}
