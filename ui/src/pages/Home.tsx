import { useEffect, useMemo, useRef, useState } from 'react';
import * as THREE from 'three';
import styled, { keyframes } from 'styled-components';
import { Canvas } from '@react-three/fiber';
import { useNavigate } from 'react-router-dom';
import { AvatarModel } from '../components/AvatarModel';
import { CameraController } from '../components/CameraController';
import { EmployeeCard, Employee } from '../components/EmployeeCard';
import { EmployeeSelector } from '../components/EmployeeSelector';

const employeesMock: Employee[] = [
  { id: '001', name: 'Иванов И.', risk: 0.1 },
  { id: '002', name: 'Петрова А.', risk: 0.35 },
  { id: '003', name: 'Сидоров К.', risk: 0.52 },
  { id: '004', name: 'Кузнецова М.', risk: 0.76 },
  { id: '005', name: 'Васильев П.', risk: 0.91 },
];

export default function Home() {
  const navigate = useNavigate();

  const [employees, setEmployees] = useState<Employee[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectorVisible, setSelectorVisible] = useState(false);
  const [focusTarget, setFocusTarget] = useState<THREE.Vector3 | null>(null);
  const [modelCenter, setModelCenter] = useState<THREE.Vector3 | null>(null);
  const [teamMood, setTeamMood] = useState<null | ReturnType<typeof calcTeamMood>>(null);
  const [justFocused, setJustFocused] = useState(false);
  const focusTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const selectedEmployee = useMemo(
    () => employees.find(e => e.id === selectedId),
    [selectedId, employees]
  );

  useEffect(() => setEmployees(employeesMock), []);

  const handleAvatarClick = () => {
    if (modelCenter) {
      const adjusted = modelCenter.clone();
      adjusted.y += 1.2;
      adjusted.z += 3.2;
      setFocusTarget(adjusted);
      setJustFocused(true);

      if (focusTimeoutRef.current) clearTimeout(focusTimeoutRef.current);
      focusTimeoutRef.current = setTimeout(() => setJustFocused(false), 700);
      setTimeout(() => setSelectorVisible(true), 600);
    }
  };

  const handlePointerMissed = () => {
    if (justFocused) return;
    setFocusTarget(null);
    setSelectedId(null);
    setSelectorVisible(false);
  };

  const handleSelect = (id: string) => {
    setSelectedId(id);
    setSelectorVisible(false);
    const emp = employees.find((e) => e.id === id);
    if (emp) playBellSound(emp.risk);
  };

  const playBellSound = (risk: number) => {
    const bin = 5 - Math.min(4, Math.floor(risk * 5));
    const audio = new Audio(`/sounds/bell${bin}.mp3`);
    audio.play().catch((e) => console.warn('Звук не проигрался:', e));
  };

  const modelColor = useMemo(() => {
    if (!selectedEmployee) return new THREE.Color('#ccc');
    return new THREE.Color().lerpColors(
      new THREE.Color('#2ecc71'),
      new THREE.Color('#e74c3c'),
      selectedEmployee.risk
    );
  }, [selectedEmployee]);

  const calcTeamMood = (team: Employee[]) => {
    const avg = team.reduce((s, e) => s + e.risk, 0) / team.length;
    if (avg < 0.35)
      return { color: '#2ecc71', msg: 'Команда в хорошем настроении 🌿', file: 'calm.mp3', risk: avg };
    if (avg < 0.7)
      return { color: '#f1c40f', msg: 'Есть признаки стресса 🟡', file: 'medium.mp3', risk: avg };
    return { color: '#e74c3c', msg: 'Команда под серьёзным давлением ❗️', file: 'tense.mp3', risk: avg };
  };

  const playTeamMoodMelody = () => {
    const mood = calcTeamMood(employees);
    setTeamMood(mood);
    const audio = new Audio(`/music/${mood.file}`);
    audio.play().catch(console.warn);
    setTimeout(() => setTeamMood(null), 12000);
  };

  return (
    <AppWrapper>
      <Logo>EchoAI</Logo>
      <NavBtn onClick={() => navigate('/dashboard')}>
        📊 Перейти в дашборд
      </NavBtn>

      <CanvasContainer>
        <Canvas
          camera={{ position: [0, 3, 8], fov: 45 }}
          onPointerMissed={handlePointerMissed}
        >
          <ambientLight intensity={0.6} />
          <pointLight position={[5, 10, 5]} intensity={1.4} />
          <CameraController focusTarget={focusTarget} />
          <AvatarModel
            color={modelColor}
            onClick={handleAvatarClick}
            onCenterComputed={(center) => setModelCenter(center)}
          />
        </Canvas>
      </CanvasContainer>

      {selectorVisible && (
        <Modal visible={selectorVisible}>
        <h3 style={{ color: '#222' }}>Выбери сотрудника:</h3>
        <EmployeeSelector employees={employees} onSelect={handleSelect} />
      </Modal>
    )}

      {selectedEmployee && !selectorVisible && (
        <RightPanel visible={selectedEmployee && !selectorVisible}>
        {selectedEmployee && <EmployeeCard employee={selectedEmployee} />}
      </RightPanel>
      )}

      <PlayButton onClick={playTeamMoodMelody}>🎶 Мелодия команды</PlayButton>

      {teamMood && (
        <MoodBanner style={{ backgroundColor: teamMood.color }}>
          <h3>{teamMood.msg}</h3>
          <p>Средний риск: <strong>{Math.round(teamMood.risk * 100)}%</strong></p>
        </MoodBanner>
      )}
    </AppWrapper>
  );
}

