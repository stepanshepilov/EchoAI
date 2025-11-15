import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import styled from 'styled-components';
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

const COLORS = { low: '#2ecc71', medium: '#f1c40f', high: '#e74c3c' };

export default function Dashboard() {
  const navigate = useNavigate();
  const [data, setData] = useState<TeamPulseResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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
      <Header>
        <h1>📊 Командная аналитика</h1>
        <BackButton onClick={() => navigate('/')}>← На главную</BackButton>
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
              <Pie
                data={distributionData}
                dataKey="value"
                nameKey="name"
                cx="50%"
                cy="50%"
                outerRadius={100}
                label
              >
                {distributionData.map((entry, index) => (
                  <Cell
                    key={`cell-${index}`}
                    fill={
                      entry.name.includes('Низкий') ? COLORS.low
                        : entry.name.includes('Средний') ? COLORS.medium
                        : COLORS.high
                    }
                  />
                ))}
              </Pie>
              <Tooltip />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard style={{ gridColumn: 'span 2' }}>
          <h2>Рейтинг сотрудников по риску выгорания</h2>
          <p style={{ textAlign: 'center', color: '#666' }}>
            Нажмите на столбец для детальной информации
          </p>
          <ResponsiveContainer width="100%" height={400}>
            <BarChart
              data={data.employees.map((e, i) => ({
                ...e,
                name: `Сотрудник ${i + 1}`
              }))}
            >
              <XAxis dataKey="name" />
              <YAxis />
              <Tooltip formatter={(value: number) => `${(value * 100).toFixed(1)}%`} />
              <Bar
                dataKey="risk_probability"
                name="Риск"
                fill="#3498db"
                barSize={30}
                style={{ cursor: 'pointer' }}
                onClick={(barData) => {
                  const token = barData?.payload?.token;
                  if (token) {
                    navigate(`/dashboard/employee/${token}`);
                  }
                }}
              >
                {data.employees.map((e) => (
                  <Cell
                    key={e.token}
                    fill={
                      e.risk_probability < 0.4
                        ? COLORS.low
                        : e.risk_probability < 0.7
                        ? COLORS.medium
                        : COLORS.high
                    }
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
      </ChartGrid>
    </Wrapper>
  );
}

const Wrapper = styled.div`
  padding: 60px;
  font-family: sans-serif;
`;

const BackButton = styled.button`
  background-color: #2c3e50;
  color: white;
  border: none;
  padding: 10px 16px;
  border-radius: 8px;
  font-size: 14px;
  cursor: pointer;
  transition: background 0.2s;
  &:hover {
    background-color: #34495e;
  }
`;

const Header = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
`;

const StatusText = styled.h1`
  text-align: center;
  color: #666;
  margin-top: 100px;
`;

const StatGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 20px;
  margin: 30px 0;
`;

const StatCard = styled.div`
  background: white;
  padding: 20px;
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.08);
  text-align: center;
  color: #222; /* 🛠 Фикс: читаемый текст */
`;

const Score = styled.p<{ color?: string }>`
  font-size: 2.5rem;
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
    grid-template-columns: 1fr;
  }
`;

const ChartCard = styled(StatCard)`
  padding: 24px;
  text-align: left;
  /* color: #222; уже есть у StatCard */
`;