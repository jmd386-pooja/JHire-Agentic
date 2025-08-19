'use client';

import { useEffect } from 'react';

interface ErrorProps {
  error: Error;                 // The error object that contains the error information
  reset: () => void;            // A function that will reset the state or the error boundary
}

export default function Error({ error, reset }: ErrorProps) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div>
      <h2>Something went wrong!</h2>
      <button onClick={reset}>
        Try again
      </button>
    </div>
  );
}
