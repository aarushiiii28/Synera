import { useState, useEffect } from 'react';

export function useSSE(url: string | null) {
  const [data, setData] = useState<any[]>([]);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    if (!url) return;
    const es = new EventSource(url);
    
    es.onopen = () => setConnected(true);
    es.onmessage = (e) => {
      try {
        const parsed = JSON.parse(e.data);
        setData(prev => [...prev, parsed]);
      } catch (err) {}
    };
    es.onerror = () => {
      setConnected(false);
      es.close();
    };

    return () => {
      es.close();
      setConnected(false);
    };
  }, [url]);

  return { data, connected };
}
