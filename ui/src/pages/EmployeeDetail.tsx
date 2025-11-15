import { useEffect, useState, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import styled, { keyframes } from 'styled-components';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import { getExplanation, getTopics } from '../services/api';
import { ExplanationResponse, TopicsResponse } from '../types';

const sentimentColor = (sentiment: number) => {
  if (sentiment > 0.1) return '#2ecc71';
  if (sentiment < -0.1) return '#e74c3c';
  return '#f1c40f';
};

export default function EmployeeDetail() {
  const { employeeToken } = useParams<{ employeeToken: string }>();
  const navigate = useNavigate();

  const [explanation, setExplanation] = useState<ExplanationResponse | null>(null);
  const [topics, setTopics] = useState<TopicsResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [predictedAfterVacation, setPredictedAfterVacation] = useState<number | null>(null);
  const [isPredicting, setIsPredicting] = useState(false);
  const [simCardVisible, setSimCardVisible] = useState(false);

  const modalRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!employeeToken) return;
    const fetchData = async () => {
      try {
        setIsLoading(true);
        const [explData, topicsData] = await Promise.all([
          getExplanation(employeeToken),
          getTopics(employeeToken)
        ]);
        setExplanation(explData);
        setTopics(topicsData);
      } catch (e: any) {
        setError(e.message || "Ошибка загрузки");
      } finally {
        setIsLoading(false);
      }
    };
    fetchData();
  }, [employeeToken]);

  // Закрытие карточки при клике вне
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (modalRef.current && !modalRef.current.contains(event.target as Node)) {
        setSimCardVisible(false);
      }
    }
    if (simCardVisible) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [simCardVisible]);

  const simulateVacation = async () => {
    if (!explanation) return;
    try {
      setIsPredicting(true);
      const features = { ...explanation.features, days_since_last_vacation: 0 };
      const res = await fetch('/api/v1/predict', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(features)
      });

      const data = await res.json();
      if (data?.probability !== undefined) {
        setPredictedAfterVacation(data.probability);
        setSimCardVisible(true);
      }
    } catch (err) {
      console.error("Ошибка симуляции отпуска", err);
    } finally {
      setIsPredicting(false);
    }
  };

  const chartData = explanation?.shap_explanation.factors
    .filter(f => f.contribution !== 0)
    .sort((a, b) => Math.abs(b.contribution) - Math.abs(a.contribution))
    .slice(0, 10)
    .reverse();

  if (isLoading) return <Wrapper><StatusText>Загрузка...</StatusText></Wrapper>;
  if (error) return <Wrapper><StatusText>Ошибка: {error}</StatusText></Wrapper>;

  return (
    <Wrapper>
      <Header>
        <h1>Детализация по сотруднику</h1>
        <BackButton onClick={() => navigate('/dashboard')}>← К общему дашборду</BackButton>
      </Header>
      <p>Token: {employeeToken}</p>

      <Grid>
        <Card>
          <h2>Ключевые факторы риска</h2>
          <ResponsiveContainer width="100%" height={400}>
            <BarChart layout="vertical" data={chartData} margin={{ left: 150 }}>
              <XAxis type="number" hide />
              <YAxis type="category" dataKey="feature" width={150} />
              <Tooltip formatter={(value: number) => value.toFixed(4)} />
              <Bar dataKey="contribution">
                {chartData?.map((entry) => (
                  <Cell key={entry.feature} fill={entry.contribution > 0 ? '#e74c3c' : '#2ecc71'} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Card>

        <Card>
          <h2>Темы из обсуждений</h2>
          {topics && topics.topics.length > 0 ? (
            <TopicList>
              {topics.topics.map((topic, i) => (
                <TopicItem key={i}>
                  <TopicHeader>
                    <TopicTitle color={sentimentColor(topic.sentiment)}>{topic.topic}</TopicTitle>
                    <span>{topic.mentions} упом.</span>
                  </TopicHeader>
                  <TopicExamples>"{topic.examples[0]}"</TopicExamples>
                </TopicItem>
              ))}
            </TopicList>
          ) : <p>Темы не найдены.</p>}
        </Card>

        <SimulateCard onClick={simulateVacation}>
          <h2>А что если отправить в отпуск?</h2>
          <p style={{ color: '#555' }}>Узнать, как изменится риск выгорания, если отправить сотрудника в отпуск.</p>
        </SimulateCard>
      </Grid>

      {simCardVisible && predictedAfterVacation !== null && (
        <SimulateModal ref={modalRef}>
          <h3>Результат моделирования</h3>
          <p>
            После отпуска вероятность выгорания снизится до → <strong>{Math.round(predictedAfterVacation * 100)}%</strong>
          </p>
          <SmallNote>Нажмите вне окна, чтобы закрыть</SmallNote>
        </SimulateModal>
      )}
    </Wrapper>
  );
}

const Wrapper = styled.div`padding: 60px; font-family: 'Roboto', sans-serif;`;
const Header = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  margin-bottom: 32px; /* отступ от блока вниз */
`;

const BackButton = styled.button`
  margin-left: 20px;
  margin-top: 8px;
  padding: 10px 16px;
  background-color: #2c3e50;
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  cursor: pointer;
  transition: background-color 0.2s ease;

  &:hover {
    background-color: #34495e;
  }
`;

const StatusText = styled.h1`
  text-align: center;
  font-size: 24px;
  color: #666;
  margin-top: 100px;
`;

const Grid = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(380px, 1fr));
  gap: 20px;
  margin-top: 30px;
`;

const Card = styled.div`
  background: #fff;
  padding: 24px;
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.08);
  color: #222;
`;

const SimulateCard = styled(Card)`
  cursor: pointer;
  user-select: none;
  transition: transform 0.2s ease-in-out;

  &:hover {
    animation: breathe 1.8s ease-in-out infinite;
    background: #f0f9f0;
  }

  @keyframes breathe {
    0%, 100% {
      transform: scale(1);
    }
    50% {
      transform: scale(1.02);
    }
  }
`;

const SimulateModal = styled.div`
  position: fixed;
  left: 50%;
  top: 56%;
  transform: translate(-50%, -50%);
  background: white;
  padding: 32px;
  width: 400px;
  max-width: 90%;
  border-radius: 14px;
  box-shadow: 0 10px 32px rgba(0, 0, 0, 0.25);
  z-index: 20;
`;

const SmallNote = styled.p`
  margin-top: 12px;
  font-size: 12px;
  color: #888;
  text-align: center;
`;

const TopicList = styled.div`display: flex; flex-direction: column; gap: 12px;`;
const TopicItem = styled.div`background: #f9f9f9; border: 1px solid #eee; padding: 12px; border-radius: 8px;`;
const TopicHeader = styled.div`display: flex; justify-content: space-between; align-items: center; font-weight: 500;`;
const TopicTitle = styled.h4`margin: 0; color: ${p => p.color};`;
const TopicExamples = styled.p`margin: 8px 0 0; font-style: italic; color: #666; font-size: 14px;`;