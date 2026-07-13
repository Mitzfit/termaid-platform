export class TermaidAPIError extends Error {
  constructor(message, status, data) {
    super(message);
    this.name = 'TermaidAPIError';
    this.status = status;
    this.data = data;
  }
}

export const parseError = (error) => {
  if (error.response) {
    return new TermaidAPIError(
      error.response.data?.detail || 'API Error',
      error.response.status,
      error.response.data
    );
  } else if (error.request) {
    return new Error('Network error or no response');
  } else {
    return new Error(error.message);
  }
};
