import { Suspense, useEffect, useMemo, useRef, useState } from 'react';
import { Canvas, useFrame, useLoader } from '@react-three/fiber';
import { Html } from '@react-three/drei';
import * as THREE from 'three';
import { EarthStatic } from './EarthStatic';

export interface EarthCity { id: string; lat: number; lon: number }

/** Latitude/longitude -> position on a three.js SphereGeometry textured with an equirectangular map. */
export function latLon(lat: number, lon: number, r = 1): THREE.Vector3 {
  const phi = ((lon + 180) / 360) * Math.PI * 2;
  const theta = ((90 - lat) / 180) * Math.PI;
  return new THREE.Vector3(-r * Math.cos(phi) * Math.sin(theta), r * Math.cos(theta), r * Math.sin(phi) * Math.sin(theta));
}

const SUN = new THREE.Vector3(0.2, 0.5, 0.85).normalize();
// The visible sun disc sits just behind the top limb (a sunrise), independent of the light direction.
const GLARE = new THREE.Vector3(0.3, 1.0, -0.7);

const vert = /* glsl */ `
varying vec2 vUv; varying vec3 vN; varying vec3 vV;
void main(){
  vUv = uv;
  vec4 wp = modelMatrix * vec4(position,1.0);
  vN = normalize(mat3(modelMatrix) * normal);
  vV = normalize(cameraPosition - wp.xyz);
  gl_Position = projectionMatrix * viewMatrix * wp;
}`;
const frag = /* glsl */ `
uniform sampler2D dayMap; uniform sampler2D nightMap; uniform vec3 sunDir;
varying vec2 vUv; varying vec3 vN; varying vec3 vV;
void main(){
  vec3 n = normalize(vN);
  float d = dot(n, normalize(sunDir));
  float dayMix = smoothstep(-0.12, 0.28, d);
  vec3 day = texture2D(dayMap, vUv).rgb;
  vec3 night = texture2D(nightMap, vUv).rgb;
  vec3 lit = day * (0.30 + 1.25 * max(d, 0.0));
  vec3 dark = day * 0.035 + night * 2.1;
  vec3 col = mix(dark, lit, dayMix);
  float tw = smoothstep(-0.05, 0.15, d) * (1.0 - smoothstep(0.15, 0.45, d));
  col += vec3(1.0, 0.52, 0.18) * tw * 0.20;
  float fr = pow(1.0 - max(dot(n, normalize(vV)), 0.0), 3.0);
  col += vec3(0.09, 0.45, 1.0) * fr * (0.15 + 0.6 * dayMix) * 0.55;
  gl_FragColor = vec4(col, 1.0);
}`;
const atmVert = /* glsl */ `
varying vec3 vN; varying vec3 vV;
void main(){
  vec4 wp = modelMatrix * vec4(position,1.0);
  vN = normalize(mat3(modelMatrix) * normal);
  vV = normalize(cameraPosition - wp.xyz);
  gl_Position = projectionMatrix * viewMatrix * wp;
}`;
const atmFrag = /* glsl */ `
uniform vec3 sunDir; uniform vec3 glow;
varying vec3 vN; varying vec3 vV;
void main(){
  float t = clamp(-dot(normalize(vN), normalize(vV)), 0.0, 1.0);
  float i = pow(clamp(t / 0.40, 0.0, 1.0), 3.0);
  float s = 0.35 + 0.65 * smoothstep(-0.4, 0.8, dot(normalize(vN), normalize(sunDir)));
  gl_FragColor = vec4(mix(glow, vec3(1.0,0.75,0.45), 0.2*s), 1.0) * i * (0.22 + 0.5*s);
}`;

