import { Suspense, useEffect, useMemo, useRef, useState } from 'react'
import { Canvas, useFrame } from '@react-three/fiber'
import { Html, OrbitControls } from '@react-three/drei'
import * as THREE from 'three'
import gsap from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import { CITIES, cityLabel } from '../data/cities'
import { useLang } from '../i18n/LanguageContext'

gsap.registerPlugin(ScrollTrigger)

const MAX_GDP = Math.max(...CITIES.map((c) => c.gdp))

function GdpColumn({ city, index, total, lang }) {
  const meshRef = useRef()
  const [hovered, setHovered] = useState(false)
  const height = 0.5 + (city.gdp / MAX_GDP) * 3.2
  const angle = (index / total) * Math.PI * 2
  const radius = 2.5
  const x = Math.cos(angle) * radius
  const z = Math.sin(angle) * radius

  useFrame((state) => {
    const m = meshRef.current
    // columns rise on first frames, then breathe
    const grow = THREE.MathUtils.lerp(m.scale.y, hovered ? 1.06 : 1, 0.1)
    m.scale.y = grow
    m.material.emissiveIntensity = THREE.MathUtils.lerp(
      m.material.emissiveIntensity,
      hovered ? 1.4 : city.hub ? 0.55 : 0.28,
      0.1
    )
    void state
  })

  return (
    <group position={[x, 0, z]}>
      <mesh
        ref={meshRef}
        position={[0, height / 2, 0]}
        onPointerOver={(e) => { e.stopPropagation(); setHovered(true); document.body.style.cursor = 'pointer' }}
        onPointerOut={() => { setHovered(false); document.body.style.cursor = 'auto' }}
      >
        <boxGeometry args={[0.42, height, 0.42]} />
        <meshStandardMaterial
          color={city.hub ? '#c9a96a' : '#3b445c'}
          emissive={city.hub ? '#c9a96a' : '#5a6b96'}
          emissiveIntensity={city.hub ? 0.55 : 0.28}
          metalness={0.85}
          roughness={0.25}
        />
      </mesh>
      {/* cap */}
      <mesh position={[0, height + 0.02, 0]}>
        <boxGeometry args={[0.46, 0.03, 0.46]} />
        <meshBasicMaterial color={city.hub ? '#f0dcae' : '#8b93a3'} />
      </mesh>

      <Html center distanceFactor={10} position={[0, -0.35, 0]} style={{ pointerEvents: 'none' }} zIndexRange={[10, 0]}>
        <span className="whitespace-nowrap font-body text-[9px] uppercase tracking-[0.22em] text-mist/80">
          {cityLabel(city, lang)}
        </span>
      </Html>

      {hovered && (
        <Html center distanceFactor={8} position={[0, height + 0.6, 0]} style={{ pointerEvents: 'none' }} zIndexRange={[30, 20]}>
          <div className="glass-strong whitespace-nowrap rounded-lg px-4 py-2.5 text-center">
            <p className="font-display text-base text-gold-bright">{cityLabel(city, lang)}</p>
            <p className="font-display text-lg text-platinum">US${city.gdp}B</p>
          </div>
        </Html>
      )}
    </group>
  )
}

function VaultScene({ lang }) {
  const groupRef = useRef()
  useFrame((_, delta) => {
    groupRef.current.rotation.y += delta * 0.12
  })

  return (
    <>
      <ambientLight intensity={0.5} />
      <pointLight position={[5, 7, 5]} intensity={90} color="#e8cf9a" />
      <pointLight position={[-6, 3, -5]} intensity={35} color="#5a6b96" />

      <group ref={groupRef} position={[0, -1.1, 0]}>
        {CITIES.map((city, i) => (
          <GdpColumn key={city.id} city={city} index={i} total={CITIES.length} lang={lang} />
        ))}
        {/* vault floor rings */}
        {[1.4, 2.5, 3.4].map((r) => (
          <mesh key={r} rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.001, 0]}>
            <ringGeometry args={[r - 0.006, r, 96]} />
            <meshBasicMaterial color="#c9a96a" transparent opacity={0.18} side={THREE.DoubleSide} />
          </mesh>
        ))}
        <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.02, 0]}>
          <circleGeometry args={[4.2, 64]} />
          <meshStandardMaterial color="#07080e" metalness={0.9} roughness={0.4} />
        </mesh>
      </group>

      <OrbitControls
        enableZoom={false}
        enablePan={false}
        minPolarAngle={Math.PI / 3.2}
        maxPolarAngle={Math.PI / 2.05}
        rotateSpeed={0.5}
      />
    </>
  )
}

