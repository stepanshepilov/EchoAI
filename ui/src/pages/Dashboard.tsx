import { useEffect, useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import styled, { keyframes, css, createGlobalStyle } from 'styled-components';
import { BarChart, Bar, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';
import ReactMarkdown from 'react-markdown';
import rehypeRaw from 'rehype-raw';
import { getTeamPulse, getInitialAIHelper, postAIChat } from '../services/api';
import type { ChatMessage as APIChatMessage } from '../services/api';
import { TeamPulseResponse } from '../types';

const GlobalStyle = createGlobalStyle`
  *:focus:not(:focus-visible) { outline: none; box-shadow: none; }
`;

const COLORS = { low: '#2ecc71', medium: '#f1c40f', high: '#e74c3c' };

type UIMessage = {
  id: number;
  role: 'user' | 'assistant';
  content: string;
};

export default function Dashboard() {
  const navigate = useNavigate();
  const [data, setData] = useState<TeamPulseResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isChatVisible, setIsChatVisible] = useState(false);
  const [messages, setMessages] = useState<UIMessage[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [isChatLoading, setIsChatLoading] = useState(false);
  const [isChatMaximized, setIsChatMaximized] = useState(false);
  const chatBodyRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (chatBodyRef.current) {
      chatBodyRef.current.scrollTop = chatBodyRef.current.scrollHeight;
    }
  }, [messages, isChatLoading]);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setIsLoading(true);
        const teamPulseData = await getTeamPulse();
        setData(teamPulseData);
      } catch (e: any) { setError(e.message || "Ошибка загрузки данных"); } 
      finally { setIsLoading(false); }
    };
    fetchData();
  }, []);

  const handleOpenChat = async () => {
    setIsChatVisible(true);
    if (messages.length === 0) {
      setIsChatLoading(true);
      try {
        const data = await getInitialAIHelper();
        setMessages([{ id: Date.now(), content: data.recommendation, role: 'assistant' }]);
      } catch (err: any) {
        setMessages([{ id: Date.now(), content: `Не удалось получить совет: ${err.message}`, role: 'assistant' }]);
      } finally {
        setIsChatLoading(false);
      }
    }
  };

  const handleSendMessage = async () => {
    const trimmedInput = inputValue.trim();
    if (!trimmedInput || isChatLoading) return;

    const userMessage: UIMessage = { id: Date.now(), content: trimmedInput, role: 'user' };
    const newMessages = [...messages, userMessage];
    setMessages(newMessages);
    setInputValue('');
    setIsChatLoading(true);

    try {
      const historyForAPI: APIChatMessage[] = newMessages.map(({ role, content }) => ({ role, content }));
      const data = await postAIChat(historyForAPI);
      const aiResponse: UIMessage = { id: Date.now() + 1, content: data.response || "Не удалось получить ответ.", role: 'assistant' };
      setMessages(prev => [...prev, aiResponse]);
    } catch (err: any) {
      const errorResponse: UIMessage = { id: Date.now() + 1, content: `Произошла ошибка: ${err.message}`, role: 'assistant' };
      setMessages(prev => [...prev, errorResponse]);
    } finally {
      setIsChatLoading(false);
    }
  };
  
  const distributionData = data ? [
    { name: 'Низкий риск', value: data.distribution.low },
    { name: 'Средний риск', value: data.distribution.medium },
    { name: 'Высокий риск', value: data.distribution.high }
  ] : [];

  if (isLoading) return <Wrapper><StatusText>Загрузка аналитики...</StatusText></Wrapper>;
  if (error) return <Wrapper><StatusText>Ошибка: {error}</StatusText></Wrapper>;
  if (!data) return <Wrapper><StatusText>Нет данных для отображения.</StatusText></Wrapper>;

  return (
    <Wrapper>
      <GlobalStyle /> 
      <Header>
        <h1>📊 Командная аналитика</h1>
        <HeaderButtons>
          <BackButton onClick={() => navigate('/')}>← На главную</BackButton>
          <AIHelperButton onClick={handleOpenChat}>⚡ Помощь AI-ассистента</AIHelperButton>
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
                {distributionData.map((entry, index) => (<Cell key={`cell-${index}`} fill={entry.name.includes('Низкий') ? COLORS.low : entry.name.includes('Средний') ? COLORS.medium : COLORS.high} />))}
              </Pie>
              <Tooltip /><Legend />
            </PieChart>
          </ResponsiveContainer>
        </ChartCard>
        <WideChartCard>
          <h2>Рейтинг сотрудников по риску выгорания</h2>
          <p style={{ textAlign: 'center', color: '#666' }}>Нажмите на столбец для детальной информации</p>
          <ResponsiveContainer width="100%" height={400}>
            <BarChart data={data.employees.map((e, i) => ({ ...e, token: e.telegram_id, name: `Сотрудник ${i + 1}` }))}>
              <XAxis dataKey="name" /><YAxis />
              <Tooltip formatter={(value: number) => `${(value * 100).toFixed(1)}%`} />
              <Bar dataKey="risk_probability" name="Риск" fill="#3498db" barSize={30} style={{ cursor: 'pointer', outline: 'none' }} 
                onClick={(barData) => {
                  const token = barData?.payload?.token;
                  const name = barData?.payload?.name;
                  if (token && name) { navigate(`/dashboard/employee/${token}`, { state: { employeeName: name } }); }
                }}>
                {data.employees.map((e) => (<Cell key={e.telegram_id} fill={e.risk_probability < 0.4 ? COLORS.low : e.risk_probability < 0.7 ? COLORS.medium : COLORS.high} />))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </WideChartCard>
      </ChartGrid>
      <ChatWidget visible={isChatVisible} maximized={isChatMaximized}>
        <ChatHeader>
          <h3>AI-ассистент</h3>
          <div>
            <HeaderButton onClick={() => setIsChatMaximized(!isChatMaximized)}>
              {isChatMaximized ? '❏' : '❐'}
            </HeaderButton>
            <HeaderButton onClick={() => setIsChatVisible(false)}>×</HeaderButton>
          </div>
        </ChatHeader>
        <ChatBody ref={chatBodyRef}>
          {messages.map((msg) => (
            <ChatMessage key={msg.id} sender={msg.role}>
              {msg.role === 'assistant' ? (
                <ReactMarkdown rehypePlugins={[rehypeRaw]}>{msg.content}</ReactMarkdown>
              ) : (
                msg.content
              )}
            </ChatMessage>
          ))}
          {isChatLoading && (
            <ChatMessage sender="assistant" isTyping>
              <TypingIndicator><span></span><span></span><span></span></TypingIndicator>
            </ChatMessage>
          )}
        </ChatBody>
        <ChatInputContainer>
          <ChatInput 
            placeholder="Спросите что-нибудь..." 
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSendMessage()}
            disabled={isChatLoading}
          />
          <SendButton onClick={handleSendMessage} disabled={isChatLoading}>➤</SendButton>
        </ChatInputContainer>
      </ChatWidget>
    </Wrapper>
  );
}

