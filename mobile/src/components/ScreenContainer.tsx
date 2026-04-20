import React from 'react';
import { ScrollView, StyleSheet, View, ViewStyle } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { appTheme } from '../theme';

type ScreenContainerProps = {
  children: React.ReactNode;
  contentStyle?: ViewStyle;
};

/**
 * Shared screen frame for consistent spacing and background.
 */
export function ScreenContainer({ children, contentStyle }: ScreenContainerProps) {
  return (
    <SafeAreaView style={styles.safeArea}>
      <ScrollView
        contentContainerStyle={[styles.content, contentStyle]}
        showsVerticalScrollIndicator={false}
        keyboardShouldPersistTaps="handled"
        contentInsetAdjustmentBehavior="automatic"
      >
        <View>{children}</View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: appTheme.colors.background
  },
  content: {
    padding: appTheme.spacing.lg,
    gap: appTheme.spacing.lg
  }
});
