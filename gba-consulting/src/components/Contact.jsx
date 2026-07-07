import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useLang } from '../i18n/LanguageContext'

const field =
  'neo-inset w-full rounded-xl bg-transparent px-5 py-3.5 font-body text-sm text-platinum placeholder:text-mist/40 outline-none transition-shadow focus:shadow-[0_0_0_1px_rgba(201,169,106,0.45)]'

const label = 'mb-2 block font-body text-[10px] uppercase tracking-[0.26em] text-gold/70'

export default function Contact() {
  const { t, isZh } = useLang()
  const [status, setStatus] = useState('idle') // idle | sending | done

  const submit = (e) => {
    e.preventDefault()
    if (status !== 'idle') return
    setStatus('sending')
    // Concierge illusion — wire to your CRM / mail service in production
    setTimeout(() => setStatus('done'), 1600)
  }

  return (
    <section id="contact" className="relative z-10 bg-obsidian py-32 md:py-44">
      <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-gold/30 to-transparent" />
      <div className="section-shell max-w-4xl">
        <motion.div
          initial={{ y: 50, opacity: 0 }}
          whileInView={{ y: 0, opacity: 1 }}
          viewport={{ once: true, margin: '-15%' }}
          transition={{ duration: 1.1, ease: [0.22, 1, 0.36, 1] }}
          className="text-center"
        >
          <p className="eyebrow">{t('contact.eyebrow')}</p>
          <h2 className={`display-title mt-8 text-4xl text-platinum md:text-6xl ${isZh ? 'font-tc' : ''}`}>
            {t('contact.title')}
          </h2>
          <p className="mx-auto mt-6 max-w-lg font-body text-[13px] font-light leading-relaxed text-mist">
            {t('contact.sub')}
          </p>
        </motion.div>

        <motion.div
          initial={{ y: 70, opacity: 0 }}
          whileInView={{ y: 0, opacity: 1 }}
          viewport={{ once: true, margin: '-10%' }}
          transition={{ duration: 1.2, delay: 0.15, ease: [0.22, 1, 0.36, 1] }}
          className="glass-strong relative mt-14 overflow-hidden rounded-3xl p-8 md:p-12"
        >
          {/* wax-seal corner ornament */}
          <div className="pointer-events-none absolute -right-8 -top-8 h-28 w-28 rounded-full border border-gold/20" />
          <div className="pointer-events-none absolute -right-4 -top-4 h-16 w-16 rounded-full border border-gold/15" />

          <AnimatePresence mode="wait">
            {status === 'done' ? (
              <motion.div
                key="done"
                initial={{ opacity: 0, scale: 0.96 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.8, ease: [0.22, 1, 0.36, 1] }}
                className="flex min-h-[320px] flex-col items-center justify-center text-center"
              >
                <motion.div
                  className="flex h-20 w-20 items-center justify-center rounded-full border border-gold/50"
                  initial={{ rotate: -30, scale: 0.6 }}
                  animate={{ rotate: 0, scale: 1 }}
                  transition={{ type: 'spring', stiffness: 160, damping: 14, delay: 0.2 }}
                >
                  <span className="font-display text-3xl text-gold-bright">✓</span>
                </motion.div>
                <p className={`mt-8 font-display text-3xl text-platinum ${isZh ? 'font-tc' : ''}`}>{t('contact.done')}</p>
                <p className="mt-3 font-body text-sm font-light text-mist">{t('contact.doneSub')}</p>
              </motion.div>
            ) : (
              <motion.form key="form" exit={{ opacity: 0, y: -20 }} onSubmit={submit} className="grid gap-6 md:grid-cols-2">
                <div>
                  <label htmlFor="c-name" className={label}>{t('contact.name')}</label>
                  <input id="c-name" required className={field} placeholder={t('contact.namePh')} />
                </div>
                <div>
                  <label htmlFor="c-org" className={label}>{t('contact.org')}</label>
                  <input id="c-org" required className={field} placeholder={t('contact.orgPh')} />
                </div>
                <div>
                  <label htmlFor="c-mandate" className={label}>{t('contact.mandate')}</label>
                  <select id="c-mandate" className={field} defaultValue={t('contact.mandateOptions')[0]}>
                    {t('contact.mandateOptions').map((o) => (
                      <option key={o} className="bg-ink">{o}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label htmlFor="c-scale" className={label}>{t('contact.scale')}</label>
                  <select id="c-scale" className={field} defaultValue={t('contact.scaleOptions')[1]}>
                    {t('contact.scaleOptions').map((o) => (
                      <option key={o} className="bg-ink">{o}</option>
                    ))}
                  </select>
                </div>
                <div className="md:col-span-2">
                  <label htmlFor="c-brief" className={label}>{t('contact.brief')}</label>
                  <textarea id="c-brief" rows={4} className={field} placeholder={t('contact.briefPh')} />
                </div>
                <div className="flex flex-col items-center gap-5 md:col-span-2">
                  <motion.button
                    type="submit"
                    whileTap={{ scale: 0.97 }}
                    disabled={status === 'sending'}
                    className="group relative w-full overflow-hidden rounded-full border border-gold/60 py-4 font-body text-[11px] uppercase tracking-[0.3em] text-gold-bright transition-all duration-500 hover:shadow-[0_0_50px_-10px_rgba(201,169,106,0.6)] disabled:opacity-60 md:w-96"
                  >
                    <span className="absolute inset-0 -translate-x-full bg-gradient-to-r from-transparent via-gold/20 to-transparent transition-transform duration-700 group-hover:translate-x-full" />
                    {status === 'sending' ? t('contact.submitting') : t('contact.submit')}
                  </motion.button>
                  <p className="font-body text-[10px] tracking-[0.14em] text-mist/60">◈ {t('contact.privacy')}</p>
                </div>
              </motion.form>
            )}
          </AnimatePresence>
        </motion.div>
      </div>
    </section>
  )
}
