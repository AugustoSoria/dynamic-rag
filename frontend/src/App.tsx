import { Workspace } from "./components/Workspace";
import { useSession } from "./hooks/useSession";

export default function App() {
  const { sessionId, resetSession } = useSession();

  // key={sessionId}: al cambiar de sesión React descarta el Workspace y lo crea de cero,
  // así todo su estado (chat, selección, subidas en curso) se resetea sin necesidad de efectos.
  return <Workspace key={sessionId} sessionId={sessionId} onNewSession={resetSession} />;
}
