import { useEffect, useRef } from 'react'
import gsap from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import { motion } from 'framer-motion'
import { useLang } from '../i18n/LanguageContext'

gsap.registerPlugin(ScrollTrigger)

function PillarCard({ item, isZh }) {
  return (
    <motion.article
      data-pillar
      whileHover={{ y: -10 }}
      transition={{ type: 'spring', stiffness: 220, damping: 22 }}
      className="glass group relative flex flex-col overflow-hidden rounded-2xl p-8 md:p-10"
    >
      <div className="pointer-events-none absolute -right-10 -top-12 font-display text-[9rem] leading-none text-gold/[0.06] transition-colors duration-700 group-hover:text-gold/[0.12]">
        {item.num}
      </div>

      <span className="font-display text-sm tracking-[0.3em] text-gold/70">{item.num}</span>
      <h3 className={`mt-5 font-display text-2xl text-platinum md:text-[1.7rem] ${isZh ? 'font-tc' : ''}`}>
        {item.title}
      </h3>
      <span className="mt-5 h-px w-10 bg-gold/50 transition-all duration-700 group-hover:w-full group-hover:bg-gold/80" />
      <p className="mt-6 flex-1 font-body text-[13px] font-light leading-relaxed text-mist">
        {item.desc}
      </p>

      <ul className="mt-8 flex flex-wrap gap-2">
        {item.tags.map((tag) => (
          <li
            key={tag}
            className={`neo rounded-full px-3.5 py-1.5 font-body text-[10px] tracking-[0.14em] text-gold/80 ${isZh ? 'font-tc' : 'uppercase'}`}
          >
            {tag}
          </li>
        ))}
      </ul>
    </motion.article>
  )
}

export default function Pillars() {
  const root = useRef(null)
  const { t, isZh, lang } = useLang()

  useEffect(() => {
    const ctx = gsap.context(() => {
      gsap.fromTo(
        '[data-pillar-head]',
        { y: 50, opacity: 0 },
        {
          y: 0,
          opacity: 1,
          duration: 1.2,
          stagger: 0.15,
          ease: 'power3.out',
          scrollTrigger: { trigger: root.current, start: 'top 70%' },
        }
      )
      gsap.fromTo(
        '[data-pillar]',
        { y: 90, opacity: 0, rotateX: 8 },
        {
          y: 0,
          opacity: 1,
          rotateX: 0,
          duration: 1.4,
          stagger: 0.2,
          ease: 'power3.out',
          scrollTrigger: { trigger: root.current, start: 'top 55%' },
        }
      )
    }, root)
    return () => ctx.revert()
  }, [lang])

  return (
    <section id="pillars" ref={root} className="relative z-10 bg-obsidian py-32 md:py-44">
      <div className="section-shell">
        <p data-pillar-head className="eyebrow">
          {t('pillars.eyebrow')}
        </p>
        <h2
          data-pillar-head
          className={`display-title mt-8 max-w-2xl text-4xl text-platinum md:text-6xl ${isZh ? 'font-tc' : ''}`}
        >
          {t('pillars.title')}
        </h2>

        <div className="mt-16 grid gap-6 md:mt-20 md:grid-cols-3 md:gap-7" style={{ perspective: '1200px' }}>
          {t('pillars.items').map((item) => (
            <PillarCard key={item.num} item={item} isZh={isZh} />
          ))}
        </div>
      </div>
    </section>
  )
}
