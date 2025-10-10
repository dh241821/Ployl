import React from 'react';
import { RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SensorCard } from '../components/SensorCard';
import { useSensorDataContext } from '../context/SensorDataContext';

export interface DashboardScreenProps {
  onSelectSensor: (kind: 'hw416a' | 'max30102' | 'sendht22') => void;
}

export const DashboardScreen: React.FC<DashboardScreenProps> = ({ onSelectSensor }) => {
  const { summaries, loading, refresh, lastUpdated } = useSensorDataContext();
  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      refreshControl={<RefreshControl refreshing={loading} onRefresh={refresh} />}>
      <Text style={styles.heading}>Sensor Dashboard</Text>
      {lastUpdated ? <Text style={styles.subHeading}>Letzte Aktualisierung: {new Date(lastUpdated).toLocaleString()}</Text> : null}
      <View style={styles.cards}>
        {Object.values(summaries).map((summary) => (
          <SensorCard
            key={summary.kind}
            summary={summary}
            loading={loading}
            onOpenHistory={() => onSelectSensor(summary.kind)}
            onRefresh={refresh}
          />
        ))}
      </View>
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#fff',
  },
  content: {
    padding: 20,
  },
  heading: {
    fontSize: 28,
    fontWeight: '700',
    marginBottom: 4,
    color: '#0f172a',
  },
  subHeading: {
    fontSize: 14,
    color: '#475569',
    marginBottom: 16,
  },
  cards: {
    gap: 16,
  },
});
