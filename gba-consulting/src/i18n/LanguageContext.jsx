import { createContext, useCallback, useContext, useMemo, useState } from 'react'
import { translations } from './translations'

const LanguageContext = createContext(null)

export const LANGS = [
  { code: 'en', label: 'EN' },
  { code: 'zh', label: '繁' },
  { code: 'cn', label: '简' },
]

export function LanguageProvider({ children }) {
  const [lang, setLangState] = useState('en')

  const setLang = useCallback((code) => {
    if (!translations[code]) return
    document.documentElement.lang = translations[code].meta.htmlLang
    setLangState(code)
  }, [])

  const value = useMemo(() => {
    // t('pillars.items') — dot-path lookup into the structured resource object
    const t = (path) =>
      path.split('.').reduce((node, key) => (node == null ? node : node[key]), translations[lang])
    // isZh = any Chinese variant (drives CJK typography treatment)
    return { lang, setLang, t, isZh: lang !== 'en' }
  }, [lang, setLang])

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>
}

export function useLang() {
  const ctx = useContext(LanguageContext)
  if (!ctx) throw new Error('useLang must be used inside <LanguageProvider>')
  return ctx
}
