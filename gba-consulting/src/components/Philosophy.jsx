import { useEffect, useRef } from 'react'
import gsap from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import { useLang } from '../i18n/LanguageContext'

gsap.registerPlugin(ScrollTrigger)

export default function Philosophy() {
  const root = useRef(null)
  const sigPath = useRef(null)
  const { t, isZh, lang } = useLang()

  useEffect(() => {
    const ctx = gsap.context(() => {
      gsap.fromTo(
        '[data-reveal]',
        { y: 60, opacity: 0 },
        {
          y: 0,
          opacity: 1,
          duration: 1.4,
          stagger: 0.18,
          ease: 'power3.out',
          scrollTrigger: { trigger: root.current, start: 'top 68%' },
        }
      )
      // hand-drawn signature flourish
      const path = sigPath.current
      const len = path.getTotalLength()
      gsap.fromTo(
        path,
        { strokeDasharray: len, strokeDashoffset: len },
        {
          strokeDashoffset: 0,
          duration: 2.2,
          ease: 'power2.inOut',
          scrollTrigger: { trigger: path, start: 'top 85%' },
        }
      )
    }, root)
    return () => ctx.revert()
  }, [lang])

  return (
    <section id="philosophy" ref={root} className="relative z-10 py-32 md:py-44">
      <div className="pointer-events-none absolute inset-0 bg-gradient-to-b from-transparent via-obsidian/80 to-obsidian" />
      <div className="section-shell relative">
        <p data-reveal className="eyebrow">
          {t('philosophy.eyebrow')}
        </p>

        <blockquote
          data-reveal
          className={`display-title mt-10 max-w-4xl text-balance text-3xl text-platinum md:text-5xl ${isZh ? 'font-tc' : 'italic'}`}
        >
          {t('philosophy.quote')}
        </blockquote>

        <div className="mt-14 grid gap-12 md:grid-cols-[1.4fr_1fr] md:gap-20">
          <p data-reveal className="max-w-xl font-body text-sm font-light leading-loose text-mist md:text-base">
            {t('philosophy.body')}
          </p>

          <div data-reveal className="flex flex-col justify-between gap-10">
            <ul className="space-y-4">
              {t('philosophy.values').map((v, i) => (
                <li key={v} className="flex items-center gap-4">
                  <span className="font-display text-sm text-gold/70">{String(i + 1).padStart(2, '0')}</span>
                  <span className="h-px flex-1 bg-gradient-to-r from-gold/30 to-transparent" />
                  <span className={`font-display text-lg tracking-wide text-platinum ${isZh ? 'font-tc' : ''}`}>{v}</span>
                </li>
              ))}
            </ul>

            {/* The Signature */}
            <div className="text-right">
              <p className="font-display text-3xl italic tracking-wide text-gold-gradient md:text-4xl">
                {t('philosophy.signature')}
              </p>
              <svg viewBox="0 0 260 40" className="ml-auto mt-1 h-8 w-56" fill="none" aria-hidden="true">
                <path
                  ref={sigPath}
                  d="M6 26 C 48 8, 74 34, 108 22 S 168 6, 196 20 S 240 30, 254 14"
                  stroke="url(#sigGold)"
                  strokeWidth="1.6"
                  strokeLinecap="round"
                />
                <defs>
                  <linearGradient id="sigGold" x1="0" y1="0" x2="260" y2="0" gradientUnits="userSpaceOnUse">
                    <stop stopColor="#8a6f3e" />
                    <stop offset="0.5" stopColor="#e8cf9a" />
                    <stop offset="1" stopColor="#8a6f3e" />
                  </linearGradient>
                </defs>
              </svg>
              <p className="mt-2 font-body text-[10px] uppercase tracking-[0.25em] text-mist">
                {t('philosophy.role')}
              </p>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
