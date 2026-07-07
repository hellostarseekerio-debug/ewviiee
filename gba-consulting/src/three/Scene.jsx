import { Suspense, useEffect, useMemo, useRef } from 'react'
import { Canvas, useFrame } from '@react-three/fiber'
import {
  EffectComposer,
  Bloom,
  ChromaticAberration,
  Noise,
  Vignette,
  DepthOfField,
} from '@react-three/postprocessing'
import { BlendFunction } from 'postprocessing'
import * as THREE from 'three'
import LiquidSilk from './LiquidSilk'
import GBANexus from './GBANexus'
import { sceneState } from './sceneState'

/** Smooths the raw pointer for parallax + drives scroll-linked DoF focus. */
function FrameDriver({ dofRef, caRef }) {
  useFrame(() => {
    sceneState.pointerSmooth.lerp(sceneState.pointer, 0.05)

    // Depth of Field breathes with scroll: crisp on load, dreamlike on exit
    if (dofRef.current) {
      const p = sceneState.heroProgress
      dofRef.current.bokehScale = 1.2 + p * 6.5
      const co = dofRef.current.circleOfConfusionMaterial
      if (co) {
        co.uniforms.focusDistance.value = 0.02 + p * 0.3
        co.uniforms.focalLength.value = 0.06 - p * 0.035
      }
    }
    // Chromatic aberration flares slightly during the cinematic zoom
    if (caRef.current?.offset?.set) {
      const focus = sceneState.focusCity ? 1.9 : 1.0
      caRef.current.offset.set(0.00055 * focus, 0.0004 * focus)
    }
  })
  return null
}

export default function Scene() {
  const dofRef = useRef()
  const caRef = useRef()
  const caOffset = useMemo(() => new THREE.Vector2(0.00055, 0.0004), [])

  const isMobile = useMemo(
    () => typeof window !== 'undefined' && window.matchMedia('(max-width: 768px)').matches,
    []
  )

  useEffect(() => {
    const onMove = (e) => {
      sceneState.pointer.set(
        (e.clientX / window.innerWidth) * 2 - 1,
        -(e.clientY / window.innerHeight) * 2 + 1
      )
    }
    window.addEventListener('pointermove', onMove, { passive: true })
    return () => window.removeEventListener('pointermove', onMove)
  }, [])

  return (
    <div className="fixed inset-0 z-0" aria-hidden="true">
      <Canvas
        // the DOM narrative scrolls above this fixed canvas — take events from <body>
        eventSource={document.body}
        eventPrefix="client"
        dpr={isMobile ? [1, 1.5] : [1, 2]}
        camera={{ position: [0, 0, 9.5], fov: 42, near: 0.1, far: 60 }}
        gl={{
          antialias: false,
          powerPreference: 'high-performance',
          toneMapping: THREE.ACESFilmicToneMapping,
        }}
      >
        <color attach="background" args={['#05060a']} />
        <fog attach="fog" args={['#05060a', 12, 26]} />
        <ambientLight intensity={0.35} />
        <pointLight position={[4, 6, 6]} intensity={40} color="#e8cf9a" />
        <pointLight position={[-6, -4, 4]} intensity={18} color="#5a6b96" />

        <Suspense fallback={null}>
          <LiquidSilk />
          <GBANexus isMobile={isMobile} />
        </Suspense>

        <FrameDriver dofRef={dofRef} caRef={caRef} />

        <EffectComposer multisampling={0}>
          {!isMobile && (
            <DepthOfField ref={dofRef} focusDistance={0.02} focalLength={0.06} bokehScale={1.2} />
          )}
          <Bloom
            intensity={0.85}
            luminanceThreshold={0.18}
            luminanceSmoothing={0.9}
            mipmapBlur
          />
          <ChromaticAberration
            ref={caRef}
            offset={caOffset}
            radialModulation
            modulationOffset={0.4}
          />
          <Noise premultiply blendFunction={BlendFunction.SCREEN} opacity={0.32} />
          <Vignette eskil={false} offset={0.18} darkness={0.92} />
        </EffectComposer>
      </Canvas>
    </div>
  )
}
