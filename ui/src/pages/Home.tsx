import { useEffect, useMemo, useRef, useState } from 'react';
import * as THREE from 'three';
import styled, { keyframes, css } from 'styled-components';
import { Canvas } from '@react-three/fiber';
import { useNavigate } from 'react-router-dom';
import { AvatarModel } from '../components/AvatarModel';
import { CameraController } from '../components/CameraController';
import { EmployeeCard } from '../components/EmployeeCard';
import { EmployeeSelector } from '../components/EmployeeSelector';
import { getTeamPulse } from '../services/api';
import * as Tone from 'tone';
import { usePulsingColor } from '../hooks/usePulsingColor';

export interface Employee {
  id: string;
  token: string;
  name: string;
  risk: number;
}

const StatusScreen = styled.div`
  display: flex; justify-content: center; align-items: center;
  width: 100vw; height: 100vh; font-size: 24px; color: #555;
  background-color: #fff; font-family: 'Segoe UI', sans-serif;
`;

export default function Home() {
  const navigate = useNavigate();

  const [employees, setEmployees] = useState<Employee[]>([]);
  const [selectedToken, setSelectedToken] = useState<string | null>(null);
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

  // ✅ ИСПРАВЛЕНО: Создаем новый объект THREE.Color каждый раз при изменении
  const baseColor = useMemo(() => {
    if (selectedEmployee) {
      // Определяем цвет в зависимости от уровня риска
      if (selectedEmployee.risk < 0.35) {
        return new THREE.Color('#2ecc71'); // зеленый - низкий риск
      } else if (selectedEmployee.risk < 0.7) {
        return new THREE.Color('#f1c40f'); // желтый - средний риск
      } else {
        return new THREE.Color('#e74c3c'); // красный - высокий риск
      }
    }
    return new THREE.Color('#0074ff'); // синий по умолчанию
  }, [selectedEmployee?.risk, selectedEmployee?.token]); // ✅ Добавили зависимости для правильного обновления

  // Пульсирующий цвет рассчитывается на основе выбранного сотрудника или дефолта
  const modelColor = usePulsingColor(baseColor);

  useEffect(() => {
    const fetchTeamData = async () => {
      try {
        setIsLoading(true);
        const data = await getTeamPulse();
        const formattedEmployees: Employee[] = data.employees.map((emp, index) => ({
          id: emp.telegram_id,
          token: emp.telegram_id,
          risk: emp.risk_probability,
          name: `Сотрудник #${index + 1}`,
        }));
        setEmployees(formattedEmployees);
      } catch (e: any) {
        setError(e.message || 'Не удалось загрузить данные о команде.');
      } finally {
        setIsLoading(false);
      }
    };

    fetchTeamData();
  }, []);

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
    // ✅ Форсируем обновление цвета
    setSelectedToken(null); // Сначала сбрасываем
    setTimeout(() => {
      setSelectedToken(token); // Затем устанавливаем новое значение
    }, 10);
    
    setSelectorVisible(false);
    const emp = employees.find((e) => e.token === token);
    if (emp) {
      playBellSound(emp.risk);
    }
  };

  const playBellSound = (risk: number) => {
    const bin = 5 - Math.min(4, Math.floor(risk * 5));
    const audio = new Audio(`/sounds/bell${bin}.mp3`);
    audio.play().catch((e) => console.warn('Звук не проигрался:', e));
  };

  const calcTeamMood = (team: Employee[]) => {
    if (team.length === 0) return { color: '#ccc', msg: 'Нет данных о команде', file: 'calm.mp3', risk: 0 };
    const avg = team.reduce((s, e) => s + e.risk, 0) / team.length;
    if (avg < 0.35) return { color: '#2ecc71', msg: 'Команда в хорошем настроении 🌿', file: 'calm.mp3', risk: avg };
    if (avg < 0.7) return { color: '#f1c40f', msg: 'Есть признаки стресса 🟡', file: 'medium.mp3', risk: avg };
    return { color: '#e74c3c', msg: 'Команда под серьёзным давлением ❗️', file: 'tense.mp3', risk: avg };
  };

  const playTeamMoodMelody = async () => {
    const mood = calcTeamMood(employees);
    setTeamMood(mood);
    await Tone.start();
    const minFreq = 130;
    const maxFreq = 700;
    const freq = minFreq + (maxFreq - minFreq) * mood.risk;
    const synth = new Tone.Synth({ oscillator: { type: 'sine' }, envelope: { attack: 2, decay: 1.5, sustain: 0.7, release: 4 } });
    const reverb = new Tone.Reverb({ decay: 5, wet: 0.7 }).toDestination();
    await reverb.generate();
    synth.connect(reverb);
    synth.triggerAttackRelease(freq, '8n');
    setTimeout(() => setTeamMood(null), 6000);
  };

  if (isLoading) return <StatusScreen>Загрузка данных...</StatusScreen>;
  if (error) return <StatusScreen>Ошибка: {error}</StatusScreen>;

  return (
    <AppWrapper>
      <Logo>EchoAI</Logo>
      <DashboardButton onClick={() => navigate('/dashboard')}>Дашборд</DashboardButton>

      <CanvasContainer>
        <Canvas shadows camera={{ position: [0, 3, 8], fov: 45 }} onPointerMissed={handlePointerMissed}>
          <ambientLight intensity={0.4} />
          <directionalLight castShadow position={[5, 10, 5]} intensity={0.8} shadow-mapSize-width={1024} shadow-mapSize-height={1024} />
          <CameraController zoomIn={isZoomedIn} />
          <AvatarModel
            key={`avatar-${selectedToken || 'default'}`} // ✅ Уникальный ключ для форсирования перерендера
            color={modelColor}
            onClick={handleAvatarClick}
            onCenterComputed={() => { cameraInitializedRef.current = true; }}
            isSessionActive={true}
          />
          <mesh receiveShadow rotation={[-Math.PI / 2, 0, 0]} position={[0, 0, 0]}>
            <planeGeometry args={[30, 30]} />
            <shadowMaterial opacity={0.2} />
          </mesh>
        </Canvas>
      </CanvasContainer>

      {selectorVisible && (
        <Modal $visible={selectorVisible}>
          <h3 style={{ color: '#222', flexShrink: 0 }}>Выбери сотрудника:</h3>
          <ScrollableContainer>
            <EmployeeSelector employees={employees} onSelect={handleSelect} />
          </ScrollableContainer>
        </Modal>
      )}

      {selectedEmployee && !selectorVisible && (
        <RightPanel $visible={true}>
          <EmployeeCard employee={selectedEmployee} onDetailsClick={() =>
            navigate(`/dashboard/employee/${selectedEmployee.token}`, {
              state: { employeeName: selectedEmployee.name },
            })}
          />
        </RightPanel>
      )}

      <PlayButton onClick={playTeamMoodMelody} title="Мелодия команды">
        <Equalizer>
          <Bar $delay="0s" /><Bar $delay="0.2s" /><Bar $delay="0.4s" />
        </Equalizer>
      </PlayButton>

      {teamMood && (
        <MoodBanner style={{ backgroundColor: teamMood.color }}>
          <h3>{teamMood.msg}</h3>
          <p>Средний риск: <strong>{Math.round(teamMood.risk * 100)}%</strong></p>
        </MoodBanner>
      )}
    </AppWrapper>
  );
}

