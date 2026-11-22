import { useQuery } from "@tanstack/react-query";

import { fetchConfig } from "../api/client";

/** Límites del backend. Mientras cargan (o si fallan) es `undefined` y el backend sigue validando igual. */
export function useConfig() {
  return useQuery({ queryKey: ["config"], queryFn: fetchConfig, staleTime: Infinity }).data;
}
