import { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';

/**
 * Пульсирующий цвет между базовым цветом и его осветлённой версией.
 */
export const usePulsingColor = (baseColor: THREE.Color) => {
  const [color, setColor] = useState<THREE.Color>(baseColor.clone());
  const directionRef = useRef(1);
  const intensityRef = useRef(0);
  const animationRef = useRef<number | null>(null);

  useEffect(() => {
    const lighterColor = baseColor.clone().lerp(new THREE.Color(1, 1, 1), 0.3); // Осветляем цвет

    const animate = () => {
      intensityRef.current += directionRef.current * 0.015;

      if (intensityRef.current >= 1) {
        intensityRef.current = 1;
        directionRef.current = -1;
      } else if (intensityRef.current <= 0) {
        intensityRef.current = 0;
        directionRef.current = 1;
      }

      const interpolated = baseColor.clone().lerp(lighterColor, intensityRef.current);
      setColor(interpolated);

      animationRef.current = requestAnimationFrame(animate);
    };

    if (animationRef.current) cancelAnimationFrame(animationRef.current);
    intensityRef.current = 0;
    directionRef.current = 1;

    animationRef.current = requestAnimationFrame(animate);

    return () => {
      if (animationRef.current) cancelAnimationFrame(animationRef.current);
    };
  }, [baseColor]);

  return color;
};