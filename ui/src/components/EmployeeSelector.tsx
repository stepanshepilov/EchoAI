import React from 'react';
import styled from 'styled-components';

export interface Employee {
  id: string;
  name: string;
  risk: number;
}

interface Props {
  employees: Employee[];
  onSelect: (id: string) => void;
}

export const EmployeeSelector: React.FC<Props> = ({ employees, onSelect }) => {
  return (
    <SelectorWrapper>
      {employees.map((e) => (
        <OptionButton
          key={e.id}
          onClick={() => onSelect(e.id)}
          style={{ borderLeft: `6px solid ${getColorByRisk(e.risk)}` }}
        >
          {e.id} – {e.name}
        </OptionButton>
      ))}
    </SelectorWrapper>
  );
};

const SelectorWrapper = styled.div`
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: 280px;
`;

const OptionButton = styled.button`
  padding: 10px 16px;
  font-size: 16px;
  background: white;
  color: #222;
  border: 1px solid #ccc;
  border-radius: 8px;
  text-align: left;
  cursor: pointer;
  transition: background 0.2s ease;
  &:hover {
    background: #f4f4f4;
  }
`;

const getColorByRisk = (risk: number): string => {
  if (risk < 0.2) return '#2ecc71';
  if (risk < 0.4) return '#f1c40f';
  if (risk < 0.6) return '#e67e22';
  if (risk < 0.8) return '#d35400';
  return '#e74c3c';
};