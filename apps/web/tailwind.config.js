/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./src/**/*.{js,ts,jsx,tsx,mdx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // SkillIssue heat palette — tier colors
        'heat-raw': '#2B6CC4',
        'heat-toasted': '#3D8B40',
        'heat-medium': '#C9922B',
        'heat-cooked': '#CF3626',
        'heat-burnt': '#4A2A22',
        // Surface tokens
        surface: {
          DEFAULT: '#ffffff',
          dark: '#0f1117',
          raised: '#1a1d27',
          'raised-dark': '#1e2230',
          border: '#e5e7eb',
          'border-dark': '#2d3142',
        },
      },
      fontFamily: {
        sans: ['var(--font-geist-sans)', 'system-ui', 'sans-serif'],
        mono: ['var(--font-geist-mono)', 'monospace'],
      },
    },
  },
  plugins: [],
}
