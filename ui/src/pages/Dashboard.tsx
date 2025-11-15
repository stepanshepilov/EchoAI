import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import styled, { keyframes, css, createGlobalStyle } from 'styled-components'; // 1. Импортируем createGlobalStyle
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell
} from 'recharts';
import { getTeamPulse } from '../services/api';
import { TeamPulseResponse } from '../types';

// 2. Создаем компонент с глобальным стилем для исправления бага с outline
const GlobalStyle = createGlobalStyle`
  /* 
    Это правило убирает синюю рамку фокуса для кликов мышью,
    но оставляет ее для навигации с клавиатуры (Tab).
    Это современный и правильный способ решения проблемы.
  */
  *:focus:not(:focus-visible) {
    outline: none;
    box-shadow: none;
  }
`;

const COLORS = { low: '#2ecc71', medium: '#f1c40f', high: '#e74c3c' };

export default function Dashboard() {
  const navigate = useNavigate();
  const [data, setData] = useState<TeamPulseResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchHelperResponse = async () => {
    try {
      const res = await fetch('/api/v1/llm_helper');
      const response = await res.json();
      alert(`AI-ассистент предлагает:\n${response.advice || response.message}`);
    } catch (err) {
      console.error('Ошибка запроса к llm_helper:', err);
      alert('Не удалось получить совет от AI.');
    }
  };

  useEffect(() => {
    const fetchData = async () => {
      try {
        setIsLoading(true);
        const teamPulseData = await getTeamPulse();
        setData(teamPulseData);
      } catch (e: any) {
        setError(e.message || "Ошибка загрузки данных");
      } finally {
        setIsLoading(false);
      }
    };
    fetchData();
  }, []);

  const distributionData = data
    ? [
        { name: 'Низкий риск', value: data.distribution.low },
        { name: 'Средний риск', value: data.distribution.medium },
        { name: 'Высокий риск', value: data.distribution.high }
      ]
    : [];

  if (isLoading) return <Wrapper><StatusText>Загрузка аналитики...</StatusText></Wrapper>;
  if (error) return <Wrapper><StatusText>Ошибка: {error}</StatusText></Wrapper>;
  if (!data) return <Wrapper><StatusText>Нет данных для отображения.</StatusText></Wrapper>;

  return (
    <Wrapper>
      {/* 3. Добавляем компонент глобальных стилей */}
      <GlobalStyle /> 
      <Header>
        <h1>📊 Командная аналитика</h1>
        <HeaderButtons>
          <BackButton onClick={() => navigate('/')}>← На главную</BackButton>
          <AIHelperButton onClick={fetchHelperResponse}>
            ⚡ Помощь AI-ассистента
          </AIHelperButton>
        </HeaderButtons>
      </Header>

      <StatGrid>
        <StatCard>
          <h3>Общий риск</h3>
          <Score>{(data.overall_risk_score * 100).toFixed(1)}%</Score>
        </StatCard>
        <StatCard>
          <h3>Динамика (неделя)</h3>
          <Score color={data.risk_dynamics_weekly.startsWith('+') ? COLORS.high : COLORS.low}>
            {data.risk_dynamics_weekly}
          </Score>
        </StatCard>
        <StatCard>
          <h3>Сотрудников в группе риска</h3>
          <Score>{data.distribution.medium + data.distribution.high}</Score>
        </StatCard>
      </StatGrid>

      <ChartGrid>
        <ChartCard>
          <h2>Распределение по группам риска</h2>
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie data={distributionData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={100} label>
                {distributionData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.name.includes('Низкий') ? COLORS.low : entry.name.includes('Средний') ? COLORS.medium : COLORS.high} />
                ))}
              </Pie>
              <Tooltip />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </ChartCard>
        
        <WideChartCard>
          <h2>Рейтинг сотрудников по риску выгорания</h2>
          <p style={{ textAlign: 'center', color: '#666' }}>Нажмите на столбец для детальной информации</p>
          <ResponsiveContainer width="100%" height={400}>
            <BarChart data={data.employees.map((e, i) => ({ ...e, token: e.telegram_id, name: `Сотрудник ${i + 1}` }))}>
              <XAxis dataKey="name" />
              <YAxis />
              <Tooltip formatter={(value: number) => `${(value * 100).toFixed(1)}%`} />
              <Bar 
                dataKey="risk_probability" 
                name="Риск" 
                fill="#3498db" 
                barSize={30} 
                // 4. Добавляем outline: none для надежности
                style={{ cursor: 'pointer', outline: 'none' }} 
                onClick={(barData) => {
                  const token = barData?.payload?.token;
                  const name = barData?.payload?.name;
                  if (token && name) {
                    navigate(`/dashboard/employee/${token}`, { state: { employeeName: name } });
                  }
                }}>
                {data.employees.map((e) => (
                  <Cell key={e.telegram_id} fill={e.risk_probability < 0.4 ? COLORS.low : e.risk_probability < 0.7 ? COLORS.medium : COLORS.high} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </WideChartCard>
      </ChartGrid>
    </Wrapper>
  );
}

// --- СТИЛИ ---
// (остальные стили без изменений)

const pulseOnce = keyframes`
  0% { transform: scale(1); }
  50% { transform: scale(1.07); }
  100% { transform: scale(1); }
`;

const buttonHoverEffect = css`
  transition: transform 0.2s ease-out;
  &:hover {
    animation: ${pulseOnce} 0.4s ease-in-out;
  }
  &:active {
    transform: scale(0.98);
    transition: transform 0.1s;
  }
`;

const Wrapper = styled.div`
  padding: 60px;
  font-family: sans-serif;
  max-width: 1400px;
  margin: 0 auto;

  @media (max-width: 768px) {
    padding: 30px 20px;
  }
`;

const Header = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 16px;
`;

const HeaderButtons = styled.div`
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
`;

const BackButton = styled.button`
  background-color: #2c3e50;
  color: white;
  border: none;
  padding: 10px 16px;
  border-radius: 8px;
  font-size: 14px;
  cursor: pointer;
  
  ${buttonHoverEffect}
`;

const pulseGradient = keyframes`
  0% { background-position: 0% 50%; }
  50% { background-position: 100% 50%; }
  100% { background-position: 0% 50%; }
`;

const AIHelperButton = styled.button`
  padding: 10px 16px;
  font-size: 14px;
  font-weight: 600;
  color: white;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  background: linear-gradient(45deg, #7c5bff, #00bbe4, #17a000);
  background-size: 300% 300%;
  animation: ${pulseGradient} 3s ease infinite;
  box-shadow: 0 0 12px rgba(124, 91, 255, 0.4);

  ${buttonHoverEffect}
`;

const StatusText = styled.h1`
  text-align: center;
  color: #666;
  margin-top: 100px;
`;

const StatGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 20px;
  margin: 30px 0;
`;

const StatCard = styled.div`
  background: white;
  padding: 24px;
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.08);
  text-align: center;
  color: #222;
`;

const Score = styled.p<{ color?: string }>`
  font-size: clamp(2rem, 5vw, 2.5rem);
  font-weight: 600;
  margin: 10px 0 0;
  color: ${p => p.color || '#34495e'};
`;

const ChartGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 20px;
  margin-top: 20px;

  @media (max-width: 1200px) {
    grid-template-columns: 1fr 1fr;
  }

  @media (max-width: 768px) {
    grid-template-columns: 1fr;
  }
`;

const ChartCard = styled(StatCard)`
  padding: 24px;
  text-align: left;
`;

const WideChartCard = styled(ChartCard)`
  grid-column: span 2;

  @media (max-width: 768px) {
    grid-column: auto;
  }
`;