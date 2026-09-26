import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'SkillIssue — How cooked is your code?',
  description: 'Scan any public GitHub repo for security, bugs, performance, and hygiene issues. Get a heat score in under a minute.',
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL ?? 'http://localhost:3000'),
  openGraph: {
    title: 'SkillIssue — How cooked is your code?',
    description: 'A code health scanner that rates your repo from Raw to Burnt to a Crisp.',
    type: 'website',
  },
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen antialiased font-sans">
        <div className="relative min-h-screen bg-white dark:bg-surface-dark text-gray-900 dark:text-gray-100">
          {children}
        </div>
      </body>
    </html>
  )
}
