import { useGLTF } from '@react-three/drei';
import * as THREE from 'three';
import { useEffect, useRef } from 'react';
import { useFrame } from '@react-three/fiber';

interface Props {
  color: THREE.Color;
  onCenterComputed?: (center: THREE.Vector3) => void;
  onClick?: () => void;
  isSessionActive: boolean;
}

export function AvatarModel({ color, onCenterComputed, onClick, isSessionActive }: Props) {
  const { scene } = useGLTF('/people-optimized.glb');
  const groupRef = useRef<THREE.Group>(null!);
  
  const materialRef = useRef<THREE.MeshStandardMaterial | null>(null);

  useEffect(() => {
    if (groupRef.current.children.length > 0) return;

    const model = scene.clone(true);
    
    model.traverse((child) => {
      if ((child as THREE.Mesh).isMesh) {
        const mesh = child as THREE.Mesh;
        materialRef.current = new THREE.MeshStandardMaterial({
          roughness: 0.5,
          metalness: 0.1,
        });
        mesh.material = materialRef.current;
      }
    });

    const box = new THREE.Box3().setFromObject(model);
    const center = new THREE.Vector3();
    box.getCenter(center);
    
    onCenterComputed?.(center.clone());

    const size = new THREE.Vector3();
    box.getSize(size);
    model.position.sub(center);
    const scale = 2 / Math.max(size.x, size.y, size.z);
    model.scale.setScalar(scale);
    groupRef.current.add(model);
  }, [scene, onCenterComputed]);
  
  useFrame((state, delta) => {
    if (!materialRef.current || !groupRef.current) return;

    const material = materialRef.current;
    
    if (isSessionActive) {
      const activeColor = new THREE.Color('#3498db');
      
      material.color.lerp(activeColor, delta * 5);
      
      material.emissive.set(activeColor);
      material.emissiveIntensity = Math.sin(state.clock.elapsedTime * 5) * 0.5 + 0.6;
      
      groupRef.current.rotation.y += Math.sin(state.clock.elapsedTime * 0.5) * 0.0005;
      groupRef.current.position.y = Math.sin(state.clock.elapsedTime * 15) * 0.005;

    } else {
      material.color.lerp(color, delta * 5);

      if (material.emissiveIntensity > 0) {
        material.emissiveIntensity = THREE.MathUtils.lerp(material.emissiveIntensity, 0, delta * 10);
      }
      
      if (Math.abs(groupRef.current.position.y) > 0.0001) {
        groupRef.current.position.y = THREE.MathUtils.lerp(groupRef.current.position.y, 0, delta * 10);
      }
    }
  });

  return (
    <group ref={groupRef} onPointerDown={onClick} />
  );
}

useGLTF.preload('/people-optimized.glb');