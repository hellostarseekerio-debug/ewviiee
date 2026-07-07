import { useMemo, useRef, useState } from 'react'
import { useFrame } from '@react-three/fiber'
import { Html, Line } from '@react-three/drei'
import * as THREE from 'three'
import { CITIES, cityPosition, cityLabel, cityTech } from '../data/cities'
import { sceneState, HOME_CAMERA, HOME_LOOK } from './sceneState'
import { useLang } from '../i18n/LanguageContext'

/* ------------------------------------------------------------------ */
/*  Generative point cloud — gaussian clusters around each city,       */
/*  breathing via a custom GLSL point shader.                          */
/* ------------------------------------------------------------------ */

const pointsVertex = /* glsl */ `
  attribute float aPhase;
  attribute float aSize;
  attribute vec3 aColor;
  uniform float uTime;
  uniform vec2 uMouse;
  varying vec3 vColor;
  varying float vTwinkle;

  void main() {
    vec3 p = position;
    // slow orbital breathing
    p.x += sin(uTime * 0.35 + aPhase * 6.2831) * 0.05;
    p.y += cos(uTime * 0.28 + aPhase * 6.2831) * 0.05;
    p.z += sin(uTime * 0.22 + aPhase * 12.566) * 0.09;

    // cursor gravitation — the constellation leans toward the pointer
    vec2 m = uMouse * vec2(3.2, 2.2);
    vec2 d = m - p.xy;
    float g = exp(-dot(d, d) * 0.55);
    p.xy += d * g * 0.12;
    p.z += g * 0.35;

    vec4 mv = modelViewMatrix * vec4(p, 1.0);
    gl_Position = projectionMatrix * mv;
    gl_PointSize = aSize * (26.0 / -mv.z) * (0.75 + 0.5 * g);

    vColor = aColor;
    vTwinkle = 0.55 + 0.45 * sin(uTime * (1.2 + aPhase) + aPhase * 40.0);
  }
`

const pointsFragment = /* glsl */ `
  varying vec3 vColor;
  varying float vTwinkle;
  void main() {
    vec2 c = gl_PointCoord - 0.5;
    float d = length(c);
    float alpha = smoothstep(0.5, 0.05, d) * vTwinkle;
    if (alpha < 0.01) discard;
    gl_FragColor = vec4(vColor, alpha);
  }
`

function NexusPoints({ count }) {
  const matRef = useRef()

  const { positions, phases, sizes, colors } = useMemo(() => {
    const positions = new Float32Array(count * 3)
    const phases = new Float32Array(count)
    const sizes = new Float32Array(count)
    const colors = new Float32Array(count * 3)
    const gold = new THREE.Color('#c9a96a')
    const platinum = new THREE.Color('#93a0b8')
    const deep = new THREE.Color('#3c465c')
    const tmp = new THREE.Color()

    const totalGdp = CITIES.reduce((s, c) => s + c.gdp, 0)
    let i = 0
    for (const city of CITIES) {
      const [cx, cy] = cityPosition(city)
      const share = Math.max(Math.round((city.gdp / totalGdp) * count * 0.82), 60)
      const spread = 0.35 + Math.sqrt(city.gdp) * 0.028
      for (let k = 0; k < share && i < count; k++, i++) {
        // gaussian-ish scatter via averaged randoms
        const gx = (Math.random() + Math.random() + Math.random()) / 3 - 0.5
        const gy = (Math.random() + Math.random() + Math.random()) / 3 - 0.5
        positions[i * 3] = cx + gx * spread * 2.4
        positions[i * 3 + 1] = cy + gy * spread * 2.0
        positions[i * 3 + 2] = (Math.random() - 0.5) * 0.9
        phases[i] = Math.random()
        sizes[i] = 0.6 + Math.random() * (city.hub ? 1.6 : 1.1)
        tmp.copy(Math.random() < (city.hub ? 0.5 : 0.22) ? gold : Math.random() < 0.5 ? platinum : deep)
        colors[i * 3] = tmp.r
        colors[i * 3 + 1] = tmp.g
        colors[i * 3 + 2] = tmp.b
      }
    }
    // ambient dust filling the estuary between cities
    for (; i < count; i++) {
      positions[i * 3] = (Math.random() - 0.5) * 9
      positions[i * 3 + 1] = (Math.random() - 0.5) * 6.5
      positions[i * 3 + 2] = (Math.random() - 0.5) * 2.4
      phases[i] = Math.random()
      sizes[i] = 0.35 + Math.random() * 0.6
      tmp.copy(deep)
      colors[i * 3] = tmp.r
      colors[i * 3 + 1] = tmp.g
      colors[i * 3 + 2] = tmp.b
    }
    return { positions, phases, sizes, colors }
  }, [count])

  const uniforms = useMemo(
    () => ({ uTime: { value: 0 }, uMouse: { value: new THREE.Vector2() } }),
    []
  )

  useFrame((state) => {
    matRef.current.uniforms.uTime.value = state.clock.elapsedTime
    matRef.current.uniforms.uMouse.value.lerp(sceneState.pointer, 0.06)
  })

  return (
    <points>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
        <bufferAttribute attach="attributes-aPhase" args={[phases, 1]} />
        <bufferAttribute attach="attributes-aSize" args={[sizes, 1]} />
        <bufferAttribute attach="attributes-aColor" args={[colors, 3]} />
      </bufferGeometry>
      <shaderMaterial
        ref={matRef}
        vertexShader={pointsVertex}
        fragmentShader={pointsFragment}
        uniforms={uniforms}
        transparent
        depthWrite={false}
        blending={THREE.AdditiveBlending}
      />
    </points>
  )
}

