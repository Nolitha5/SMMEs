import { useEffect, useState } from 'react';
export function useOnline() {
  const [online, setOnline] = useState(navigator.onLine);
  useEffect(() => {
    const yes = () => setOnline(true); const no = () => setOnline(false);
    addEventListener('online', yes); addEventListener('offline', no);
    return () => { removeEventListener('online', yes); removeEventListener('offline', no); };
  }, []);
  return online;
}
