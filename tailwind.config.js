/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: 'class',
  content: [
    './web/templates/**/*.html',
  ],
  theme: {
    extend: {
      colors: {
        background: 'rgb(var(--color-background-rgb) / <alpha-value>)',
        'surface': 'rgb(var(--color-surface-rgb) / <alpha-value>)',
        'surface-dim': 'rgb(var(--color-surface-dim-rgb) / <alpha-value>)',
        'surface-bright': 'rgb(var(--color-surface-bright-rgb) / <alpha-value>)',
        'surface-container-lowest': 'rgb(var(--color-surface-container-lowest-rgb) / <alpha-value>)',
        'surface-container-low': 'rgb(var(--color-surface-container-low-rgb) / <alpha-value>)',
        'surface-container': 'rgb(var(--color-surface-container-rgb) / <alpha-value>)',
        'surface-container-high': 'rgb(var(--color-surface-container-high-rgb) / <alpha-value>)',
        'surface-container-highest': 'rgb(var(--color-surface-container-highest-rgb) / <alpha-value>)',
        'surface-variant': 'rgb(var(--color-surface-variant-rgb) / <alpha-value>)',
        'on-surface': 'rgb(var(--color-on-surface-rgb) / <alpha-value>)',
        'on-surface-variant': 'rgb(var(--color-on-surface-variant-rgb) / <alpha-value>)',
        'primary': 'rgb(var(--color-primary-rgb) / <alpha-value>)',
        'on-primary': 'rgb(var(--color-on-primary-rgb) / <alpha-value>)',
        'primary-container': 'rgb(var(--color-primary-container-rgb) / <alpha-value>)',
        'on-primary-container': 'rgb(var(--color-on-primary-container-rgb) / <alpha-value>)',
        'secondary': 'rgb(var(--color-secondary-rgb) / <alpha-value>)',
        'secondary-container': 'rgb(var(--color-secondary-container-rgb) / <alpha-value>)',
        'tertiary': 'rgb(var(--color-tertiary-rgb) / <alpha-value>)',
        'tertiary-container': 'rgb(var(--color-tertiary-container-rgb) / <alpha-value>)',
        'error': 'rgb(var(--color-error-rgb) / <alpha-value>)',
        'error-container': 'rgb(var(--color-error-container-rgb) / <alpha-value>)',
        'outline': 'rgb(var(--color-outline-rgb) / <alpha-value>)',
        'outline-variant': 'rgb(var(--color-outline-variant-rgb) / <alpha-value>)',
        'surface-glass': 'var(--color-surface-glass)',
        'border-glass': 'var(--color-border-glass)',
        'pure-white': '#FFFFFF',
        'off-white': '#F4F4F4'
      },
      borderRadius: {
        DEFAULT: '0.75rem',
        'lg': '1rem',
        'xl': '1.25rem',
        'full': '9999px'
      },
      spacing: {
        'margin-mobile': '20px',
        'margin-desktop': '64px',
        'gutter': '24px',
        'unit': '8px',
        'container-max': '1440px'
      },
      fontFamily: {
        'display-hero': ['"Plus Jakarta Sans"', 'sans-serif'],
        'headline-lg': ['"Plus Jakarta Sans"', 'sans-serif'],
        'headline-md': ['"Plus Jakarta Sans"', 'sans-serif'],
        'label-bold': ['"Plus Jakarta Sans"', 'sans-serif'],
        'stat-giant': ['"Plus Jakarta Sans"', 'sans-serif'],
        'body-md': ['"Plus Jakarta Sans"', 'sans-serif'],
        'body-lg': ['"Plus Jakarta Sans"', 'sans-serif']
      },
      fontSize: {
        'display-hero': ['80px', { lineHeight: '88px', letterSpacing: '-0.04em', fontWeight: '800' }],
        'headline-lg': ['48px', { lineHeight: '56px', letterSpacing: '-0.02em', fontWeight: '800' }],
        'headline-lg-mobile': ['28px', { lineHeight: '34px', letterSpacing: '-0.02em', fontWeight: '800' }],
        'headline-md': ['32px', { lineHeight: '40px', letterSpacing: '-0.02em', fontWeight: '800' }],
        'label-bold': ['14px', { lineHeight: '20px', letterSpacing: '0.05em', fontWeight: '700' }],
        'stat-giant': ['64px', { lineHeight: '64px', fontWeight: '800' }],
        'body-md': ['16px', { lineHeight: '24px', fontWeight: '400' }],
        'body-lg': ['18px', { lineHeight: '28px', fontWeight: '500' }]
      }
    }
  },
  plugins: [
    require('@tailwindcss/forms'),
    require('@tailwindcss/container-queries')
  ]
}