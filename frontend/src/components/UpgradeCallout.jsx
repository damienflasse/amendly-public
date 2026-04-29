import { Link } from 'react-router-dom'

export default function UpgradeCallout({
  eyebrow = null,
  title,
  body,
  benefits = [],
  ctaLabel,
  ctaTo,
  note = null,
}) {
  return (
    <div className="relative overflow-hidden rounded-2xl bg-[linear-gradient(135deg,#0f2747_0%,#173f73_52%,#2b6cc1_100%)] px-6 py-6 text-white shadow-ambient">
      <div
        aria-hidden="true"
        className="absolute inset-0 bg-[radial-gradient(circle_at_top_right,_rgba(255,255,255,0.18),_transparent_42%)]"
      />

      <div className="relative">
        {eyebrow && (
          <p className="font-body text-label-sm uppercase tracking-[0.16em] text-white/65">
            {eyebrow}
          </p>
        )}
        <h3 className="mt-2 font-display text-headline-sm tracking-[-0.01em]">
          {title}
        </h3>
        <p className="mt-3 max-w-2xl font-body text-body-md text-white/85">
          {body}
        </p>

        {benefits.length > 0 && (
          <ul className="mt-5 grid gap-3 sm:grid-cols-3">
            {benefits.map((benefit, index) => (
              <li
                key={`${benefit}-${index}`}
                className="rounded-xl bg-white/10 px-4 py-3 backdrop-blur-sm"
              >
                <p className="font-body text-label-sm uppercase tracking-[0.12em] text-white/55">
                  {String(index + 1).padStart(2, '0')}
                </p>
                <p className="mt-2 font-body text-body-md text-white">
                  {benefit}
                </p>
              </li>
            ))}
          </ul>
        )}

        {(ctaLabel || note) && (
          <div className="mt-5 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            {ctaLabel && ctaTo ? (
              <Link
                to={ctaTo}
                className="inline-flex items-center justify-center rounded-xl bg-white px-5 py-2.5 font-body text-body-md font-semibold text-[#123766] transition-opacity hover:opacity-90"
              >
                {ctaLabel}
              </Link>
            ) : (
              <span />
            )}
            {note && (
              <p className="max-w-xl font-body text-label-sm text-white/65">
                {note}
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
