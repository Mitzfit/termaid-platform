import client from './termaidClient';
import { ENDPOINTS } from './termaidConfig';
import { saveTokens, clearTokens } from './termaidTokens';

export const login = async (username, password) => {
  const formData = new URLSearchParams();
  formData.append('username', username);
  formData.append('password', password);
  
  const { data } = await client.post(ENDPOINTS.authLogin, formData, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
  });
  await saveTokens(data.access_token, data.refresh_token);
  return data;
};

export const register = async (username, email, password) => {
  const { data } = await client.post(ENDPOINTS.authRegister, { username, email, password });
  return data;
};

export const logout = async () => {
  await clearTokens();
};
