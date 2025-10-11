export type SensorKind = 'hw416a' | 'max30102' | 'sendht22';

export interface SensorSample {
  id: string;
  kind: SensorKind;
  capturedAt: string;
  values: Record<string, number>;
}

export interface SensorSummary {
  kind: SensorKind;
  title: string;
  description: string;
  latest?: SensorSample;
  history: SensorSample[];
}

export interface SensorApi {
  baseUrl: string;
  fetchLatest(kind: SensorKind): Promise<SensorSample | undefined>;
  fetchHistory(kind: SensorKind): Promise<SensorSample[]>;
}

export interface SensorDataContextState {
  summaries: Record<SensorKind, SensorSummary>;
  loading: boolean;
  lastUpdated?: string;
  refresh(): Promise<void>;
  loadHistory(kind: SensorKind): Promise<void>;
}

export interface SensorEndpointConfig {
  kind: SensorKind;
  latestPath: string;
  historyPath: string;
}
