import { motion } from 'framer-motion'
import { useLang } from '../i18n/LanguageContext'

const fadeUp = (delay) => ({
  initial: { y: 42, opacity: 0 },
  animate: { y: 0, opacity: 1 },
  transition: { duration: 1.2, delay, ease: [0.22, 1, 0.36, 1] },
})

export default function Hero() {
  const { t, isZh } = useLang()

  return (
    <section id="top" className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden">
      {/* legibility scrim over the WebGL silk */}
      <div
        className="pointer-events-none absolute inset-0"
        style={{ background: 'radial-gradient(ellipse 60% 55% at 50% 46%, rgba(5,6,10,0.72) 0%, rgba(5,6,10,0.38) 55%, transparent 100%)' }}
      />
      <div className="section-shell flex flex-col items-center text-center">
        <motion.p className="eyebrow" {...fadeUp(0.3)}>
          {t('hero.eyebrow')}
        </motion.p>

        <motion.h1
          className={`display-title mt-7 text-balance text-5xl text-platinum md:text-7xl lg:text-8xl ${isZh ? 'font-tc' : ''}`}
          {...fadeUp(0.5)}
        >
          {t('hero.titleA')}
          <br />
          <span className="text-gold-gradient italic">{t('hero.titleB')}</span>
        </motion.h1>

        <motion.p
          className="mt-8 max-w-xl text-balance font-body text-sm font-light leading-relaxed text-mist md:text-base"
          {...fadeUp(0.75)}
        >
          {t('hero.sub')}
        </motion.p>

        <motion.div className="mt-11 flex flex-col items-center gap-4 sm:flex-row" {...fadeUp(0.95)}>
          <a
            href="#contact"
            className="group relative overflow-hidden rounded-full border border-gold/50 px-9 py-3.5 font-body text-[11px] uppercase tracking-[0.28em] text-gold-bright transition-all duration-500 hover:border-gold hover:shadow-[0_0_44px_-8px_rgba(201,169,106,0.55)]"
          >
            <span className="absolute inset-0 -translate-x-full bg-gradient-to-r from-transparent via-gold/15 to-transparent transition-transform duration-700 group-hover:translate-x-full" />
            {t('hero.cta')}
          </a>
          <a
            href="#philosophy"
            className="px-6 py-3 font-body text-[11px] uppercase tracking-[0.28em] text-mist transition-colors hover:text-platinum"
          >
            {t('hero.explore')} →
          </a>
        </motion.div>

        <motion.p
          className="mt-14 animate-shimmer font-body text-[10px] uppercase tracking-[0.3em] text-mist/60"
          {...fadeUp(1.2)}
        >
          ◈ {t('hero.hint')}
        </motion.p>
      </div>

      {/* scroll cue */}
      <motion.div
        className="absolute bottom-8 flex flex-col items-center gap-2"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 1.6, duration: 1 }}
      >
        <span className="font-body text-[9px] uppercase tracking-[0.35em] text-mist/50">{t('hero.scroll')}</span>
        <motion.span
          className="h-10 w-px bg-gradient-to-b from-gold/70 to-transparent"
          animate={{ scaleY: [1, 0.4, 1], opacity: [1, 0.4, 1] }}
          transition={{ duration: 2.2, repeat: Infinity, ease: 'easeInOut' }}
          style={{ transformOrigin: 'top' }}
        />
      </motion.div>
    </section>
  )
}
