import { BASE_URL, ENDPOINTS } from './termaidConfig';
import { getTokens } from './termaidTokens';

export class TermaidChatSocket {
  constructor(onMessage, onClose, onError) {
    this.onMessage = onMessage;
    this.onClose = onClose;
    this.onError = onError;
    this.socket = null;
  }

  async connect() {
    const { access } = await getTokens();
    if (!access) throw new Error('Not authenticated');

    const wsUrl = BASE_URL.replace(/^http/, 'ws') + `${ENDPOINTS.wsTerminal}?token=${access}`;
    this.socket = new WebSocket(wsUrl);

    this.socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (this.onMessage) this.onMessage(data);
      } catch (e) {
        console.error('Failed to parse WS message', e);
      }
    };

    this.socket.onclose = (event) => {
      if (this.onClose) this.onClose(event);
    };

    this.socket.onerror = (event) => {
      if (this.onError) this.onError(event);
    };
  }

  send(type, payload) {
    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify({ type, payload }));
    }
  }

  close() {
    if (this.socket) {
      this.socket.close();
    }
  }
}
