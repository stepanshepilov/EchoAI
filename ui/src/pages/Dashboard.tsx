import styled from 'styled-components';
import { useNavigate } from 'react-router-dom';

export default function Dashboard() {
  const navigate = useNavigate();

  return (
    <Wrapper>
      <h1>📊 Командная аналитика</h1>

      <p>Здесь будет график SHAP, история рисков, нагрузка и т.д.</p>

      <BackButton onClick={() => navigate('/')}>← Назад</BackButton>
    </Wrapper>
  );
}

const Wrapper = styled.div`
  padding: 60px;
  font-family: sans-serif;
  background: #f4f4f4;
  min-height: 100vh;
  color: #333;
`;

const BackButton = styled.button`
  margin-top: 20px;
  background: #444;
  color: white;
  padding: 10px 16px;
  border: none;
  border-radius: 8px;
  cursor: pointer;
`;