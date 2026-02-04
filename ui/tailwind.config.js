/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Geist', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['Geist Mono', 'ui-monospace', 'SFMono-Regular', 'monospace'],
      },
      colors: {
        // Linq Brand Colors
        linq: {
          black: '#141414',
          cream: '#FCF9E9',
          sage: '#B0BFB7',
          blue: '#4F9FDF',
          navy: '#1B3D67',
          green: '#83B149',
          lime: '#E8DF6E',
        },
        // Status Colors for health indicators
        status: {
          healthy: '#83B149',
          warning: '#CA8A04',
          error: '#DC2626',
          critical: '#991B1B',
          muted: '#6B7280',
        },
      },
    },
  },
  plugins: [],
};
