import React from 'react';

/**
 * Composant Logo Amendly basé sur la Charte Graphique Canvas
 * Monogramme stylisé "A" + Typographie
 */
export default function Logo({ className = '' }) {
  return (
    <div className={`flex items-center gap-3 ${className}`}>
      {/* Monogramme SVG "A" */}
      <svg
        width="32"
        height="32"
        viewBox="0 0 32 32"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className="shrink-0"
      >
        {/* Ligne principale (Left leg + top) */}
        <path
          d="M12 28L14 8C14.5 5 17.5 4 20 6L22 7"
          stroke="#2563EB"
          strokeWidth="4"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        {/* Ligne transversale (Right leg crossing) */}
        <path
          d="M24 26L10 14"
          stroke="#94A3B8"
          strokeWidth="4"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        {/* Point/Accent optionnel pour la "précision" */}
        <circle cx="22" cy="7" r="2" fill="#0F172A" />
      </svg>
      
      {/* Typographie de la marque */}
      <span className="font-display font-black text-2xl tracking-[-0.04em] text-amendly-dark">
        amendly
      </span>
    </div>
  );
}
