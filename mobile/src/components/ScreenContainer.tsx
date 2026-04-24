import React from 'react';
import { ScrollView, StyleProp, StyleSheet, ViewStyle } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { appTheme } from '../theme';

type ScreenContainerProps = {
  children: React.ReactNode;
  contentStyle?: StyleProp<ViewStyle>;
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
        keyboardDismissMode="on-drag"
        automaticallyAdjustKeyboardInsets={true}
        contentInsetAdjustmentBehavior="automatic"
      >
        {children}
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
    paddingBottom: appTheme.spacing.xl + appTheme.spacing.md,
    gap: appTheme.spacing.lg
  }
});
