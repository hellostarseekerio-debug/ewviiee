import { useRef } from 'react'
import { motion, useMotionValue, useSpring } from 'framer-motion'
import { useLang, LANGS } from '../i18n/LanguageContext'

const ARIA = { en: 'Switch to English', zh: '切換至繁體中文', cn: '切换至简体中文' }

/**
 * Minimalist magnetic toggle — the pill leans toward the cursor
 * (spring physics), and the gold puck slides between EN / 繁 / 简.
 */
export default function LanguageToggle() {
  const { lang, setLang } = useLang()
  const ref = useRef(null)

  const mx = useMotionValue(0)
  const my = useMotionValue(0)
  const x = useSpring(mx, { stiffness: 180, damping: 14, mass: 0.4 })
  const y = useSpring(my, { stiffness: 180, damping: 14, mass: 0.4 })

  const onMove = (e) => {
    const r = ref.current.getBoundingClientRect()
    mx.set((e.clientX - (r.left + r.width / 2)) * 0.35)
    my.set((e.clientY - (r.top + r.height / 2)) * 0.35)
  }
  const onLeave = () => {
    mx.set(0)
    my.set(0)
  }

  const activeIndex = LANGS.findIndex((l) => l.code === lang)

  return (
    <motion.div
      ref={ref}
      style={{ x, y }}
      onPointerMove={onMove}
      onPointerLeave={onLeave}
      role="radiogroup"
      aria-label="Language"
      className="glass relative flex h-9 w-[6.9rem] items-center rounded-full p-1 transition-colors hover:border-gold/40"
    >
      <span
        aria-hidden="true"
        className="absolute left-1 h-7 w-[2.1rem] rounded-full bg-gradient-to-b from-gold-bright/90 to-gold-dim/90 shadow-[0_2px_10px_rgba(201,169,106,0.45)]"
        style={{
          transform: `translateX(${activeIndex * 34.15}px)`,
          transition: 'transform 0.45s cubic-bezier(0.22, 1, 0.36, 1)',
        }}
      />
      {LANGS.map(({ code, label }) => (
        <button
          key={code}
          type="button"
          role="radio"
          aria-checked={lang === code}
          aria-label={ARIA[code]}
          onClick={() => setLang(code)}
          className={`relative z-10 flex-1 text-center outline-none transition-colors ${
            code === 'en' ? 'font-body text-[11px] font-medium tracking-wide' : 'font-tc text-[12px] font-medium'
          } ${lang === code ? 'text-obsidian' : 'text-mist hover:text-platinum'}`}
        >
          {label}
        </button>
      ))}
    </motion.div>
  )
}
