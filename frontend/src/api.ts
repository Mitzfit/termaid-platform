export class TokenStore {
  get access(): string | null {
    return localStorage.getItem('termaid_access_token');
  }

  set(tokens: any) {
    if (tokens && tokens.access_token) {
      localStorage.setItem('termaid_access_token', tokens.access_token);
    } else if (typeof tokens === 'string') {
      localStorage.setItem('termaid_access_token', tokens);
    }
  }

  clear() {
    localStorage.removeItem('termaid_access_token');
  }
}

export class ApiClient {
  async login(username: string, password: string): Promise<any> {
    const formData = new URLSearchParams();
    formData.append('username', username);
    formData.append('password', password);

    // Attempt standard FastAPI OAuth2 login route
    let response = await fetch('http://localhost:8000/api/auth/login', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded'
      },
      body: formData.toString()
    });

    // Fallback if your backend uses a different endpoint route
    if (response.status === 404) {
      response = await fetch('http://localhost:8000/token', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: formData.toString()
      });
    }

    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || 'Authentication failed. Check credentials.');
    }

    return await response.json();
  }
}
