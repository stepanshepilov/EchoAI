// src/components/CameraController.tsx
import { useThree, useFrame } from '@react-three/fiber';
import { Vector3 } from 'three';
import { useRef, useEffect } from 'react';

interface Props {
  focusTarget: Vector3 | null;
}

export function CameraController({ focusTarget }: Props) {
  const { camera } = useThree();
  const defaultPos = new Vector3(0, 3, 8);
  const targetPos = useRef<Vector3>(defaultPos.clone());

  useEffect(() => {
    if (focusTarget) {
      targetPos.current = focusTarget.clone();
    } else {
      targetPos.current = defaultPos.clone();
    }
  }, [focusTarget]);

  useFrame(() => {
    camera.position.lerp(targetPos.current, 0.1);
    if (focusTarget) {
      camera.lookAt(focusTarget);
    } else {
      camera.lookAt(0, 1.5, 0);
    }
  });

  return null;
}