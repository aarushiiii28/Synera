import React, { useMemo, useRef, useState, useEffect } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { Sphere } from '@react-three/drei';
import * as THREE from 'three';
import { geoEquirectangular, geoPath } from 'd3';

function GlobePoints() {
  const [points, setPoints] = useState<THREE.Vector3[]>([]);
  const meshRef = useRef<THREE.InstancedMesh>(null);
  
  useEffect(() => {
    fetch('/land.geojson')
      .then(res => res.json())
      .then(data => {
        // Simple rejection sampling to get points in polygons
        const pts: THREE.Vector3[] = [];
        const canvas = document.createElement('canvas');
        canvas.width = 1024;
        canvas.height = 512;
        const ctx = canvas.getContext('2d')!;
        
        const projection = geoEquirectangular()
          .translate([512, 256])
          .scale(1024 / (2 * Math.PI));
          
        const path = geoPath(projection, ctx);
        
        ctx.fillStyle = '#fff';
        ctx.beginPath();
        path(data);
        ctx.fill();
        
        const imgData = ctx.getImageData(0, 0, 1024, 512).data;
        
        const R = 1.01;
        const count = 9000;
        let added = 0;
        let attempts = 0;
        
        while(added < count && attempts < 100000) {
          attempts++;
          const phi = Math.acos(2 * Math.random() - 1);
          const theta = 2 * Math.PI * Math.random();
          
          const u = theta / (2 * Math.PI);
          const v = phi / Math.PI;
          
          const x = Math.floor(u * 1024);
          const y = Math.floor(v * 512);
          
          if (imgData[(y * 1024 + x) * 4] > 128) {
            pts.push(new THREE.Vector3(
              R * Math.sin(phi) * Math.cos(theta),
              R * Math.cos(phi),
              -R * Math.sin(phi) * Math.sin(theta)
            ));
            added++;
          }
        }
        setPoints(pts);
      });
  }, []);

  const dummy = useMemo(() => new THREE.Object3D(), []);

  useEffect(() => {
    if (meshRef.current && points.length > 0) {
      points.forEach((p, i) => {
        dummy.position.copy(p);
        dummy.lookAt(new THREE.Vector3().copy(p).multiplyScalar(2));
        dummy.updateMatrix();
        meshRef.current!.setMatrixAt(i, dummy.matrix);
      });
      meshRef.current.instanceMatrix.needsUpdate = true;
    }
  }, [points, dummy]);

  if (points.length === 0) return null;

  return (
    <instancedMesh ref={meshRef} args={[undefined, undefined, points.length]}>
      <circleGeometry args={[0.005, 4]} />
      <meshBasicMaterial color="#7F98B2" transparent opacity={0.6} depthWrite={false} side={THREE.DoubleSide} />
    </instancedMesh>
  );
}

function Atmosphere() {
  return (
    <Sphere args={[1.05, 64, 64]}>
      <meshPhysicalMaterial 
        color="#16B5FF"
        transparent 
        opacity={0.1} 
        roughness={1}
        transmission={0.9}
        thickness={0.5}
        side={THREE.BackSide}
      />
    </Sphere>
  );
}

function GlobeGroup() {
  const groupRef = useRef<THREE.Group>(null);
  
  useFrame((state) => {
    if (groupRef.current) {
      groupRef.current.rotation.y = state.clock.elapsedTime * 0.05;
    }
  });

  return (
    <group ref={groupRef} rotation={[0.2, -Math.PI / 2, 0]}>
      {/* Dark Ocean Sphere */}
      <Sphere args={[1, 64, 64]}>
        <meshBasicMaterial color="#050D18" />
      </Sphere>
      
      <Atmosphere />
      <GlobePoints />
      
      {/* Glare */}
      <directionalLight position={[5, 3, -5]} intensity={4} color="#FFB547" />
    </group>
  );
}

export default function Globe() {
  const [isWebGLAvailable] = useState(() => {
    if (typeof window === 'undefined') return true;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return false;
    try {
      const canvas = document.createElement('canvas');
      return !!(window.WebGLRenderingContext && canvas.getContext('webgl'));
    } catch {
      return false;
    }
  });

  if (!isWebGLAvailable) {
    return (
      <div className="w-full h-full rounded-full border border-line bg-void/50 backdrop-blur-sm flex items-center justify-center">
        <span className="font-mono text-xs text-faint">STATIC FALLBACK</span>
      </div>
    );
  }

  return (
    <Canvas 
      camera={{ position: [0, 0, 2.5], fov: 45 }}
      dpr={[1, 1.5]}
      gl={{ antialias: true, alpha: true }}
    >
      <ambientLight intensity={0.5} />
      <GlobeGroup />
    </Canvas>
  );
}
