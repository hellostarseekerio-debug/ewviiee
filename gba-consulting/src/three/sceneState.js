import * as THREE from 'three'

/**
 * Shared mutable scene state, written by React handlers / scroll listeners
 * and consumed inside useFrame loops without triggering re-renders.
 */
export const sceneState = {
  pointer: new THREE.Vector2(0, 0),      // normalised -1..1
  pointerSmooth: new THREE.Vector2(0, 0),
  scroll: 0,                             // 0..1 page progress
  heroProgress: 0,                       // 0..1 progress through hero viewport
  focusCity: null,                       // city object under cursor, or null
  cameraTarget: new THREE.Vector3(0, 0, 9.5),
  lookTarget: new THREE.Vector3(0, 0, 0),
}

export const HOME_CAMERA = new THREE.Vector3(0, 0, 9.5)
export const HOME_LOOK = new THREE.Vector3(0, 0, 0)
