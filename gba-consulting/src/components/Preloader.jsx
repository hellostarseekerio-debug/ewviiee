import { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useLang } from '../i18n/LanguageContext'

const MONOGRAM = ['G', 'B', 'A']

export default function Preloader({ onDone }) {
  const [progress, setProgress] = useState(0)
  const [leaving, setLeaving] = useState(false)
  const { t } = useLang()

  useEffect(() => {
    let raf
    const start = performance.now()
    const DURATION = 2400

    const tick = (now) => {
      // ease-out counter: fast start, deliberate finish — the "vault unlocking"
      const linear = Math.min((now - start) / DURATION, 1)
      const eased = 1 - Math.pow(1 - linear, 3)
      setProgress(Math.round(eased * 100))
      if (linear < 1) {
        raf = requestAnimationFrame(tick)
      } else {
        setTimeout(() => {
          setLeaving(true)
          setTimeout(onDone, 900)
        }, 250)
      }
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [onDone])

  return (
    <AnimatePresence>
      {!leaving && (
        <motion.div
          className="fixed inset-0 z-[100] flex flex-col items-center justify-center bg-obsidian"
          exit={{ opacity: 0, scale: 1.04 }}
          transition={{ duration: 0.9, ease: [0.76, 0, 0.24, 1] }}
        >
          {/* Monogram */}
          <div className="relative flex items-center justify-center">
            <motion.div
              className="absolute h-36 w-36 rounded-full border border-gold/25 md:h-44 md:w-44"
              initial={{ scale: 0.6, opacity: 0, rotate: -90 }}
              animate={{ scale: 1, opacity: 1, rotate: 0 }}
              transition={{ duration: 1.4, ease: [0.22, 1, 0.36, 1] }}
            />
            <motion.div
              className="absolute h-36 w-36 rounded-full md:h-44 md:w-44"
              style={{
                background:
                  'conic-gradient(from 0deg, transparent 0%, rgba(201,169,106,0.5) 12%, transparent 24%)',
                maskImage: 'radial-gradient(circle, transparent 64%, black 66%)',
                WebkitMaskImage: 'radial-gradient(circle, transparent 64%, black 66%)',
              }}
              animate={{ rotate: 360 }}
              transition={{ duration: 2.6, repeat: Infinity, ease: 'linear' }}
            />
            <div className="flex overflow-hidden py-2">
              {MONOGRAM.map((ch, i) => (
                <motion.span
                  key={ch}
                  className="font-display text-5xl tracking-[0.18em] text-gold-gradient md:text-6xl"
                  initial={{ y: 80, opacity: 0 }}
                  animate={{ y: 0, opacity: 1 }}
                  transition={{ delay: 0.35 + i * 0.14, duration: 1, ease: [0.22, 1, 0.36, 1] }}
                >
                  {ch}
                </motion.span>
              ))}
            </div>
          </div>

          <motion.p
            className="mt-10 font-body text-[10px] uppercase tracking-widest2 text-mist"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.9 }}
          >
            {progress < 55 ? t('preloader.establishing') : t('preloader.cities')}
          </motion.p>

          {/* Percentage counter */}
          <div className="mt-6 flex w-56 flex-col items-center gap-3 md:w-72">
            <span className="font-display text-2xl tabular-nums text-platinum">
              {String(progress).padStart(3, '0')}
              <span className="ml-1 text-sm text-gold">%</span>
            </span>
            <div className="neo-inset h-[3px] w-full overflow-hidden rounded-full">
              <div
                className="h-full rounded-full bg-gradient-to-r from-gold-dim via-gold to-gold-bright transition-[width] duration-100"
                style={{ width: `${progress}%` }}
              />
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
