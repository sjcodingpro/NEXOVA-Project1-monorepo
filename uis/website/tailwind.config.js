/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./*.html'],
  theme: {
    extend: {
      colors: {
        ink: { DEFAULT: '#1E241D', 2: '#262D24', 700: '#333B2E', 500: '#6E7565' },
        paper: { DEFAULT: '#EAE6DA', 2: '#DFDBC9' },
        olive: { DEFAULT: '#7C8A3C', dark: '#5E6A2C', 50: '#EEF0DE' },
        aegean: { DEFAULT: '#2C4C5C', dark: '#1F3945', 50: '#E3EAEC' },
        error: { DEFAULT: '#B3261E', 50: '#FBEAE9' },
        success: { DEFAULT: '#1F6F41', 50: '#E9F4EC' },
      },
      fontFamily: {
        display: ['"Fraunces"', 'ui-serif', 'serif'],
        body: ['"Inter"', 'ui-sans-serif', 'sans-serif'],
        mono: ['"IBM Plex Mono"', 'ui-monospace', 'monospace'],
      },
      keyframes: {
        'tile-in': {
          '0%': { opacity: '0', transform: 'translateY(8px) scale(0.94)' },
          '100%': { opacity: '1', transform: 'translateY(0) scale(1)' },
        },
      },
      animation: {
        'tile-in': 'tile-in 0.6s cubic-bezier(0.16,1,0.3,1) both',
      },
    },
  },
  plugins: [],
};