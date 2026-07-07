import { useRef } from 'react'
import { motion, useMotionValue, useSpring } from 'framer-motion'
import { useLang } from '../i18n/LanguageContext'

/**
 * Minimalist magnetic toggle — the pill leans toward the cursor
 * (spring physics), and the gold puck slides between 繁 and EN.
 */
export default function LanguageToggle() {
  const { lang, toggle } = useLang()
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

  return (
    <motion.button
      ref={ref}
      style={{ x, y }}
      onPointerMove={onMove}
      onPointerLeave={onLeave}
      onClick={toggle}
      aria-label={lang === 'en' ? 'Switch to Traditional Chinese' : '切換至英文'}
      className="glass relative flex h-9 w-[4.6rem] items-center rounded-full px-1 outline-none transition-colors hover:border-gold/40"
    >
      <motion.span
        layout
        className="absolute h-7 w-8 rounded-full bg-gradient-to-b from-gold-bright/90 to-gold-dim/90 shadow-[0_2px_10px_rgba(201,169,106,0.45)]"
        animate={{ left: lang === 'en' ? 4 : 'calc(100% - 2.25rem)' }}
        transition={{ type: 'spring', stiffness: 400, damping: 30 }}
      />
      <span
        className={`relative z-10 flex-1 text-center font-body text-[11px] font-medium tracking-wide transition-colors ${
          lang === 'en' ? 'text-obsidian' : 'text-mist'
        }`}
      >
        EN
      </span>
      <span
        className={`relative z-10 flex-1 text-center font-tc text-[12px] font-medium transition-colors ${
          lang === 'zh' ? 'text-obsidian' : 'text-mist'
        }`}
      >
        繁
      </span>
    </motion.button>
  )
}
