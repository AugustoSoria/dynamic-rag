import { useState } from "react";

const STORAGE_KEY = "dynamic-rag-session-id";

function loadOrCreateSessionId(): string {
  try {
    const existing = localStorage.getItem(STORAGE_KEY);
    if (existing) return existing;
  } catch {
    // localStorage puede no estar disponible (modo privado, cookies bloqueadas)
  }
  const id = crypto.randomUUID();
  try {
    localStorage.setItem(STORAGE_KEY, id);
  } catch {
    // sin persistencia: la sesión dura lo que dure la pestaña
  }
  return id;
}

/** Id de sesión anónimo: identifica los PDFs del usuario sin necesidad de login. */
export function useSession() {
  const [sessionId, setSessionId] = useState(loadOrCreateSessionId);

  const resetSession = () => {
    const id = crypto.randomUUID();
    try {
      localStorage.setItem(STORAGE_KEY, id);
    } catch {
      // ignorado
    }
    setSessionId(id);
  };

  return { sessionId, resetSession };
}
