import AsyncStorage from '@react-native-async-storage/async-storage';
import { SensorApi, SensorEndpointConfig, SensorKind, SensorSample } from '../types';

const STORAGE_KEY = 'sensor-dashboard-cache-v1';

async function loadCache(): Promise<SensorSample[]> {
  try {
    const raw = await AsyncStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return [];
    }
    return JSON.parse(raw) as SensorSample[];
  } catch (error) {
    console.warn('Failed to load cached sensor data', error);
    return [];
  }
}

async function persistCache(samples: SensorSample[]): Promise<void> {
  try {
    await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(samples));
  } catch (error) {
    console.warn('Failed to persist cached sensor data', error);
  }
}

async function fetchWithTimeout(url: string, timeoutMs = 4000): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { signal: controller.signal });
  } finally {
    clearTimeout(timer);
  }
}

function buildApi(baseUrl: string, endpoints: SensorEndpointConfig[]): SensorApi {
  const endpointMap: Record<SensorKind, SensorEndpointConfig> = endpoints.reduce(
    (acc, entry) => {
      acc[entry.kind] = entry;
      return acc;
    },
    {} as Record<SensorKind, SensorEndpointConfig>,
  );

  async function fetchSamples(kind: SensorKind, path: keyof SensorEndpointConfig): Promise<SensorSample[]> {
    const endpoint = endpointMap[kind];
    if (!endpoint) {
      throw new Error(`Missing endpoint configuration for ${kind}`);
    }

    const url = `${baseUrl}${endpoint[path]}`;
    try {
      const response = await fetchWithTimeout(url);
      if (!response.ok) {
        throw new Error(`Unexpected response ${response.status}`);
      }
      const body = (await response.json()) as SensorSample | SensorSample[];
      const samples = Array.isArray(body) ? body : [body];
      await mergeWithCache(samples);
      return samples;
    } catch (error) {
      console.warn(`Falling back to cached ${kind} data`, error);
      const cached = await loadCache();
      return cached.filter((sample) => sample.kind === kind);
    }
  }

  async function mergeWithCache(samples: SensorSample[]): Promise<void> {
    if (!samples.length) {
      return;
    }
    const cached = await loadCache();
    const merged = [...cached];
    samples.forEach((incoming) => {
      const index = merged.findIndex((item) => item.id === incoming.id);
      if (index >= 0) {
        merged[index] = incoming;
      } else {
        merged.push(incoming);
      }
    });
    await persistCache(merged);
  }

  return {
    baseUrl,
    async fetchLatest(kind: SensorKind): Promise<SensorSample | undefined> {
      const samples = await fetchSamples(kind, 'latestPath');
      return samples[0];
    },
    async fetchHistory(kind: SensorKind): Promise<SensorSample[]> {
      return fetchSamples(kind, 'historyPath');
    },
  };
}

export interface SensorApiFactoryConfig {
  baseUrl: string;
  endpoints?: SensorEndpointConfig[];
}

const DEFAULT_ENDPOINTS: SensorEndpointConfig[] = [
  { kind: 'hw416a', latestPath: '/hw416a/latest', historyPath: '/hw416a/history' },
  { kind: 'max30102', latestPath: '/max30102/latest', historyPath: '/max30102/history' },
  { kind: 'sendht22', latestPath: '/sendht22/latest', historyPath: '/sendht22/history' },
];

export function createSensorApi(config: SensorApiFactoryConfig): SensorApi {
  return buildApi(config.baseUrl, config.endpoints ?? DEFAULT_ENDPOINTS);
}
