import React from 'react';
import styled from 'styled-components';

// 1. (РЕКОМЕНДАЦИЯ) Обновляем интерфейс для соответствия данным из Home.tsx
export interface Employee {
  id: string;
  token: string;
  name: string;
  risk: number;
}

// 2. Добавляем onDetailsClick в интерфейс Props
interface Props {
  employee: Employee;
  onDetailsClick: () => void;
}

// 3. Принимаем onDetailsClick в компоненте
export const EmployeeCard: React.FC<Props> = ({ employee, onDetailsClick }) => {
  const color = getColorByRisk(employee.risk);

  return (
    <Card style={{ borderLeft: `5px solid ${color}` }}>
      <h3>{employee.name}</h3>
      <RiskIndicator>
        Риск выгорания: <strong>{Math.round(employee.risk * 100)}%</strong>
      </RiskIndicator>
      
      {/* 4. Добавляем кнопку и привязываем к ней onDetailsClick */}
      <DetailsButton onClick={onDetailsClick}>
        Посмотреть детали
      </DetailsButton>
    </Card>
  );
};

// --- Вспомогательные функции и стили (без изменений, кроме добавления кнопки) ---

function getColorByRisk(risk: number): string {
  if (risk < 0.35) return '#2ecc71'; // Green
  if (risk < 0.7) return '#f1c40f'; // Yellow
  return '#e74c3c'; // Red
}

const Card = styled.div`
  background: white;
  padding: 20px;
  border-radius: 12px;
  width: 280px;
  font-family: 'Segoe UI', sans-serif;
  box-shadow: 0 10px 30px rgba(0,0,0,0.12);
  color: #2c3e50;
  display: flex;
  flex-direction: column;

  h3 {
    margin: 0 0 10px 0;
    font-size: 18px;
  }
`;

const RiskIndicator = styled.p`
  margin: 0;
  font-size: 15px;
  color: #34495e;

  strong {
    font-size: 16px;
  }
`;

// 5. Стили для новой кнопки
const DetailsButton = styled.button`
  background-color: #34495e;
  color: white;
  border: none;
  border-radius: 8px;
  padding: 10px 15px;
  margin-top: 20px;
  width: 100%;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: background-color 0.2s ease-in-out;

  &:hover {
    background-color: #2c3e50;
  }
`;