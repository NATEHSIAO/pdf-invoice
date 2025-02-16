declare module 'next-themes' {
  interface ThemeProviderProps {
    attribute?: string
    defaultTheme?: string
    enableSystem?: boolean
    disableTransitionOnChange?: boolean
    children: React.ReactNode
  }

  export function ThemeProvider(props: ThemeProviderProps): JSX.Element
  export function useTheme(): {
    theme: string
    setTheme: (theme: string) => void
    systemTheme: string
  }
} 