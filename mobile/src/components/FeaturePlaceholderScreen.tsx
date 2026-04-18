import React from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { appTheme } from '../theme';
import { ScreenContainer } from './ScreenContainer';

type FeaturePlaceholderScreenProps = {
  title: string;
  description: string;
  todoItems: string[];
  footer?: React.ReactNode;
};

/**
 * Placeholder template for MVP screens.
 */
export function FeaturePlaceholderScreen({
  title,
  description,
  todoItems,
  footer
}: FeaturePlaceholderScreenProps) {
  return (
    <ScreenContainer>
      <View style={styles.hero}>
        <Text style={styles.badge}>Tomb of Light Mobile</Text>
        <Text style={styles.title}>{title}</Text>
        <Text style={styles.description}>{description}</Text>
      </View>

      <View style={styles.card}>
        <Text style={styles.cardTitle}>Integration TODO</Text>
        {todoItems.map((item) => (
          <Text key={item} style={styles.todoItem}>
            • {item}
          </Text>
        ))}
      </View>

      {footer}
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  hero: {
    backgroundColor: appTheme.colors.surface,
    borderRadius: appTheme.radius.lg,
    padding: appTheme.spacing.lg,
    borderWidth: 1,
    borderColor: '#CFE0FA',
    gap: appTheme.spacing.sm
  },
  badge: {
    color: appTheme.colors.primary,
    fontSize: appTheme.typography.caption,
    fontWeight: '700',
    textTransform: 'uppercase',
    letterSpacing: 0.6
  },
  title: {
    color: appTheme.colors.textPrimary,
    fontSize: appTheme.typography.title,
    fontWeight: '700'
  },
  description: {
    color: appTheme.colors.textSecondary,
    fontSize: appTheme.typography.body,
    lineHeight: 24
  },
  card: {
    backgroundColor: appTheme.colors.surface,
    borderRadius: appTheme.radius.md,
    padding: appTheme.spacing.md,
    borderWidth: 1,
    borderColor: appTheme.colors.border,
    gap: appTheme.spacing.sm
  },
  cardTitle: {
    color: appTheme.colors.textPrimary,
    fontSize: appTheme.typography.heading,
    fontWeight: '600'
  },
  todoItem: {
    color: appTheme.colors.textSecondary,
    fontSize: appTheme.typography.body,
    lineHeight: 22
  }
});