/* ------------------------------------------------------------------ */
/*  Golden corridors between the three hub cities and their satellites */
/* ------------------------------------------------------------------ */

function Corridors() {
  const lines = useMemo(() => {
    const hubs = CITIES.filter((c) => c.hub)
    const out = []
    // hub triangle
    for (let a = 0; a < hubs.length; a++) {
      for (let b = a + 1; b < hubs.length; b++) {
        out.push({ from: cityPosition(hubs[a]), to: cityPosition(hubs[b]), hub: true })
      }
    }
    // each satellite links to its nearest hub
    for (const city of CITIES.filter((c) => !c.hub)) {
      const p = cityPosition(city)
      let best = null
      let bestD = Infinity
      for (const hub of hubs) {
        const q = cityPosition(hub)
        const d = (p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2
        if (d < bestD) { bestD = d; best = q }
      }
      out.push({ from: p, to: best, hub: false })
    }
    return out.map(({ from, to, hub }) => {
      const mid = new THREE.Vector3(
        (from[0] + to[0]) / 2,
        (from[1] + to[1]) / 2,
        0.55 + Math.random() * 0.5
      )
      const curve = new THREE.QuadraticBezierCurve3(
        new THREE.Vector3(...from),
        mid,
        new THREE.Vector3(...to)
      )
      return { pts: curve.getPoints(40), hub }
    })
  }, [])

  return (
    <group>
      {lines.map(({ pts, hub }, i) => (
        <Line
          key={i}
          points={pts}
          color={hub ? '#c9a96a' : '#46506a'}
          lineWidth={hub ? 1.4 : 0.8}
          transparent
          opacity={hub ? 0.55 : 0.28}
        />
      ))}
    </group>
  )
}

/* ------------------------------------------------------------------ */
/*  Interactive nodes — hover triggers the cinematic zoom + micro-data */
/* ------------------------------------------------------------------ */

function CityNode({ city }) {
  const [hovered, setHovered] = useState(false)
  const ringRef = useRef()
  const coreRef = useRef()
  const { lang, t } = useLang()
  const pos = useMemo(() => cityPosition(city), [city])
  const baseScale = city.hub ? 1 : 0.55

  useFrame((state) => {
    const tm = state.clock.elapsedTime
    const pulse = 1 + Math.sin(tm * 2.2 + pos[0]) * 0.08
    const target = hovered ? 1.7 : 1
    const s = THREE.MathUtils.lerp(ringRef.current.scale.x, baseScale * pulse * target, 0.12)
    ringRef.current.scale.setScalar(s)
    ringRef.current.rotation.z = tm * (city.hub ? 0.4 : 0.2)
    coreRef.current.material.emissiveIntensity = THREE.MathUtils.lerp(
      coreRef.current.material.emissiveIntensity,
      hovered ? 3.2 : city.hub ? 1.6 : 0.9,
      0.1
    )
  })

  const onOver = (e) => {
    e.stopPropagation()
    setHovered(true)
    sceneState.focusCity = city
    // cinematic zoom: dolly toward the node, slightly off-axis for parallax
    sceneState.cameraTarget.set(pos[0] * 0.75, pos[1] * 0.75 - 0.25, 4.4)
    sceneState.lookTarget.set(pos[0], pos[1], 0)
    document.body.style.cursor = 'pointer'
  }

  const onOut = () => {
    setHovered(false)
    if (sceneState.focusCity?.id === city.id) {
      sceneState.focusCity = null
      sceneState.cameraTarget.copy(HOME_CAMERA)
      sceneState.lookTarget.copy(HOME_LOOK)
    }
    document.body.style.cursor = 'auto'
  }

  return (
    <group position={pos}>
      {/* generous invisible hit target */}
      <mesh onPointerOver={onOver} onPointerOut={onOut} visible={false}>
        <sphereGeometry args={[city.hub ? 0.42 : 0.3, 8, 8]} />
      </mesh>

      <mesh ref={coreRef}>
        <sphereGeometry args={[city.hub ? 0.055 : 0.035, 16, 16]} />
        <meshStandardMaterial
          color="#f0dcae"
          emissive="#c9a96a"
          emissiveIntensity={city.hub ? 1.6 : 0.9}
          toneMapped={false}
        />
      </mesh>

      <mesh ref={ringRef}>
        <ringGeometry args={[0.13, 0.14, 48]} />
        <meshBasicMaterial
          color={city.hub ? '#c9a96a' : '#6b7690'}
          transparent
          opacity={city.hub ? 0.8 : 0.5}
          side={THREE.DoubleSide}
        />
      </mesh>

      <Html center distanceFactor={9} zIndexRange={[20, 0]} style={{ pointerEvents: 'none' }}>
        <div
          className="select-none text-center transition-all duration-500"
          style={{ transform: `translateY(${city.hub ? 26 : 20}px)`, opacity: hovered ? 0 : 1 }}
        >
          <span className={`whitespace-nowrap font-body uppercase tracking-[0.3em] ${city.hub ? 'text-[11px] text-gold/90' : 'text-[9px] text-mist/70'}`}>
            {cityLabel(city, lang)}
          </span>
        </div>
      </Html>

      {hovered && (
        <Html center distanceFactor={7.5} zIndexRange={[40, 30]} style={{ pointerEvents: 'none' }}>
          <div className="glass-strong w-56 -translate-y-24 rounded-xl px-5 py-4 text-left">
            <p className="font-display text-lg leading-tight text-gold-bright">
              {cityLabel(city, lang)}
              <span className="ml-2 font-body text-[9px] uppercase tracking-[0.25em] text-mist">
                {lang === 'en' ? city.zh : city.en}
              </span>
            </p>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="font-body text-[9px] uppercase tracking-[0.2em] text-mist">{t('cityCard.gdp')}</span>
              <span className="font-display text-xl text-platinum">US${city.gdp}B</span>
            </div>
            <p className="mt-1.5 border-t border-gold/15 pt-1.5 font-body text-[10px] leading-relaxed text-mist">
              <span className="text-gold/70">{t('cityCard.tech')} — </span>
              {cityTech(city, lang)}
            </p>
          </div>
        </Html>
      )}
    </group>
  )
}

/* ------------------------------------------------------------------ */
/*  Camera rig — eases toward the shared target every frame            */
/* ------------------------------------------------------------------ */

function CameraRig() {
  const look = useRef(new THREE.Vector3(0, 0, 0))
  useFrame((state) => {
    const cam = state.camera
    const drift = sceneState.focusCity ? 0.06 : 0.35
    const target = sceneState.cameraTarget
    cam.position.x = THREE.MathUtils.lerp(cam.position.x, target.x + sceneState.pointerSmooth.x * drift, 0.045)
    cam.position.y = THREE.MathUtils.lerp(cam.position.y, target.y + sceneState.pointerSmooth.y * drift * 0.6, 0.045)
    cam.position.z = THREE.MathUtils.lerp(cam.position.z, target.z + sceneState.heroProgress * 2.2, 0.05)
    look.current.lerp(sceneState.lookTarget, 0.05)
    cam.lookAt(look.current)
  })
  return null
}

/* ------------------------------------------------------------------ */

export default function GBANexus({ isMobile }) {
  const groupRef = useRef()

  useFrame((state) => {
    // gentle plane tilt for depth; recedes as user scrolls away
    const g = groupRef.current
    g.rotation.x = THREE.MathUtils.lerp(g.rotation.x, -0.32 + sceneState.pointerSmooth.y * 0.05, 0.04)
    g.rotation.z = THREE.MathUtils.lerp(g.rotation.z, sceneState.pointerSmooth.x * 0.03, 0.04)
    g.position.y = THREE.MathUtils.lerp(g.position.y, -0.3 - sceneState.heroProgress * 2.6, 0.08)
    const s = 1 - sceneState.heroProgress * 0.15
    g.scale.setScalar(s)
    g.visible = sceneState.heroProgress < 0.98
    void state
  })

  return (
    <group ref={groupRef} position={[0, -0.3, 0]} rotation={[-0.32, 0, 0]}>
      <NexusPoints count={isMobile ? 2600 : 6500} />
      <Corridors />
      {CITIES.map((city) => (
        <CityNode key={city.id} city={city} />
      ))}
      <CameraRig />
    </group>
  )
}
