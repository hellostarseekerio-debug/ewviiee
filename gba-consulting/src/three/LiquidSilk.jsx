import { useMemo, useRef } from 'react'
import { useFrame, useThree } from '@react-three/fiber'
import * as THREE from 'three'
import { sceneState } from './sceneState'

/**
 * "Digital Silk" — a fullscreen custom-GLSL backdrop.
 * Raymarch-style layered FBM with derivative-based normals produces a
 * liquid-metal sheen in obsidian + champagne gold that flows toward the cursor.
 */
const vertexShader = /* glsl */ `
  varying vec2 vUv;
  void main() {
    vUv = uv;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`

const fragmentShader = /* glsl */ `
  precision highp float;

  uniform float uTime;
  uniform vec2  uMouse;
  uniform vec2  uRes;
  uniform float uScroll;
  varying vec2  vUv;

  mat2 rot(float a) { float c = cos(a), s = sin(a); return mat2(c, -s, s, c); }

  float hash(vec2 p) {
    p = fract(p * vec2(234.34, 435.345));
    p += dot(p, p + 34.23);
    return fract(p.x * p.y);
  }

  float noise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    vec2 u = f * f * (3.0 - 2.0 * f);
    return mix(
      mix(hash(i), hash(i + vec2(1.0, 0.0)), u.x),
      mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), u.x),
      u.y
    );
  }

  float fbm(vec2 p) {
    float v = 0.0;
    float a = 0.55;
    for (int i = 0; i < 5; i++) {
      v += a * noise(p);
      p = rot(0.62) * p * 2.03 + vec2(11.7, 5.3);
      a *= 0.5;
    }
    return v;
  }

  // Silk height field: domain-warped fbm, dragged by time and by the cursor.
  float silk(vec2 p, float t) {
    vec2 toMouse = p - uMouse * vec2(1.4, 0.9);
    float pull = exp(-dot(toMouse, toMouse) * 1.6);
    vec2 warp = vec2(
      fbm(p * 1.4 + vec2(t * 0.06, -t * 0.04)),
      fbm(p * 1.4 + vec2(-t * 0.05, t * 0.07) + 7.3)
    );
    p += (warp - 0.5) * 1.35 + toMouse * pull * -0.35;
    float ridges = fbm(p * 2.2 + vec2(0.0, t * 0.05));
    return ridges + pull * 0.22;
  }

  void main() {
    vec2 uv = (vUv - 0.5) * vec2(uRes.x / uRes.y, 1.0) * 2.0;
    float t = uTime;

    float h = silk(uv, t);

    // Screen-space derivatives -> pseudo surface normal for the metal sheen
    float e = 0.012;
    float hx = silk(uv + vec2(e, 0.0), t) - h;
    float hy = silk(uv + vec2(0.0, e), t) - h;
    vec3 n = normalize(vec3(-hx / e, -hy / e, 2.6));

    vec3 lightDir = normalize(vec3(uMouse * 0.6 + vec2(0.3, 0.55), 0.9));
    float diff = clamp(dot(n, lightDir), 0.0, 1.0);
    float specular = pow(clamp(dot(reflect(-lightDir, n), vec3(0.0, 0.0, 1.0)), 0.0, 1.0), 24.0);

    // Palette: obsidian depths -> steel platinum -> champagne gold sheen
    vec3 obsidian = vec3(0.010, 0.013, 0.024);
    vec3 steel    = vec3(0.055, 0.063, 0.088);
    vec3 gold     = vec3(0.79, 0.66, 0.42);

    vec3 col = mix(obsidian, steel, smoothstep(0.25, 1.05, h) * diff);
    col += gold * specular * 0.38;
    col += gold * pow(h, 3.5) * 0.10;

    // Fine woven-silk threads
    float thread = sin((uv.y + h * 1.8) * 240.0) * 0.5 + 0.5;
    col *= 0.94 + 0.06 * thread;

    // Sink to black as the user scrolls into the narrative sections
    col *= 1.0 - uScroll * 0.85;

    // Corner vignette
    float vig = smoothstep(1.9, 0.45, length(uv));
    col *= 0.35 + 0.65 * vig;

    gl_FragColor = vec4(col, 1.0);
  }
`

export default function LiquidSilk() {
  const matRef = useRef()
  const { viewport } = useThree()

  const uniforms = useMemo(
    () => ({
      uTime: { value: 0 },
      uMouse: { value: new THREE.Vector2(0, 0) },
      uRes: { value: new THREE.Vector2(1, 1) },
      uScroll: { value: 0 },
    }),
    []
  )

  useFrame((state) => {
    const u = matRef.current.uniforms
    u.uTime.value = state.clock.elapsedTime
    u.uMouse.value.lerp(sceneState.pointer, 0.05)
    u.uRes.value.set(state.size.width, state.size.height)
    u.uScroll.value = sceneState.heroProgress
  })

  return (
    <mesh position={[0, 0, -6]} scale={[viewport.width * 2.6, viewport.height * 2.6, 1]}>
      <planeGeometry args={[1, 1]} />
      <shaderMaterial
        ref={matRef}
        vertexShader={vertexShader}
        fragmentShader={fragmentShader}
        uniforms={uniforms}
        depthWrite={false}
      />
    </mesh>
  )
}
