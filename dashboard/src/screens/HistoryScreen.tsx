import React from 'react';
import { FlatList, Pressable, StyleSheet, Text, View } from 'react-native';
import { useSensorData } from '../hooks/useSensorData';
import { SensorKind } from '../types';

export interface HistoryScreenProps {
  kind: SensorKind;
  onBack: () => void;
}

export const HistoryScreen: React.FC<HistoryScreenProps> = ({ kind, onBack }) => {
  const { summary, formattedHistory, refreshHistory, loading } = useSensorData(kind);
  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Pressable onPress={onBack} accessibilityRole="button">
          <Text style={styles.backLink}>Zurück</Text>
        </Pressable>
        <Text style={styles.title}>{summary.title}</Text>
        <Text style={styles.subTitle}>{summary.description}</Text>
        <Pressable style={styles.refreshButton} onPress={refreshHistory} accessibilityRole="button">
          <Text style={styles.refreshText}>{loading ? 'Lade…' : 'Historie aktualisieren'}</Text>
        </Pressable>
      </View>
      <FlatList
        data={formattedHistory}
        keyExtractor={(item) => item.id}
        contentContainerStyle={styles.listContent}
        renderItem={({ item }) => (
          <View style={styles.listItem}>
            <Text style={styles.listItemText}>{item.label}</Text>
          </View>
        )}
        ListEmptyComponent={<Text style={styles.emptyText}>Noch keine Historie vorhanden.</Text>}
      />
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#fff',
  },
  header: {
    paddingHorizontal: 20,
    paddingTop: 24,
    paddingBottom: 12,
    backgroundColor: '#eff6ff',
  },
  backLink: {
    color: '#1d4ed8',
    fontWeight: '600',
    marginBottom: 12,
  },
  title: {
    fontSize: 24,
    fontWeight: '700',
    color: '#0f172a',
  },
  subTitle: {
    fontSize: 14,
    color: '#475569',
    marginTop: 4,
  },
  refreshButton: {
    alignSelf: 'flex-start',
    marginTop: 12,
    backgroundColor: '#1d4ed8',
    borderRadius: 12,
    paddingVertical: 8,
    paddingHorizontal: 16,
  },
  refreshText: {
    color: '#fff',
    fontWeight: '600',
  },
  listContent: {
    padding: 20,
    gap: 12,
  },
  listItem: {
    backgroundColor: '#f1f5f9',
    borderRadius: 12,
    padding: 16,
  },
  listItemText: {
    color: '#0f172a',
  },
  emptyText: {
    textAlign: 'center',
    marginTop: 48,
    color: '#94a3b8',
  },
});
