/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./index.html",
    "./src/**/*.{html,js}",
    "./dist/**/*.{html,js}"
  ],
  darkMode: 'class', // Light mode strictly enforced; class never applied
  theme: {
    extend: {
      colors: {
        canvas: {
          primary: '#F5F7FA',
          secondary: '#FFFFFF',
          surface: '#F0F3F7',
          elevated: '#FFFFFF'
        },
        ink: {
          primary: '#202631',
          secondary: '#667085',
          muted: '#8993A4',
          subtle: '#A0AEC0'
        },
        brand: {
          DEFAULT: '#4F83CC',
          hover: '#3E6FB3',
          light: '#E8F0FC',
          subtle: 'rgba(79, 131, 204, 0.08)'
        },
        line: {
          DEFAULT: '#E3E8EF',
          soft: '#EDF1F7',
          active: '#CBD5E1'
        },
        state: {
          success: '#2E7D32',
          'success-bg': '#E8F5E9',
          'success-border': '#C8E6C9',
          warning: '#B45309',
          'warning-bg': '#FEF3C7',
          'warning-border': '#FDE68A',
          danger: '#C62828',
          'danger-bg': '#FFEBEE',
          'danger-border': '#FFCDD2',
          info: '#4F83CC',
          'info-bg': '#E8F0FC'
        }
      },
      fontFamily: {
        sans: [
          '-apple-system',
          'BlinkMacSystemFont',
          '"SF Pro Display"',
          '"SF Pro Text"',
          '"Segoe UI"',
          'Roboto',
          '"Helvetica Neue"',
          'Arial',
          'sans-serif'
        ],
        mono: [
          'ui-monospace',
          '"SF Mono"',
          'Menlo',
          'Consolas',
          '"Liberation Mono"',
          'monospace'
        ]
      },
      boxShadow: {
        glass: '0 4px 24px -1px rgba(16, 24, 40, 0.06), 0 2px 6px -1px rgba(16, 24, 40, 0.03)',
        card: '0 1px 3px 0 rgba(16, 24, 40, 0.04), 0 1px 2px -1px rgba(16, 24, 40, 0.02)',
        'card-hover': '0 8px 30px -4px rgba(16, 24, 40, 0.08), 0 4px 10px -2px rgba(16, 24, 40, 0.03)',
        modal: '0 20px 40px -8px rgba(16, 24, 40, 0.16)'
      },
      letterSpacing: {
        tighter: '-0.03em',
        tight: '-0.015em',
        normal: '0',
        wide: '0.04em',
        widest: '0.08em'
      },
      borderRadius: {
        apple: '12px',
        'apple-sm': '8px',
        'apple-lg': '16px',
        'apple-xl': '20px'
      }
    }
  },
  plugins: []
};
