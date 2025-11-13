// src/components/AvatarModel.tsx
import { useGLTF } from '@react-three/drei';
import * as THREE from 'three';
import { useMemo } from 'react';

interface Props {
  color: THREE.Color;
  onCenterComputed?: (center: THREE.Vector3) => void;
  onClick?: () => void;
}

export function AvatarModel({ color, onCenterComputed, onClick }: Props) {
  const { scene } = useGLTF('/people-optimized.glb');

  const model = useMemo(() => {
    const cloned = scene.clone(true);

    cloned.traverse((child) => {
      if ((child as THREE.Mesh).isMesh) {
        const mesh = child as THREE.Mesh;
        mesh.material = new THREE.MeshStandardMaterial({
          color,
          roughness: 0.5,
          metalness: 0.1,
        });
      }
    });

    const box = new THREE.Box3().setFromObject(cloned);
    const center = new THREE.Vector3();
    box.getCenter(center);

    onCenterComputed?.(center);

    const size = new THREE.Vector3();
    box.getSize(size);
    cloned.position.sub(center);

    const scale = 2 / Math.max(size.x, size.y, size.z);
    cloned.scale.setScalar(scale);

    return cloned;
  }, [scene, color]);

  return (
    <group onPointerDown={onClick}> {/* ✅ тут ловим клик */}
      <primitive object={model} />
    </group>
  );
}

useGLTF.preload('/people-optimized.glb');