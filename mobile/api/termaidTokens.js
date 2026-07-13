import * as SecureStore from 'expo-secure-store';

const ACCESS_KEY = 'termaid_access_token';
const REFRESH_KEY = 'termaid_refresh_token';

export const getTokens = async () => {
  const access = await SecureStore.getItemAsync(ACCESS_KEY);
  const refresh = await SecureStore.getItemAsync(REFRESH_KEY);
  return { access, refresh };
};

export const saveTokens = async (access, refresh) => {
  await SecureStore.setItemAsync(ACCESS_KEY, access);
  await SecureStore.setItemAsync(REFRESH_KEY, refresh);
};

export const clearTokens = async () => {
  await SecureStore.deleteItemAsync(ACCESS_KEY);
  await SecureStore.deleteItemAsync(REFRESH_KEY);
};