const pulseOnce = keyframes`0%{transform:scale(1)}50%{transform:scale(1.07)}100%{transform:scale(1)}`;
const buttonHoverEffect = css`transition:transform .2s ease-out;&:hover{animation:${pulseOnce} .4s ease-in-out}&:active{transform:scale(.98);transition:transform .1s}`;
const AppWrapper = styled.div`width:100vw;height:100vh;position:relative;background-color:#fff;font-family:'Segoe UI',sans-serif`;
const Logo = styled.h1`position:absolute;top:24px;left:30px;font-size:24px;font-weight:600;color:#222;z-index:10`;
const gradientShift = keyframes`0%{background-position:0 50%}50%{background-position:100% 50%}100%{background-position:0 50%}`;
const DashboardButton = styled.button`position:absolute;top:24px;right:30px;z-index:10;padding:10px 22px;border:none;border-radius:100px;font-size:14px;font-weight:600;cursor:pointer;color:#fff;background:linear-gradient(45deg,#7c5bff,#00bbe4,#17a000);background-size:300% 300%;animation:${gradientShift} 6s ease infinite;box-shadow:0 0 15px rgba(124,91,255,.4);${buttonHoverEffect}`;
const CanvasContainer = styled.div`position:absolute;top:0;left:0;width:100%;height:100%;z-index:1`;
const fadeIn = keyframes`from{opacity:0;transform:translateY(20px)}to{opacity:1;transform:translateY(0)}`;

const Modal = styled.div<{ $visible: boolean }>`
  position: absolute;top: 56%;left: 68%;transform: translate(-50%, -50%);background: white;padding: 30px;
  border-radius: 14px;box-shadow: 0 10px 30px rgba(0, 0, 0, 0.25);z-index: 5;
  display: flex;flex-direction: column;max-height: 400px;
  opacity: ${({ $visible }) => ($visible ? 1 : 0)};visibility: ${({ $visible }) => ($visible ? 'visible' : 'hidden')};
  transform: translate(-50%, -50%) scale(${({ $visible }) => ($visible ? 1 : 0.95)});
  transition: opacity 0.4s ease, transform 0.4s ease;
`;

const ScrollableContainer = styled.div`
  overflow-y: auto;margin-right: -10px;padding-right: 10px;
  &::-webkit-scrollbar {width: 6px;}
  &::-webkit-scrollbar-thumb {background-color: #ccc;border-radius: 3px;}
  &::-webkit-scrollbar-track {background: transparent;}
`;

const RightPanel = styled.div<{ $visible: boolean }>`
  position:absolute;top:90px;right:40px;z-index:10;
  opacity:${({ $visible }) => $visible ? 1 : 0};transform:translateX(${({ $visible }) => $visible ? "0" : "20px"});
  transition:opacity .4s ease,transform .4s ease
`;
const PlayButton = styled.button`
  position:absolute;bottom:30px;right:30px;z-index:20;width:64px;height:64px;border:none;
  background:#222;border-radius:50%;cursor:pointer;box-shadow:0 0 20px rgba(0,255,180,.3);
  display:flex;align-items:center;justify-content:center;padding:0;
  &:hover{background:#111}
  ${buttonHoverEffect}
`;
const Equalizer = styled.div`display:flex;align-items:flex-end;gap:3px;height:24px;width:20px`;

const Bar = styled.div<{ $delay: string }>`
  width:4px;height:100%;background:linear-gradient(180deg,#00ffe0,#a566ff,#00ffe0);
  animation:bounce 1s infinite;animation-delay:${p => p.$delay};border-radius:2px;
  @keyframes bounce{0%,100%{transform:scaleY(1)}50%{transform:scaleY(.3)}}
`;
const MoodBanner = styled.div`
  position:fixed;bottom:30px;left:0;right:0;margin:0 auto;width:fit-content;padding:18px 24px;
  border-radius:16px;color:#fff;text-align:center;font-size:16px;z-index:20;
  background:#000;box-shadow:0 10px 30px rgba(0,0,0,.25);animation:${fadeIn} .5s ease-out
`;