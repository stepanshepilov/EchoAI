import { useEffect, useMemo, useRef, useState } from 'react';
import * as THREE from 'three';
import styled, { keyframes } from 'styled-components';
import { Canvas } from '@react-three/fiber';
import { useNavigate } from 'react-router-dom';
import { AvatarModel } from '../components/AvatarModel';
import { CameraController } from '../components/CameraController';
import { EmployeeCard } from '../components/EmployeeCard';
import { EmployeeSelector } from '../components/EmployeeSelector';
import { getTeamPulse } from '../services/api';
import { useWebSocket } from '../hooks/useWebSocket';
import * as Tone from 'tone';

export interface Employee {
  id: string;
  token: string;
  name: string;
  risk: number;
}

const StatusScreen = styled.div`
  display: flex;
  justify-content: center;
  align-items: center;
  width: 100vw;
  height: 100vh;
  font-family: 'Segoe UI', sans-serif;
  font-size: 24px;
  color: #555;
  background-color: #fff;
`;

export default function Home() {
  const navigate = useNavigate();

  const [employees, setEmployees] = useState<Employee[]>([]);
  const [selectedToken, setSelectedToken] = useState<string | null>(null);
  const [isSessionActive, setIsSessionActive] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [selectorVisible, setSelectorVisible] = useState(false);
  const [teamMood, setTeamMood] = useState<null | ReturnType<typeof calcTeamMood>>(null);

  const [isZoomedIn, setIsZoomedIn] = useState(false);
  const cameraInitializedRef = useRef(false);

  const selectedEmployee = useMemo(
    () => employees.find((e) => e.token === selectedToken),
    [selectedToken, employees]
  );

  useEffect(() => {
    const fetchTeamData = async () => {
      try {
        setIsLoading(true);
        const data = await getTeamPulse();
        const formattedEmployees: Employee[] = data.employees.map((emp, index) => ({
          id: emp.token,
          token: emp.token,
          risk: emp.risk_probability,
          name: `Сотрудник #${index + 1}`,
        }));
        setEmployees(formattedEmployees);
        setError(null);
      } catch (e: any) {
        setError(e.message || 'Не удалось загрузить данные о команде.');
      } finally {
        setIsLoading(false);
      }
    };
    fetchTeamData();
  }, []);

  useWebSocket('ws://localhost:8000/api/v1/ws/dashboard', {
    onOpen: () => setIsSessionActive(true),
    onClose: () => setIsSessionActive(false),
    onMessage: (data) => {
      if (data.event_type === 'EMPLOYEE_RISK_UPDATED') {
        const { token, new_risk_probability } = data.payload;
        setEmployees((prev) =>
          prev.map((emp) =>
            emp.token === token ? { ...emp, risk: new_risk_probability } : emp
          )
        );
      }
    },
    onError: () => setIsSessionActive(false),
  });

  const handleAvatarClick = () => {
    if (!cameraInitializedRef.current) return;
    setIsZoomedIn(true);
    setSelectorVisible(true);
  };

  const handlePointerMissed = () => {
    setSelectorVisible(false);
    setSelectedToken(null);
    setIsZoomedIn(false);
  };

  const handleSelect = (token: string) => {
    setSelectedToken(token);
    setSelectorVisible(false);
    const emp = employees.find((e) => e.token === token);
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
    if (team.length === 0) {
      return {
        color: '#ccc',
        msg: 'Нет данных о команде',
        file: 'calm.mp3',
        risk: 0,
      };
    }

    const avg = team.reduce((s, e) => s + e.risk, 0) / team.length;

    if (avg < 0.35)
      return { color: '#2ecc71', msg: 'Команда в хорошем настроении 🌿', file: 'calm.mp3', risk: avg };
    if (avg < 0.7)
      return { color: '#f1c40f', msg: 'Есть признаки стресса 🟡', file: 'medium.mp3', risk: avg };
    return { color: '#e74c3c', msg: 'Команда под серьёзным давлением ❗️', file: 'tense.mp3', risk: avg };
  };

  const playTeamMoodMelody = async () => {
    const mood = calcTeamMood(employees);
    setTeamMood(mood);

    await Tone.start();

    const minFreq = 130;
    const maxFreq = 700;
    const freq = minFreq + (maxFreq - minFreq) * mood.risk;

    const synth = new Tone.Synth({
      oscillator: {
        type: 'sine',
      },
      envelope: {
        attack: 2,
        decay: 1.5,
        sustain: 0.7,
        release: 4,
      },
    });

    // 🎛 Реверберация
    const reverb = new Tone.Reverb({
      decay: 5,
      wet: 0.7,
    }).toDestination();

    await reverb.generate(); // ждать генерации reverb

    synth.connect(reverb);

    // 🎹 Воспроизводим звук
    synth.triggerAttackRelease(freq, '8n');

    // ⏱ Убрать баннер чуть позже окончания звучания
    setTimeout(() => setTeamMood(null), 6000);
  };

  if (isLoading) return <StatusScreen>Загрузка данных...</StatusScreen>;
  if (error) return <StatusScreen>Ошибка: {error}</StatusScreen>;

  return (
    <AppWrapper>
      <Logo>EchoAI</Logo>
      <NavBtn onClick={() => navigate('/dashboard')}>📊 Перейти в дашборд</NavBtn>

      <CanvasContainer>
        <Canvas shadows camera={{ position: [0, 3, 8], fov: 45 }} onPointerMissed={handlePointerMissed}>
          <ambientLight intensity={0.4} />
          <directionalLight
            castShadow
            position={[5, 10, 5]}
            intensity={0.8}
            shadow-mapSize-width={1024}
            shadow-mapSize-height={1024}
          />

          <CameraController zoomIn={isZoomedIn} />

          {/* model */}
          <AvatarModel
            color={modelColor}
            onClick={handleAvatarClick}
            onCenterComputed={() => {
              cameraInitializedRef.current = true;
            }}
            isSessionActive={isSessionActive}
          />

          {/* пол */}
          <mesh receiveShadow rotation={[-Math.PI / 2, 0, 0]} position={[0, 0, 0]}>
            <planeGeometry args={[30, 30]} />
            <shadowMaterial opacity={0.2} />
          </mesh>
        </Canvas>
      </CanvasContainer>

      {selectorVisible && (
        <Modal visible={selectorVisible}>
          <h3 style={{ color: '#222' }}>Выбери сотрудника:</h3>
          <EmployeeSelector employees={employees} onSelect={handleSelect} />
        </Modal>
      )}

      {selectedEmployee && !selectorVisible && (
        <RightPanel visible={!!selectedEmployee && !selectorVisible}>
          <EmployeeCard
            employee={selectedEmployee}
            onDetailsClick={() =>
              navigate(`/dashboard/employee/${selectedEmployee.token}`)
            }
          />
        </RightPanel>
      )}

      <PlayButton onClick={playTeamMoodMelody}>🎶 Мелодия команды</PlayButton>

      {teamMood && (
        <MoodBanner style={{ backgroundColor: teamMood.color }}>
          <h3>{teamMood.msg}</h3>
          <p>
            Средний риск: <strong>{Math.round(teamMood.risk * 100)}%</strong>
          </p>
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
  top: 0;
  left: 0;
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
  top: 56%;
  left: 68%;
  transform: translate(-50%, -50%);
  background: white;
  padding: 30px;
  border-radius: 14px;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.25);
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
  left: 0;
  right: 0;
  margin: 0 auto;
  width: fit-content;

  padding: 18px 24px;
  border-radius: 16px;
  color: white;
  text-align: center;
  font-size: 16px;
  z-index: 20;

  background: #000; // будет переопределяться через style={{ backgroundColor }}
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.25);
  animation: ${fadeIn} 0.5s ease-out;
`;