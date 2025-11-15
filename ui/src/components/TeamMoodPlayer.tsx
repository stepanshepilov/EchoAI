import React, { useState } from 'react';
import styled, { keyframes } from 'styled-components';
import { Employee } from './EmployeeCard';

interface Props {
  employees: Employee[];
}

export const TeamMoodPlayer: React.FC<Props> = ({ employees }) => {
  const [mood, setMood] = useState<null | MoodLevel>(null);
  const [isPlaying, setIsPlaying] = useState(false);

  const getMood = () => {
    const avg = employees.reduce((sum, emp) => sum + emp.risk, 0) / employees.length;

    if (avg < 0.35)
      return {
        level: 'calm',
        color: '#2ecc71',
        msg: 'Команда в хорошем настроении 🌿',
        file: 'calm.mp3',
        risk: avg,
      };
    if (avg < 0.7)
      return {
        level: 'medium',
        color: '#f1c40f',
        msg: 'Есть признаки стресса 🟡',
        file: 'medium.mp3',
        risk: avg,
      };
    return {
      level: 'tense',
      color: '#e74c3c',
      msg: 'Команда под серьёзным давлением ❗️',
      file: 'tense.mp3',
      risk: avg,
    };
  };

  const playMood = () => {
    const moodInfo = getMood();
    const audio = new Audio(`/music/${moodInfo.file}`);
    setMood(moodInfo);
    setIsPlaying(true);

    audio.play().catch(console.warn);

    setTimeout(() => {
      setMood(null);
      setIsPlaying(false);
    }, 12000);
  };

  return (
    <>
      <PlayButton onClick={playMood} disabled={isPlaying}>
        🔔 Проиграть мелодию сотрудников
      </PlayButton>

      {mood && (
        <MoodBanner style={{ backgroundColor: mood.color }}>
          <h3>{mood.msg}</h3>
          <p>Средний уровень стресса: <strong>{Math.round(mood.risk * 100)}%</strong></p>
        </MoodBanner>
      )}
    </>
  );
};

interface MoodLevel {
  level: 'calm' | 'medium' | 'tense';
  color: string;
  msg: string;
  file: string;
  risk: number;
}

const PlayButton = styled.button`
  margin-top: 20px;
  padding: 12px 20px;
  border-radius: 10px;
  border: none;
  background: #444;
  color: white;
  font-size: 16px;
  cursor: pointer;
  transition: all 0.3s ease;

  &:hover {
    background: #333;
  }
  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
`;

const fadeIn = keyframes`
  from {
    opacity: 0;
    transform: translateY(30px);
  } to {
    opacity: 1;
    transform: translateY(0);
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
`;