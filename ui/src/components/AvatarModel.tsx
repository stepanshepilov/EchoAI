// src/components/AvatarModel.tsx

import { useGLTF } from '@react-three/drei';
import * as THREE from 'three';
import { useEffect, useRef } from 'react';
import { useFrame } from '@react-three/fiber';

interface Props {
  color: THREE.Color;
  onCenterComputed?: (center: THREE.Vector3) => void;
  onClick?: () => void;
  isSessionActive: boolean; // Проп для управления WebSocket анимацией
}

export function AvatarModel({ color, onCenterComputed, onClick, isSessionActive }: Props) {
  const { scene } = useGLTF('/people-optimized.glb');
  const groupRef = useRef<THREE.Group>(null!);
  
  // Исправлено: инициализируем ref с null, чтобы TypeScript был доволен
  const materialRef = useRef<THREE.MeshStandardMaterial | null>(null);

  // Этот useEffect выполняется один раз для начальной настройки модели
  useEffect(() => {
    // Не запускать код, если модель уже добавлена
    if (groupRef.current.children.length > 0) return;

    const model = scene.clone(true);
    
    model.traverse((child) => {
      if ((child as THREE.Mesh).isMesh) {
        const mesh = child as THREE.Mesh;
        // Создаем материал один раз и сохраняем ссылку на него
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
    
    // Вызываем колбэк с центром модели
    onCenterComputed?.(center.clone());

    const size = new THREE.Vector3();
    box.getSize(size);
    // Центрируем и масштабируем модель
    model.position.sub(center);
    const scale = 2 / Math.max(size.x, size.y, size.z);
    model.scale.setScalar(scale);

    // Добавляем готовую модель в ref группы
    groupRef.current.add(model);
    
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scene, onCenterComputed]);
  
  // Этот хук выполняется на каждом кадре для анимации
  useFrame((state, delta) => {
    if (!materialRef.current || !groupRef.current) return;

    const material = materialRef.current;
    
    if (isSessionActive) {
      // --- Анимация активной сессии (WebSocket подключен) ---
      const activeColor = new THREE.Color('#3498db'); // Синий цвет
      
      // Плавный переход к синему цвету
      material.color.lerp(activeColor, delta * 5);
      
      // Эффект свечения
      material.emissive.set(activeColor);
      material.emissiveIntensity = Math.sin(state.clock.elapsedTime * 5) * 0.5 + 0.6;
      
      // Эффект легкой вибрации/покачивания
      groupRef.current.rotation.y += Math.sin(state.clock.elapsedTime * 0.5) * 0.0005;
      groupRef.current.position.y = Math.sin(state.clock.elapsedTime * 15) * 0.005;

    } else {
      // --- Возврат в обычное состояние ---

      // Плавный переход к цвету риска сотрудника (или серому)
      material.color.lerp(color, delta * 5);
      
      // Плавно убираем свечение
      if (material.emissiveIntensity > 0) {
        material.emissiveIntensity = THREE.MathUtils.lerp(material.emissiveIntensity, 0, delta * 10);
      }
      
      // Плавно возвращаем модель в исходное положение
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