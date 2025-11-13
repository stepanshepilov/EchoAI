// src/components/EmployeeCard.tsx
import React from 'react';
import styled from 'styled-components';

export interface Employee {
  id: string;
  name: string;
  risk: number;
}

interface Props {
  employee: Employee;
}

export const EmployeeCard: React.FC<Props> = ({ employee }) => {
  const color = getColorByRisk(employee.risk);

  return (
    <Card style={{ borderLeft: `5px solid ${color}` }}>
      <h3>{employee.name}</h3>
      <p>ID: {employee.id}</p>
      <p>Риск выгорания: <strong>{Math.round(employee.risk * 100)}%</strong></p>
    </Card>
  );
};

function getColorByRisk(risk: number): string {
  if (risk < 0.2) return '#2ecc71';
  if (risk < 0.4) return '#f1c40f';
  if (risk < 0.6) return '#e67e22';
  if (risk < 0.8) return '#d35400';
  return '#e74c3c';
}

const Card = styled.div`
  background: white;
  padding: 20px;
  border-radius: 12px;
  width: 300px;
  font-family: sans-serif;
  box-shadow: 0 10px 30px rgba(0,0,0,0.1);
  color: #222;
`;