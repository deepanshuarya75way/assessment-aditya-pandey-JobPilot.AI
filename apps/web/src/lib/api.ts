export const API_URL = process.env.NEXT_PUBLIC_API_URL ;

export async function fetchAPI(endpoint: string, options: RequestInit = {}) {
  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
  
  const headers = {
    "Content-Type": "application/json",
    ...(token && { Authorization: `Bearer ${token}` }),
    ...options.headers,
  };

  const response = await fetch(`${API_URL}${endpoint}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    
    // FastAPI 422 validation errors send an array in 'detail'
    if (response.status === 422 && Array.isArray(errorData.detail)) {
      const messages = errorData.detail.map((err: any) => `${err.loc.join('.')}: ${err.msg}`);
      throw new Error(messages.join(" | "));
    }
    
    throw new Error(errorData.detail || "API Request Failed");
  }

  return response.json();
}