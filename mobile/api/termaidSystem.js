import client from './termaidClient';
import { ENDPOINTS } from './termaidConfig';

export const getHealth = () => client.get(ENDPOINTS.health).then(res => res.data);
export const getCommands = () => client.get(ENDPOINTS.commands).then(res => res.data);
export const getModules = () => client.get(ENDPOINTS.modules).then(res => res.data);
export const getBlocked = () => client.get(ENDPOINTS.blocked).then(res => res.data);
export const getHistory = (limit = 50) => client.get(`${ENDPOINTS.history}?limit=${limit}`).then(res => res.data);
export const executeCommand = (command) => client.post(ENDPOINTS.exec, { command }).then(res => res.data);
export const scanPorts = (host, start = 1, end = 1024, timeout = 300) => client.post(ENDPOINTS.scan, { host, start, end, timeout_ms: timeout }).then(res => res.data);
