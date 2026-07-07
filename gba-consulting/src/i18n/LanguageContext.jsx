import { createContext, useCallback, useContext, useMemo, useState } from 'react'
import { translations } from './translations'

const LanguageContext = createContext(null)

export function LanguageProvider({ children }) {
  const [lang, setLang] = useState('en')

  const toggle = useCallback(() => {
    setLang((l) => {
      const next = l === 'en' ? 'zh' : 'en'
      document.documentElement.lang = translations[next].meta.htmlLang
      return next
    })
  }, [])

  const value = useMemo(() => {
    // t('pillars.items') — dot-path lookup into the structured resource object
    const t = (path) =>
      path.split('.').reduce((node, key) => (node == null ? node : node[key]), translations[lang])
    return { lang, toggle, t, isZh: lang === 'zh' }
  }, [lang, toggle])

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>
}

export function useLang() {
  const ctx = useContext(LanguageContext)
  if (!ctx) throw new Error('useLang must be used inside <LanguageProvider>')
  return ctx
}
