import React from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native';
import { SensorSample, SensorSummary } from '../types';
import { formatSensorSample } from '../context/SensorDataContext';

export interface SensorCardProps {
  summary: SensorSummary;
  loading?: boolean;
  onOpenHistory?: () => void;
  onRefresh?: () => void;
}

export const SensorCard: React.FC<SensorCardProps> = ({ summary, loading, onOpenHistory, onRefresh }) => {
  const latest: SensorSample | undefined = summary.latest;
  return (
    <Pressable style={styles.card} onPress={onOpenHistory} accessibilityRole="button">
      <View style={styles.headerRow}>
        <Text style={styles.title}>{summary.title}</Text>
        {loading ? <ActivityIndicator size="small" color="#1d4ed8" /> : null}
      </View>
      <Text style={styles.description}>{summary.description}</Text>
      {latest ? (
        <View style={styles.latestContainer}>
          <Text style={styles.latestLabel}>Letzter Messwert</Text>
          <Text style={styles.latestValue}>{formatSensorSample(latest)}</Text>
        </View>
      ) : (
        <Text style={styles.emptyState}>Noch keine Messwerte vorhanden.</Text>
      )}
      <View style={styles.actions}>
        <Pressable style={styles.actionButton} onPress={onRefresh} accessibilityRole="button">
          <Text style={styles.actionText}>Aktualisieren</Text>
        </Pressable>
        <Pressable style={styles.actionButtonSecondary} onPress={onOpenHistory} accessibilityRole="button">
          <Text style={styles.actionTextSecondary}>Historie</Text>
        </Pressable>
      </View>
    </Pressable>
  );
};

const styles = StyleSheet.create({
  card: {
    backgroundColor: '#f8fafc',
    borderRadius: 16,
    padding: 20,
    marginBottom: 16,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.08,
    shadowRadius: 6,
    elevation: 2,
  },
  headerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 4,
  },
  title: {
    fontSize: 18,
    fontWeight: '600',
    color: '#0f172a',
  },
  description: {
    fontSize: 14,
    color: '#475569',
    marginBottom: 12,
  },
  latestContainer: {
    backgroundColor: '#e0f2fe',
    borderRadius: 12,
    padding: 12,
    marginBottom: 12,
  },
  latestLabel: {
    fontSize: 12,
    color: '#1d4ed8',
    marginBottom: 4,
    fontWeight: '500',
  },
  latestValue: {
    fontSize: 14,
    color: '#0f172a',
  },
  emptyState: {
    fontSize: 14,
    color: '#94a3b8',
    marginBottom: 12,
  },
  actions: {
    flexDirection: 'row',
    justifyContent: 'flex-start',
    gap: 12,
  },
  actionButton: {
    backgroundColor: '#1d4ed8',
    paddingVertical: 10,
    paddingHorizontal: 16,
    borderRadius: 12,
  },
  actionText: {
    color: '#fff',
    fontWeight: '600',
  },
  actionButtonSecondary: {
    borderColor: '#1d4ed8',
    borderWidth: 1,
    paddingVertical: 10,
    paddingHorizontal: 16,
    borderRadius: 12,
  },
  actionTextSecondary: {
    color: '#1d4ed8',
    fontWeight: '600',
  },
});