const AppWrapper = styled.div`
  width: 100vw;
  height: 100vh;
  position: relative;
  background-color: #fff;
  font-family: 'Segoe UI', sans-serif;
`;

const Logo = styled.h1`
  position: absolute;
  top: 24px;
  left: 30px;
  font-size: 24px;
  font-weight: 600;
  color: #222;
  z-index: 10;
`;

const NavBtn = styled.button`
  position: absolute;
  top: 24px;
  right: 30px;
  z-index: 10;
  background: #2c3e50;
  color: white;
  padding: 10px 16px;
  border-radius: 8px;
  border: none;
  font-size: 15px;
  cursor: pointer;
  transition: background-color 0.2s ease;
  &:hover {
    background: #34495e;
  }
`;

const CanvasContainer = styled.div`
  position: absolute;
  top: 0; left: 0;
  width: 100%;
  height: 100%;
  z-index: 1;
  transition: all 0.5s ease;
`;

const fadeIn = keyframes`
  from { opacity: 0; transform: translateY(20px); }
  to { opacity: 1; transform: translateY(0); }
`;

const Modal = styled.div<{ visible: boolean }>`
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  background: white;
  padding: 30px;
  border-radius: 14px;
  box-shadow: 0 10px 30px rgba(0,0,0,0.25);
  z-index: 5;

  opacity: ${({ visible }) => (visible ? 1 : 0)};
  visibility: ${({ visible }) => (visible ? 'visible' : 'hidden')};
  transform: translate(-50%, -50%) scale(${({ visible }) => (visible ? 1 : 0.95)});
  transition: opacity 0.4s ease, transform 0.4s ease;
`;

const RightPanel = styled.div<{ visible: boolean }>`
  position: absolute;
  top: 90px;
  right: 40px;
  z-index: 10;

  opacity: ${({ visible }) => (visible ? 1 : 0)};
  transform: translateX(${({ visible }) => (visible ? '0' : '20px')});
  transition: opacity 0.4s ease, transform 0.4s ease;
`;

const PlayButton = styled.button`
  position: absolute;
  bottom: 30px;
  left: 30px;
  z-index: 10;
  padding: 12px 20px;
  border-radius: 10px;
  border: none;
  background: #444;
  color: white;
  font-size: 16px;
  cursor: pointer;
  transition: background 0.2s;
  &:hover {
    background: #333;
  }
`;

const MoodBanner = styled.div`
  position: fixed;
  bottom: 30px;
  left: 50%;
  transform: translateX(-50%);
  padding: 18px 24px;
  border-radius: 16px;
  color: white;
  text-align: center;
  animation: ${fadeIn} 0.5s ease-out;
  font-size: 16px;
  box-shadow: 0 10px 30px rgba(0,0,0,0.25);
  z-index: 20;
`;