import React, { useState } from 'react';
import { SafeAreaView, StatusBar, StyleSheet } from 'react-native';
import { SensorDataProvider } from './src/context/SensorDataContext';
import { DashboardScreen } from './src/screens/DashboardScreen';
import { HistoryScreen } from './src/screens/HistoryScreen';
import { SensorKind } from './src/types';

const DEFAULT_API_BASE = 'http://raspberrypi.local:8000';

type ScreenState =
  | { screen: 'dashboard' }
  | { screen: 'history'; sensor: SensorKind };

export default function App() {
  const [screen, setScreen] = useState<ScreenState>({ screen: 'dashboard' });

  return (
    <SensorDataProvider apiBaseUrl={DEFAULT_API_BASE}>
      <SafeAreaView style={styles.safeArea}>
        <StatusBar barStyle="dark-content" />
        {screen.screen === 'dashboard' ? (
          <DashboardScreen onSelectSensor={(kind) => setScreen({ screen: 'history', sensor: kind })} />
        ) : (
          <HistoryScreen kind={screen.sensor} onBack={() => setScreen({ screen: 'dashboard' })} />
        )}
      </SafeAreaView>
    </SensorDataProvider>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: '#fff',
  },
});