function Planet({ cities, spin, focusLon, onCity }: { cities: EarthCity[]; spin: number; focusLon: number; onCity?: (id: string) => void }) {
  const group = useRef<THREE.Group>(null);
  const clouds = useRef<THREE.Mesh>(null);
  const [day, night, cloud] = useLoader(THREE.TextureLoader, ['/textures/earth_atmos_2048.jpg', '/textures/earth_lights_2048.png', '/textures/earth_clouds_1024.png']);
  const [hover, setHover] = useState<string | null>(null);
  useMemo(() => { [day, night, cloud].forEach((t) => { t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 4; }); }, [day, night, cloud]);
  const uniforms = useMemo(() => ({ dayMap: { value: day }, nightMap: { value: night }, sunDir: { value: SUN } }), [day, night]);
  const atm = useMemo(() => ({ sunDir: { value: SUN }, glow: { value: new THREE.Color('#16B5FF') } }), []);
  useFrame((_, dt) => {
    if (group.current) group.current.rotation.y += dt * spin;
    if (clouds.current) clouds.current.rotation.y += dt * spin * 0.35;
  });
  const start = -((focusLon + 180) / 360) * Math.PI * 2 - Math.PI / 2;
  return (
    <>
      <group ref={group} rotation={[0.28, start, 0]}>
        <mesh>
          <sphereGeometry args={[1, 96, 96]} />
          <shaderMaterial uniforms={uniforms} vertexShader={vert} fragmentShader={frag} />
        </mesh>
        <mesh ref={clouds} scale={1.012}>
          <sphereGeometry args={[1, 64, 64]} />
          <meshBasicMaterial map={cloud} transparent opacity={0.22} depthWrite={false} />
        </mesh>
        {cities.map((c) => {
          const p = latLon(c.lat, c.lon, 1.012);
          return (
            <group key={c.id} position={p}>
              <mesh onPointerOver={() => setHover(c.id)} onPointerOut={() => setHover(null)} onClick={() => onCity?.(c.id)}>
                <sphereGeometry args={[0.014, 12, 12]} />
                <meshBasicMaterial color="#6FD65B" />
              </mesh>
              <Pulse normal={p} />
              {hover === c.id && (
                <Html center distanceFactor={4} style={{ pointerEvents: 'none' }}>
                  <div className="num text-[10px] tracking-[0.14em] text-biosphere bg-void/90 border border-biosphere/50 px-2 py-0.5 whitespace-nowrap -translate-y-5">{c.id.toUpperCase()}</div>
                </Html>
              )}
            </group>
          );
        })}
      </group>
      <mesh scale={1.085}>
        <sphereGeometry args={[1, 64, 64]} />
        <shaderMaterial uniforms={atm} vertexShader={atmVert} fragmentShader={atmFrag} side={THREE.BackSide} transparent blending={THREE.AdditiveBlending} depthWrite={false} />
      </mesh>
      <SunGlare />
    </>
  );
}

function Pulse({ normal }: { normal: THREE.Vector3 }) {
  const m = useRef<THREE.Mesh>(null);
  useEffect(() => {
    m.current?.quaternion.setFromUnitVectors(new THREE.Vector3(0, 0, 1), normal.clone().normalize());
  }, [normal]);
  useFrame(({ clock }) => {
    if (!m.current) return;
    const k = (clock.elapsedTime * 0.7) % 1;
    m.current.scale.setScalar(1 + k * 2.6);
    (m.current.material as THREE.MeshBasicMaterial).opacity = 0.6 * (1 - k);
  });
  return (
    <mesh ref={m}>
      <ringGeometry args={[0.014, 0.019, 24]} />
      <meshBasicMaterial color="#6FD65B" transparent depthWrite={false} side={THREE.DoubleSide} />
    </mesh>
  );
}

function SunGlare() {
  const tex = useMemo(() => {
    const c = document.createElement('canvas');
    c.width = c.height = 256;
    const g = c.getContext('2d')!;
    const grd = g.createRadialGradient(128, 128, 0, 128, 128, 128);
    grd.addColorStop(0, 'rgba(255,240,210,1)');
    grd.addColorStop(0.12, 'rgba(255,200,130,0.65)');
    grd.addColorStop(0.4, 'rgba(255,150,60,0.16)');
    grd.addColorStop(1, 'rgba(255,120,40,0)');
    g.fillStyle = grd;
    g.fillRect(0, 0, 256, 256);
    return new THREE.CanvasTexture(c);
  }, []);
  return (
    <sprite position={GLARE} scale={[3.2, 3.2, 1]}>
      <spriteMaterial map={tex} transparent blending={THREE.AdditiveBlending} depthWrite={false} opacity={0.9} />
    </sprite>
  );
}

function webglOK(): boolean {
  try {
    const c = document.createElement('canvas');
    return !!(window.WebGLRenderingContext && (c.getContext('webgl') || c.getContext('experimental-webgl')));
  } catch { return false; }
}

export interface EarthProps { cities?: EarthCity[]; spin?: number; focusLon?: number; reduced?: boolean; className?: string; onCity?: (id: string) => void }

/** The SYNERA planet. Lazy-load this module; it pulls in three.js. */
export default function Earth({ cities = [], spin = 0.045, focusLon = 78, reduced = false, className = '', onCity }: EarthProps) {
  const [ok, setOk] = useState(true);
  useEffect(() => setOk(webglOK()), []);
  if (reduced || !ok) return <EarthStatic className={className} />;
  return (
    <div className={className}>
      <Canvas camera={{ position: [0, 0, 4.3], fov: 36 }} dpr={[1, 1.6]} gl={{ antialias: true, alpha: true, powerPreference: 'high-performance' }}>
        <Suspense fallback={null}>
          <Planet cities={cities} spin={spin} focusLon={focusLon} onCity={onCity} />
        </Suspense>
      </Canvas>
    </div>
  );
}

