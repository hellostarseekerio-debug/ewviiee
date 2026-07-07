/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        obsidian: '#05060a',
        ink: '#0a0c12',
        gold: {
          DEFAULT: '#c9a96a',
          bright: '#e8cf9a',
          dim: '#8a6f3e',
        },
        platinum: '#c8ccd4',
        mist: '#8b93a3',
      },
      fontFamily: {
        display: ['"Cormorant Garamond"', '"Noto Serif TC"', 'serif'],
        body: ['Inter', '"Noto Serif TC"', 'sans-serif'],
        tc: ['"Noto Serif TC"', 'serif'],
      },
      letterSpacing: {
        widest2: '0.35em',
      },
      animation: {
        'slow-spin': 'spin 14s linear infinite',
        shimmer: 'shimmer 3.2s ease-in-out infinite',
      },
      keyframes: {
        shimmer: {
          '0%, 100%': { opacity: '0.55' },
          '50%': { opacity: '1' },
        },
      },
    },
  },
  plugins: [
    function ({ addUtilities }) {
      addUtilities({
        /* Glassmorphism — frosted obsidian panels */
        '.glass': {
          background: 'linear-gradient(135deg, rgba(255,255,255,0.055), rgba(255,255,255,0.015))',
          backdropFilter: 'blur(18px) saturate(140%)',
          '-webkit-backdrop-filter': 'blur(18px) saturate(140%)',
          border: '1px solid rgba(201,169,106,0.16)',
          boxShadow: '0 24px 60px -24px rgba(0,0,0,0.8), inset 0 1px 0 rgba(255,255,255,0.06)',
        },
        '.glass-strong': {
          background: 'linear-gradient(150deg, rgba(20,22,30,0.82), rgba(8,9,14,0.9))',
          backdropFilter: 'blur(26px) saturate(160%)',
          '-webkit-backdrop-filter': 'blur(26px) saturate(160%)',
          border: '1px solid rgba(201,169,106,0.22)',
          boxShadow: '0 40px 90px -30px rgba(0,0,0,0.9), inset 0 1px 0 rgba(255,255,255,0.08)',
        },
        /* Neomorphism — soft-extruded dark surfaces */
        '.neo': {
          background: 'linear-gradient(145deg, #0c0e15, #070810)',
          boxShadow: '9px 9px 22px rgba(0,0,0,0.65), -6px -6px 18px rgba(38,42,56,0.35)',
          border: '1px solid rgba(255,255,255,0.04)',
        },
        '.neo-inset': {
          background: 'linear-gradient(145deg, #070810, #0c0e15)',
          boxShadow: 'inset 6px 6px 14px rgba(0,0,0,0.7), inset -4px -4px 12px rgba(44,48,64,0.28)',
          border: '1px solid rgba(255,255,255,0.03)',
        },
        '.text-gold-gradient': {
          background: 'linear-gradient(100deg, #8a6f3e 0%, #c9a96a 35%, #f0dcae 52%, #c9a96a 70%, #8a6f3e 100%)',
          '-webkit-background-clip': 'text',
          backgroundClip: 'text',
          color: 'transparent',
        },
        '.hairline-gold': {
          borderColor: 'rgba(201,169,106,0.28)',
        },
      })
    },
  ],
}
