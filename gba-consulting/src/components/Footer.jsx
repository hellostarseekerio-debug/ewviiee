import { useLang } from '../i18n/LanguageContext'

export default function Footer() {
  const { t, isZh } = useLang()
  const year = new Date().getFullYear()

  return (
    <footer className="relative z-10 border-t border-gold/10 bg-obsidian py-14">
      <div className="section-shell flex flex-col items-center gap-6 text-center">
        <p className="font-display text-lg tracking-[0.24em] text-gold-gradient">GBA × ANITA KO</p>
        <p className={`font-body text-[11px] tracking-[0.18em] text-mist ${isZh ? 'font-tc' : ''}`}>
          {t('footer.line')}
        </p>
        <p className={`font-body text-[10px] tracking-[0.3em] text-gold/50 ${isZh ? 'font-tc' : 'uppercase'}`}>
          {t('footer.credo')}
        </p>
        <p className="font-body text-[10px] text-mist/50">
          © {year} GBA Consulting · GBA Partners — {t('footer.rights')}
        </p>
      </div>
    </footer>
  )
}
