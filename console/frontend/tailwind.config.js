/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        mono: ['"IBM Plex Mono"', 'ui-monospace', 'monospace'],
        sans: ['"IBM Plex Sans"', 'system-ui', 'sans-serif'],
      },
      colors: {
        // Design tokens — dark theme
        bg: {
          base:    '#0d0d0f',
          surface: '#16161a',
          card:    '#1c1c22',
          hover:   '#222228',
          border:  '#2a2a32',
        },
        text: {
          primary:   '#e8e8f0',
          secondary: '#9090a8',
          muted:     '#5a5a70',
          accent:    '#7c6af7',
        },
        accent: {
          purple: '#7c6af7',
          blue:   '#4a9eff',
          green:  '#34d399',
          yellow: '#fbbf24',
          red:    '#f87171',
          cyan:   '#22d3ee',
        },
        status: {
          draft:          { bg: '#1e1e2e', text: '#9090a8', border: '#2a2a42' },
          pending_review: { bg: '#1e1a00', text: '#fbbf24', border: '#3a3000' },
          approved:       { bg: '#001e12', text: '#34d399', border: '#003020' },
          rejected:       { bg: '#1e0a0a', text: '#f87171', border: '#3a1010' },
          editing:        { bg: '#001624', text: '#4a9eff', border: '#002840' },
          producing:      { bg: '#1a0e2e', text: '#7c6af7', border: '#2a1a50' },
          completed:      { bg: '#0a1e14', text: '#34d399', border: '#103020' },
        },
      },
    },
  },
  plugins: [],
}
