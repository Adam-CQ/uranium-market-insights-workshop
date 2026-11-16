import { useEffect, useState } from "react";

export interface Resource<T> { data: T | null; loading: boolean; error: string | null; retry: () => void }
export function useResource<T>(loader: (signal: AbortSignal) => Promise<T>): Resource<T> {
  const [attempt, setAttempt] = useState(0);
  const [state, setState] = useState<Omit<Resource<T>, "retry">>({ data: null, loading: true, error: null });
  useEffect(() => {
    const controller = new AbortController();
    setState({ data: null, loading: true, error: null });
    loader(controller.signal).then(data => {
      if (!controller.signal.aborted) setState({ data, loading: false, error: null });
    }).catch((error: unknown) => {
      if (!controller.signal.aborted) setState({ data: null, loading: false, error: error instanceof Error ? error.message : "Data request failed" });
    });
    return () => controller.abort();
  }, [loader, attempt]);
  return { ...state, retry: () => setAttempt(value => value + 1) };
}
export function ResourceNotice<T>({ resource }: { resource: Resource<T> }) {
  if (resource.loading) return <p role="status">Loading data from API…</p>;
  if (resource.error) return <div role="alert"><p>{resource.error}</p><button onClick={resource.retry}>Retry data request</button></div>;
  return null;
}
