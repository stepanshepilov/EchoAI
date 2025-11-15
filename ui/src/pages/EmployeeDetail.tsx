import { useEffect, useState, useRef } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import styled, { keyframes, css } from 'styled-components';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import { getExplanation, getTopics, getTeamPulse, getWhatIfVacation } from '../services/api';
import { ExplanationResponse, TopicsResponse } from '../types';

type PredictionResult = {
  original_probability: number;
  what_if_vacation_probability: number;
  probability_change: number;
};

const sentimentColor = (sentiment: number) => {
  if (sentiment > 0.1) return '#2ecc71';
  if (sentiment < -0.1) return '#e74c3c';
  return '#f1c40f';
};

export default function EmployeeDetail() {
  const { employeeToken } = useParams<{ employeeToken: string }>();
  const navigate = useNavigate();
  const location = useLocation();

  const [employeeName, setEmployeeName] = useState<string | null>(null);
  const [explanation, setExplanation] = useState<ExplanationResponse | null>(null);
  const [topics, setTopics] = useState<TopicsResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [predictionResult, setPredictionResult] = useState<PredictionResult | null>(null);
  const [isPredicting, setIsPredicting] = useState(false);
  const [simCardVisible, setSimCardVisible] = useState(false);
  const modalRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!employeeToken) return;
    const fetchData = async () => {
      setIsLoading(true);
      setExplanation(null); setTopics(null); setError(null);
      try {
        const nameFromState = location.state?.employeeName;
        setEmployeeName(nameFromState || null);
        const dataPromises = [getExplanation(employeeToken), getTopics(employeeToken)];
        if (!nameFromState) { dataPromises.push(getTeamPulse()); }
        const [explData, topicsData, teamData] = await Promise.all(dataPromises);
        setExplanation(explData); setTopics(topicsData);
        if (teamData) {
          const employeeIndex = teamData.employees.findIndex((emp: { telegram_id: string }) => emp.telegram_id === employeeToken);
          if (employeeIndex !== -1) { setEmployeeName(`Сотрудник #${employeeIndex + 1}`); }
        }
      } catch (e: any) { setError(e.message || "Ошибка загрузки"); } 
      finally { setIsLoading(false); }
    };
    fetchData();
  }, [employeeToken]);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (modalRef.current && !modalRef.current.contains(event.target as Node)) {
        setSimCardVisible(false);
      }
    }
    if (simCardVisible) { document.addEventListener('mousedown', handleClickOutside); }
    return () => { document.removeEventListener('mousedown', handleClickOutside); };
  }, [simCardVisible]);

  const simulateVacation = async () => {
    if (isPredicting || !employeeToken) return;
    try {
      setIsPredicting(true);
      setPredictionResult(null);
      const data = await getWhatIfVacation(employeeToken);
      setPredictionResult(data);
      setSimCardVisible(true);
    } catch (err: any) {
      console.error("Ошибка симуляции отпуска:", err);
      alert(`Не удалось выполнить моделирование: ${err.message}`);
    } finally {
      setIsPredicting(false);
    }
  };

  const chartData = explanation?.shap_explanation.factors
    .filter(f => f.contribution !== 0)
    .sort((a, b) => Math.abs(b.contribution) - Math.abs(a.contribution))
    .slice(0, 10)
    .reverse();

  if (isLoading) return <Wrapper><StatusText>Загрузка данных сотрудника...</StatusText></Wrapper>;
  if (error) return <Wrapper><StatusText>Ошибка: {error}</StatusText></Wrapper>;

  return (
    <Wrapper>
      <Header>
        <h1>{employeeName ? `Аналитика: ${employeeName}` : 'Детализация по сотруднику'}</h1>
        <BackButton onClick={() => navigate('/dashboard')}>← К общему дашборду</BackButton>
      </Header>

      <Grid>
        <Card>
          <h2>Ключевые факторы риска</h2>
          {chartData && (
            <ResponsiveContainer width="100%" height={400}>
              <BarChart layout="vertical" data={chartData} margin={{ left: 120 }}>
                <XAxis type="number" hide />
                <YAxis type="category" dataKey="feature" width={120} tick={{ fontSize: 11 }} />
                <Tooltip formatter={(value: number) => value.toFixed(4)} />
                <Bar dataKey="contribution">
                  {chartData.map((entry) => (
                    <Cell key={entry.feature} fill={entry.contribution > 0 ? '#e74c3c' : '#2ecc71'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </Card>

        <Card>
          <h2>Темы из обсуждений</h2>
          {topics?.topics?.length > 0 ? (
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
          <CardDescription>
            {isPredicting ? 'Моделируем...' : 'Узнать, как изменится риск выгорания, если отправить сотрудника в отпуск.'}
          </CardDescription>
        </SimulateCard>
      </Grid>
      
      <SimulateModal ref={modalRef} visible={simCardVisible && !!predictionResult}>
        {predictionResult && (
          <>
            <h3>Результат моделирования</h3>
            <ResultText>
              Текущий риск: <strong>{Math.round(predictionResult.original_probability * 100)}%</strong>
            </ResultText>
            <ResultText style={{ marginTop: '16px' }}>
              После отпуска риск снизится до:
            </ResultText>
            <NewProbability>
              {Math.round(predictionResult.what_if_vacation_probability * 100)}%
            </NewProbability>
            <SmallNote>Нажмите вне окна, чтобы закрыть</SmallNote>
          </>
        )}
      </SimulateModal>
    </Wrapper>
  );
}

const pulseOnce = keyframes`
  0% { transform: scale(1); }
  50% { transform: scale(1.07); }
  100% { transform: scale(1); }
`;
const buttonHoverEffect = css`
  transition: transform 0.2s ease-out;
  &:hover { animation: ${pulseOnce} 0.4s ease-in-out; }
  &:active { transform: scale(0.98); transition: transform 0.1s; }
`;

const Wrapper = styled.div`
  display: flex; flex-direction: column; align-items: center;
  padding: 60px 20px; font-family: 'Roboto', sans-serif;
  width: 100%; box-sizing: border-box;
`;
const Header = styled.div`
  display: flex; justify-content: space-between; align-items: center;
  flex-wrap: wrap; gap: 16px; width: 100%; max-width: 1240px; margin-bottom: 32px;
`;
const BackButton = styled.button`
  padding: 10px 16px; background-color: #2c3e50; color: white; border: none;
  border-radius: 8px; font-size: 14px; cursor: pointer; white-space: nowrap;
  ${buttonHoverEffect}
`;
const Grid = styled.div`
  display: flex; flex-wrap: wrap; justify-content: center;
  gap: 20px; width: 100%; max-width: 1240px;
  align-items: stretch; /* Заставляет все карточки в ряду иметь одинаковую высоту */
`;
const Card = styled.div`
  background: #fff; padding: 24px; border-radius: 12px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.08); color: #222;
  flex-grow: 1; width: 100%; max-width: 400px;
  display: flex;
  flex-direction: column;
`;

const CardDescription = styled.p`
  color: #555;
  text-align: center;
  margin-top: auto; /* Прижимает текст к низу карточки, если он короткий */
  
  /* КЛЮЧЕВОЙ ФИКС: Задаем минимальную высоту, равную высоте 2-3 строк текста */
  min-height: 48px; 
  
  /* Эти стили центрируют текст, когда он короткий ("Моделируем...") */
  display: flex;
  align-items: center;
  justify-content: center;
`;

const SimulateCard = styled(Card)`
  cursor: pointer; user-select: none;
  ${buttonHoverEffect}
  &:hover { background: #f0f9f0; }
`;
const StatusText = styled.h1`
  text-align: center; font-size: 24px; color: #666; margin-top: 100px;
`;
const SimulateModal = styled.div<{ visible: boolean }>`
  position: fixed;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
  background: white;
  padding: 32px;
  width: 400px;
  max-width: 90%;
  border-radius: 14px;
  box-shadow: 0 10px 32px rgba(0, 0, 0, 0.25);
  z-index: 20;
  text-align: center;
  
  opacity: ${({ visible }) => (visible ? 1 : 0)};
  visibility: ${({ visible }) => (visible ? 'visible' : 'hidden')};
  transform: translate(-50%, -50%) scale(${({ visible }) => (visible ? 1 : 0.95)});
  transition: opacity 0.3s ease, transform 0.3s ease, visibility 0.3s;
`;
const ResultText = styled.p`margin: 0; font-size: 16px; color: #555;`;
const NewProbability = styled.p`
  margin: 8px 0 16px; font-size: 42px; font-weight: 700; color: #2ecc71;
`;
const SmallNote = styled.p`
  margin-top: 12px; font-size: 12px; color: #888; text-align: center;
`;
const TopicList = styled.div`display: flex; flex-direction: column; gap: 12px;`;
const TopicItem = styled.div`background: #f9f9f9; border: 1px solid #eee; padding: 12px; border-radius: 8px;`;
const TopicHeader = styled.div`display: flex; justify-content: space-between; align-items: center; font-weight: 500;`;
const TopicTitle = styled.h4`margin: 0; color: ${p => p.color};`;
const TopicExamples = styled.p`margin: 8px 0 0; font-style: italic; color: #666; font-size: 14px;`;