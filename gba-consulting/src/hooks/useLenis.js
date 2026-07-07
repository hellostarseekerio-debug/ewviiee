import { useEffect } from 'react'
import Lenis from 'lenis'
import gsap from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import { sceneState } from '../three/sceneState'

gsap.registerPlugin(ScrollTrigger)

/**
 * Lenis smooth scroll, synced into GSAP's ScrollTrigger and the WebGL scene.
 */
export function useLenis(enabled) {
  useEffect(() => {
    if (!enabled) return

    const lenis = new Lenis({
      duration: 1.35,
      easing: (t) => Math.min(1, 1.001 - Math.pow(2, -10 * t)),
      smoothWheel: true,
      touchMultiplier: 1.6,
    })

    const onScroll = ({ scroll, limit }) => {
      sceneState.scroll = limit > 0 ? scroll / limit : 0
      sceneState.heroProgress = Math.min(scroll / (window.innerHeight * 0.9), 1)
      ScrollTrigger.update()
    }
    lenis.on('scroll', onScroll)

    const raf = (time) => lenis.raf(time * 1000)
    gsap.ticker.add(raf)
    gsap.ticker.lagSmoothing(0)

    return () => {
      lenis.off('scroll', onScroll)
      gsap.ticker.remove(raf)
      lenis.destroy()
    }
  }, [enabled])
}
