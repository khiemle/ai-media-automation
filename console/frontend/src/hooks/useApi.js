import { useState, useEffect, useCallback } from 'react'

/**
 * Simple data-fetching hook.
 * Usage: const { data, loading, error, refetch } = useApi(fn, [deps])
 */
export function useApi(fetchFn, deps = []) {
  const [data, setData]       = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState(null)

  const run = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await fetchFn()
      setData(result)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, deps) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { run() }, [run])

  return { data, loading, error, refetch: run }
}
