/** @type {import('tailwindcss').Config} */
// Colour tokens sourced from frontend/DESIGN.md — "The Editorial Ledger" design system
export default {
  content: [
    './index.html',
    './src/**/*.{js,jsx,ts,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        // Core palette — "The Editorial Ledger" tonal tokens
        // Note: primary (#515f74 Slate) removed — all actions now use amendly-blue (#2563eb)
        secondary: '#0053dc',
        'on-secondary': '#ffffff',
        surface: '#f7f9fb',
        'surface-container-low': '#f0f4f7',
        'surface-container-lowest': '#ffffff',
        'surface-container-high': '#e5edf2',
        'surface-container-highest': '#d9e4ea',
        'on-surface': '#2a3439',
        outline: '#717c82',
        // Variant 2 custom 
        'amendly-blue': '#2563eb',
        'amendly-dark': '#0f172a',
        'amendly-gray': '#94a3b8',
        'amendly-light': '#f8fafc',
        // Text-on-surface tokens
        'on-primary': '#ffffff',          // text on bg-amendly-blue buttons
        'on-surface-variant': '#64748b',  // muted / secondary body text (slate-500)
        // Tonal surface scale (MD3 — light mode only)
        // surface (#f7f9fb) → surface-container-low (#f0f4f7)
        //   → surface-container (#eaeff3) → surface-container-high (#e5edf2)
        //     → surface-container-highest (#d9e4ea)
        'surface-container': '#eaeff3',
        // Fixed / invariant aliases (same value in light-only product)
        'amendly-blue-fixed': '#2563eb',  // alias of amendly-blue for fixed-colour contexts
        // Diff tokens
        'secondary-container': '#dbe1ff',
        'on-secondary-fixed': '#003798',
        // Status badge tokens
        'tertiary-fixed': '#dcddfe',
        'on-tertiary-fixed': '#393c55',
        'primary-fixed': '#d5e3fd',
        'on-primary-fixed': '#324054',
        // Error / destructive state tokens
        'error': '#dc2626',               // red-600 — destructive actions, validation errors
        'on-error': '#ffffff',            // white text on bg-error buttons
        'error-container': '#fe8983',
        'on-error-container': '#752121',
        // Primary container (light blue tint — info / tip surfaces)
        'primary-container': '#dbeafe',   // blue-100 equivalent
        'on-primary-container': '#1e3a5f',// dark blue text on primary-container
        // Outline variant — subtle ring / divider, lighter than outline (#717c82)
        'outline-variant': '#c4cdd4',
      },
      fontFamily: {
        // Section 8 (Gemini Canvas / unified brand): Inter Black for headings & display
        display: ['Inter', 'sans-serif'],
        body: ['Inter', 'sans-serif'],
      },
      fontSize: {
        'display-md': ['2.75rem', { letterSpacing: '-0.02em', lineHeight: '1.1' }],
        'display-sm': ['2.0rem',  { letterSpacing: '-0.015em', lineHeight: '1.15' }],
        'headline-md': ['1.75rem', { letterSpacing: '-0.015em', lineHeight: '1.15' }],
        'headline-sm': ['1.5rem',  { letterSpacing: '-0.01em', lineHeight: '1.2' }],
        'title-md': ['1.125rem', { letterSpacing: '0', lineHeight: '1.35' }],
        'title-sm': ['1.0rem',   { letterSpacing: '0', lineHeight: '1.4' }],
        'body-md': ['0.875rem',  { letterSpacing: '0', lineHeight: '1.5' }],
        'body-sm': ['0.8125rem', { letterSpacing: '0', lineHeight: '1.4' }],
        'label-sm': ['0.6875rem', { letterSpacing: '0.02em', lineHeight: '1.4' }],
      },
      spacing: {
        1: '0.2rem',
        2: '0.4rem',
        4: '0.9rem',
        8: '1.75rem',
        12: '2.75rem',
      },
      borderRadius: {
        md: '0.375rem',
      },
      boxShadow: {
        ambient: '0px 12px 32px rgba(42, 52, 57, 0.06)',
      },
      backgroundImage: {
        'dot-pattern': 'radial-gradient(#e5e7eb 1px, transparent 1px)',
      },
      keyframes: {
        'pin-in': {
          '0%': { opacity: '0', transform: 'scale(0.4)' },
          '100%': { opacity: '1', transform: 'scale(1)' },
        },
      },
      animation: {
        'pin-in': 'pin-in 0.18s ease-out both',
      },
    },
  },
  plugins: [],
}
