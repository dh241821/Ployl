import React, { createContext, useCallback, useEffect, useMemo, useState } from 'react';
import { createSensorApi } from '../services/sensorApi';
import { SensorApi, SensorDataContextState, SensorKind, SensorSample, SensorSummary } from '../types';

const SensorDataContext = createContext<SensorDataContextState | undefined>(undefined);

export interface SensorDataProviderProps {
  apiBaseUrl: string;
  children: React.ReactNode;
}

const SENSOR_METADATA: Record<SensorKind, Pick<SensorSummary, 'title' | 'description'>> = {
  hw416a: {
    title: 'HW416A Präsenzsensor',
    description:
      'Überwacht Bewegungen, verwaltet Betriebsmodi und stellt Triggerereignisse für Automatisierung bereit.',
  },
  max30102: {
    title: 'MAX30102 Pulsoximeter',
    description: 'Zeigt Herzfrequenz- und SpO₂-Samples aus dem FIFO des Sensors.',
  },
  sendht22: {
    title: 'SEN-DHT22 Temperatur & Feuchtigkeit',
    description: 'Erfasst Temperatur- und Feuchtigkeitswerte für Raumklimamonitoring.',
  },
};

function buildInitialSummaries(): Record<SensorKind, SensorSummary> {
  return {
    hw416a: { kind: 'hw416a', history: [], ...SENSOR_METADATA.hw416a },
    max30102: { kind: 'max30102', history: [], ...SENSOR_METADATA.max30102 },
    sendht22: { kind: 'sendht22', history: [], ...SENSOR_METADATA.sendht22 },
  };
}

export const SensorDataProvider: React.FC<SensorDataProviderProps> = ({ apiBaseUrl, children }) => {
  const [summaries, setSummaries] = useState<Record<SensorKind, SensorSummary>>(buildInitialSummaries);
  const [loading, setLoading] = useState<boolean>(false);
  const [lastUpdated, setLastUpdated] = useState<string | undefined>(undefined);

  const api: SensorApi = useMemo(() => createSensorApi({ baseUrl: apiBaseUrl }), [apiBaseUrl]);

  const updateSummary = useCallback((kind: SensorKind, update: Partial<SensorSummary>) => {
    setSummaries((previous) => ({
      ...previous,
      [kind]: {
        ...previous[kind],
        ...update,
      },
    }));
  }, []);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      await Promise.all(
        (Object.keys(SENSOR_METADATA) as SensorKind[]).map(async (kind) => {
          const latest = await api.fetchLatest(kind);
          if (latest) {
            updateSummary(kind, { latest });
          }
        }),
      );
      setLastUpdated(new Date().toISOString());
    } finally {
      setLoading(false);
    }
  }, [api, updateSummary]);

  const loadHistory = useCallback(
    async (kind: SensorKind) => {
      const history = await api.fetchHistory(kind);
      updateSummary(kind, { history });
    },
    [api, updateSummary],
  );

  useEffect(() => {
    refresh().catch((error) => {
      console.warn('Initial refresh failed', error);
    });
  }, [refresh]);

  const value: SensorDataContextState = {
    summaries,
    loading,
    lastUpdated,
    refresh,
    loadHistory,
  };

  return <SensorDataContext.Provider value={value}>{children}</SensorDataContext.Provider>;
};

export function useSensorDataContext(): SensorDataContextState {
  const context = React.useContext(SensorDataContext);
  if (!context) {
    throw new Error('useSensorDataContext must be used within SensorDataProvider');
  }
  return context;
}

export function formatSensorSample(sample: SensorSample): string {
  const timestamp = new Date(sample.capturedAt).toLocaleString();
  const values = Object.entries(sample.values)
    .map(([key, value]) => `${key}: ${value}`)
    .join(' · ');
  return `${timestamp} — ${values}`;
}
