import { useState } from 'react'
import { LanguageProvider } from './i18n/LanguageContext'
import { useLenis } from './hooks/useLenis'
import Preloader from './components/Preloader'
import Scene from './three/Scene'
import Navbar from './components/Navbar'
import Hero from './components/Hero'
import Philosophy from './components/Philosophy'
import Pillars from './components/Pillars'
import DataVault from './components/DataVault'
import Contact from './components/Contact'
import Footer from './components/Footer'

function Experience() {
  const [ready, setReady] = useState(false)
  useLenis(ready)

  return (
    <>
      {!ready && <Preloader onDone={() => setReady(true)} />}

      <Scene />

      <div className={`relative transition-opacity duration-1000 ${ready ? 'opacity-100' : 'opacity-0'}`}>
        <Navbar />
        <main>
          <Hero />
          <Philosophy />
          <Pillars />
          <DataVault />
          <Contact />
        </main>
        <Footer />
      </div>
    </>
  )
}

export default function App() {
  return (
    <LanguageProvider>
      <Experience />
    </LanguageProvider>
  )
}
