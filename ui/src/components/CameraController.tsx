import { useFrame, useThree } from '@react-three/fiber';

type Props = {
  zoomIn: boolean;
};

export const CameraController = ({ zoomIn }: Props) => {
  const { camera } = useThree();

  const target = {
    y: zoomIn ? 2.5 : 3,
    z: zoomIn ? 3.5 : 8
  };

  const speed = 0.08;

  useFrame(() => {
    if (Math.abs(camera.position.z - target.z) > 0.01) {
      camera.position.z += (target.z - camera.position.z) * speed;
    } else {
      camera.position.z = target.z;
    }

    if (Math.abs(camera.position.y - target.y) > 0.01) {
      camera.position.y += (target.y - camera.position.y) * speed;
    } else {
      camera.position.y = target.y;
    }
  });

  return null;
};