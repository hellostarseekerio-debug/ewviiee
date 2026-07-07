import { motion } from 'framer-motion'
import { useLang } from '../i18n/LanguageContext'
import LanguageToggle from './LanguageToggle'

const LINKS = [
  { key: 'philosophy', href: '#philosophy' },
  { key: 'pillars', href: '#pillars' },
  { key: 'vault', href: '#vault' },
  { key: 'contact', href: '#contact' },
]

export default function Navbar() {
  const { t } = useLang()

  return (
    <motion.header
      className="fixed inset-x-0 top-0 z-50"
      initial={{ y: -80, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 1.1, delay: 0.2, ease: [0.22, 1, 0.36, 1] }}
    >
      <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-5 md:px-10">
        <a href="#top" className="group flex items-baseline gap-3">
          <span className="font-display text-xl tracking-[0.22em] text-gold-gradient">
            {t('nav.brand')}
          </span>
          <span className="hidden font-body text-[9px] uppercase tracking-[0.3em] text-mist transition-colors group-hover:text-gold/80 sm:inline">
            {t('nav.brandBy')}
          </span>
        </a>

        <nav className="hidden items-center gap-9 md:flex">
          {LINKS.map(({ key, href }) => (
            <a
              key={key}
              href={href}
              className="relative font-body text-[11px] uppercase tracking-[0.24em] text-platinum/70 transition-colors hover:text-gold-bright after:absolute after:-bottom-1.5 after:left-0 after:h-px after:w-0 after:bg-gold after:transition-all after:duration-500 hover:after:w-full"
            >
              {t(`nav.${key}`)}
            </a>
          ))}
        </nav>

        <LanguageToggle />
      </div>
    </motion.header>
  )
}