export default function DataVault() {
  const root = useRef(null)
  const counterRef = useRef(null)
  const { t, isZh, lang } = useLang()

  useEffect(() => {
    const ctx = gsap.context(() => {
      gsap.fromTo(
        '[data-vault-reveal]',
        { y: 55, opacity: 0 },
        {
          y: 0,
          opacity: 1,
          duration: 1.3,
          stagger: 0.14,
          ease: 'power3.out',
          scrollTrigger: { trigger: root.current, start: 'top 65%' },
        }
      )
      // GDP odometer: 0.00 -> 1.67
      const state = { v: 0 }
      gsap.to(state, {
        v: t('vault.gdpValue'),
        duration: 2.4,
        ease: 'power2.out',
        scrollTrigger: { trigger: counterRef.current, start: 'top 80%' },
        onUpdate: () => {
          if (counterRef.current) counterRef.current.textContent = `$${state.v.toFixed(2)}T`
        },
      })
    }, root)
    return () => ctx.revert()
  }, [lang, t])

  return (
    <section id="vault" ref={root} className="relative z-10 bg-obsidian py-32 md:py-44">
      <div className="section-shell">
        <div className="grid items-center gap-14 lg:grid-cols-[1fr_1.15fr] lg:gap-8">
          <div>
            <p data-vault-reveal className="eyebrow">{t('vault.eyebrow')}</p>
            <h2
              data-vault-reveal
              className={`display-title mt-8 text-4xl text-platinum md:text-6xl ${isZh ? 'font-tc' : ''}`}
            >
              {t('vault.title')}
            </h2>

            <div data-vault-reveal className="mt-10">
              <p className="font-body text-[10px] uppercase tracking-[0.3em] text-mist">{t('vault.gdpLabel')}</p>
              <p ref={counterRef} className="mt-2 font-display text-6xl tabular-nums text-gold-gradient md:text-7xl">
                $0.00T
              </p>
              <p className={`mt-1 font-body text-xs tracking-[0.2em] text-mist ${isZh ? 'font-tc' : 'uppercase'}`}>
                {t('vault.gdpUnit')}
              </p>
            </div>

            <p data-vault-reveal className="mt-8 max-w-md font-body text-[13px] font-light leading-relaxed text-mist">
              {t('vault.sub')}
            </p>

            <div data-vault-reveal className="mt-10 grid grid-cols-2 gap-4">
              {t('vault.stats').map((s) => (
                <div key={s.label} className="neo rounded-xl px-5 py-4">
                  <p className="font-display text-2xl text-platinum">{s.value}</p>
                  <p className={`mt-1 font-body text-[10px] tracking-[0.16em] text-mist ${isZh ? 'font-tc' : 'uppercase'}`}>
                    {s.label}
                  </p>
                </div>
              ))}
            </div>

            <ul data-vault-reveal className="mt-8 flex flex-wrap gap-2">
              {t('vault.terms').map((term) => (
                <li
                  key={term}
                  className={`rounded-full border border-gold/25 px-4 py-1.5 font-body text-[10px] tracking-[0.14em] text-gold/80 ${isZh ? 'font-tc text-[11px]' : 'uppercase'}`}
                >
                  {term}
                </li>
              ))}
            </ul>
          </div>

          <div data-vault-reveal className="glass relative h-[420px] overflow-hidden rounded-3xl md:h-[540px]">
            <Canvas dpr={[1, 1.75]} camera={{ position: [0, 2.6, 7.2], fov: 40 }}>
              <color attach="background" args={['#06070c']} />
              <fog attach="fog" args={['#06070c', 9, 16]} />
              <Suspense fallback={null}>
                <VaultScene lang={lang} />
              </Suspense>
            </Canvas>
            <div className="pointer-events-none absolute inset-x-0 bottom-0 h-16 bg-gradient-to-t from-obsidian/70 to-transparent" />
          </div>
        </div>
      </div>
    </section>
  )
}
