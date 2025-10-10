import { useCallback } from 'react';
import { SensorKind } from '../types';
import { formatSensorSample, useSensorDataContext } from '../context/SensorDataContext';

export function useSensorData(kind: SensorKind) {
  const { summaries, loadHistory, loading, lastUpdated, refresh } = useSensorDataContext();
  const summary = summaries[kind];

  const refreshHistory = useCallback(async () => {
    await loadHistory(kind);
  }, [kind, loadHistory]);

  return {
    summary,
    loading,
    lastUpdated,
    refresh,
    refreshHistory,
    formattedHistory: summary.history.map((sample) => ({
      id: sample.id,
      label: formatSensorSample(sample),
    })),
  };
}