const pulseOnce = keyframes`0%{transform:scale(1)}50%{transform:scale(1.07)}100%{transform:scale(1)}`;
const buttonHoverEffect = css`transition:transform .2s ease-out;&:hover{animation:${pulseOnce} .4s ease-in-out}&:active{transform:scale(.98);transition:transform .1s}`;
const Wrapper = styled.div`padding:60px;font-family:sans-serif;max-width:1400px;margin:0 auto;@media (max-width:768px){padding:30px 20px}`;
const Header = styled.div`display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:16px`;
const HeaderButtons = styled.div`display:flex;align-items:center;gap:12px;flex-shrink:0`;
const BackButton = styled.button`background-color:#2c3e50;color:#fff;border:none;padding:10px 16px;border-radius:8px;font-size:14px;cursor:pointer;${buttonHoverEffect}`;
const pulseGradient = keyframes`0%{background-position:0 50%}50%{background-position:100% 50%}100%{background-position:0 50%}`;
const AIHelperButton = styled.button`padding:10px 16px;font-size:14px;font-weight:600;color:#fff;border:none;border-radius:8px;cursor:pointer;background:linear-gradient(45deg,#7c5bff,#00bbe4,#17a000);background-size:300% 300%;animation:${pulseGradient} 3s ease infinite;box-shadow:0 0 12px rgba(124,91,255,.4);${buttonHoverEffect}`;
const StatusText = styled.h1`text-align:center;color:#666;margin-top:100px`;
const StatGrid = styled.div`display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:20px;margin:30px 0`;
const StatCard = styled.div`background:#fff;padding:24px;border-radius:12px;box-shadow:0 4px 12px rgba(0,0,0,.08);text-align:center;color:#222`;
const Score = styled.p<{color?:string}>`font-size:clamp(2rem,5vw,2.5rem);font-weight:600;margin:10px 0 0;color:${p=>p.color||"#34495e"}`;
const ChartGrid = styled.div`display:grid;grid-template-columns:repeat(3,1fr);gap:20px;margin-top:20px;@media (max-width:1200px){grid-template-columns:1fr 1fr}@media (max-width:768px){grid-template-columns:1fr}`;
const ChartCard = styled(StatCard)`padding:24px;text-align:left`;
const WideChartCard = styled(ChartCard)`grid-column:span 2;@media (max-width:768px){grid-column:auto}`;
const ChatWidget = styled.div<{ visible: boolean; maximized: boolean }>`
  position: fixed; z-index: 1000; display: flex; flex-direction: column; background: white;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2); transition: all 0.4s ease-in-out;
  bottom: ${({ maximized }) => (maximized ? '0' : '20px')};
  right: ${({ maximized }) => (maximized ? '0' : '20px')};
  width: ${({ maximized }) => (maximized ? '100vw' : '350px')};
  height: ${({ maximized }) => (maximized ? '100vh' : '500px')};
  border-radius: ${({ maximized }) => (maximized ? '0' : '16px')};
  opacity: ${({ visible }) => (visible ? 1 : 0)};
  visibility: ${({ visible }) => (visible ? 'visible' : 'hidden')};
  transform: translateY(${({ visible }) => (visible ? '0' : '20px')});
`;
const ChatHeader = styled.div`
  padding: 16px; border-bottom: 1px solid #f0f0f0; display: flex;
  justify-content: space-between; align-items: center; flex-shrink: 0;
  h3 { margin: 0; font-size: 18px; color: #333; }
`;
const HeaderButton = styled.button`
  background: none; border: none; font-size: 24px; color: #aaa;
  cursor: pointer; line-height: 1; padding: 0 8px;
  &:hover { color: #333; }
`;
const ChatBody = styled.div`
  flex-grow: 1; padding: 16px; overflow-y: auto; display: flex; flex-direction: column;
  &::-webkit-scrollbar { width: 6px; }
  &::-webkit-scrollbar-thumb { background: #e0e0e0; border-radius: 3px; }
`;
const ChatMessage = styled.div<{ sender: 'user' | 'assistant', isTyping?: boolean }>`
  background-color: ${props => props.sender === 'user' ? '#7c5bff' : '#f1f1f1'};
  color: ${props => props.sender === 'user' ? 'white' : '#333'};
  padding: 1px 14px; border-radius: 18px; margin-bottom: 10px; max-width: 80%;
  align-self: ${props => props.sender === 'user' ? 'flex-end' : 'flex-start'};
  margin-left: ${props => props.sender === 'user' ? 'auto' : '0'};
  margin-right: ${props => props.sender === 'user' ? '0' : 'auto'};
  white-space: pre-wrap; opacity: ${props => props.isTyping ? 0.7 : 1};
  
  h1,h2,h3{margin-top:12px;margin-bottom:4px}
  p{margin:0 0 8px;&:last-child{margin-bottom:0}}
  ul,ol{padding-left:20px;margin:0 0 8px}
  li{margin-bottom:4px}
  code{background-color:rgba(0,0,0,.1);padding:2px 4px;border-radius:4px;font-size:.9em}
  pre{background-color:rgba(0,0,0,.1);padding:10px;border-radius:8px;overflow-x:auto;code{background:none;padding:0}}
  blockquote{border-left:3px solid #ccc;padding-left:10px;margin:0 0 8px;color:#666}
`;
const typingAnimation = keyframes`0%,80%,100%{transform:scale(0)}40%{transform:scale(1)}`;
const TypingIndicator = styled.div`span{display:inline-block;width:8px;height:8px;border-radius:50%;background-color:#aaa;animation:${typingAnimation} 1.4s infinite ease-in-out both;&:nth-child(1){animation-delay:-.32s}&:nth-child(2){animation-delay:-.16s}}`;
const ChatInputContainer = styled.div`border-top:1px solid #f0f0f0;padding:12px;display:flex;gap:8px;align-items:center`;
const ChatInput = styled.input`flex-grow:1;border:1px solid #ddd;border-radius:8px;padding:10px 12px;font-size:14px;&:focus{outline:none;border-color:#7c5bff;box-shadow:0 0 0 2px rgba(124,91,255,.2)}&:disabled{background-color:#f9f9f9}`;
const SendButton = styled.button`
  background:#7c5bff;border:none;color:#fff;font-size:16px;border-radius:8px;
  width:40px;height:40px;cursor:pointer;flex-shrink:0;
  display:flex;align-items:center;justify-content:center;
  padding:0;padding-left:2px;
  ${buttonHoverEffect}
  &:hover{background:#6a4fe3}
  &:disabled{background:#c5b8ff;cursor:not-allowed}
`;