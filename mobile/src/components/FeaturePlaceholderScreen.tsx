import React from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { appTheme } from '../theme';
import { ScreenContainer } from './ScreenContainer';

type FeatureHighlight = {
  label: string;
  value: string;
  tone?: 'default' | 'accent' | 'success' | 'warning';
};

type FeaturePlaceholderScreenProps = {
  title: string;
  description: string;
  todoItems: string[];
  highlights?: FeatureHighlight[];
  stageLabel?: string;
  checklistTitle?: string;
  footer?: React.ReactNode;
};

/**
 * Shared feature screen frame for non-dashboard routes.
 * Keeps layout and tone consistent while feature APIs roll in.
 */
export function FeaturePlaceholderScreen({
  title,
  description,
  todoItems,
  highlights = [],
  stageLabel = 'Operational Preview',
  checklistTitle = 'Launch Checklist',
  footer
}: FeaturePlaceholderScreenProps) {
  return (
    <ScreenContainer>
      <View style={styles.hero}>
        <View style={styles.heroTopRow}>
          <Text style={styles.badge}>Tomb of Light Mobile</Text>
          <View style={styles.stagePill}>
            <Text style={styles.stageText}>{stageLabel}</Text>
          </View>
        </View>
        <Text style={styles.title}>{title}</Text>
        <Text style={styles.description}>{description}</Text>
      </View>

      {highlights.length > 0 ? (
        <View style={styles.highlightGrid}>
          {highlights.map((highlight) => (
            <View key={`${highlight.label}-${highlight.value}`} style={styles.highlightCard}>
              <Text style={styles.highlightLabel}>{highlight.label}</Text>
              <Text
                style={[
                  styles.highlightValue,
                  highlight.tone === 'accent' && styles.highlightValueAccent,
                  highlight.tone === 'success' && styles.highlightValueSuccess,
                  highlight.tone === 'warning' && styles.highlightValueWarning
                ]}
              >
                {highlight.value}
              </Text>
            </View>
          ))}
        </View>
      ) : null}

      <View style={styles.card}>
        <Text style={styles.cardTitle}>{checklistTitle}</Text>
        {todoItems.map((item) => (
          <Text key={item} style={styles.todoItem}>
            - {item}
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
    borderColor: '#C7D9F6',
    gap: appTheme.spacing.sm,
    shadowColor: '#0B1B35',
    shadowOpacity: 0.08,
    shadowRadius: 16,
    shadowOffset: { width: 0, height: 6 },
    elevation: 2
  },
  heroTopRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: appTheme.spacing.sm
  },
  badge: {
    color: appTheme.colors.primary,
    fontSize: appTheme.typography.caption,
    fontWeight: '700',
    textTransform: 'uppercase',
    letterSpacing: 0.6
  },
  stagePill: {
    borderWidth: 1,
    borderColor: '#BFD7FF',
    backgroundColor: '#EFF5FF',
    borderRadius: 999,
    paddingHorizontal: 10,
    paddingVertical: 4
  },
  stageText: {
    color: appTheme.colors.primary,
    fontSize: appTheme.typography.caption,
    fontWeight: '700'
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
  highlightGrid: {
    gap: appTheme.spacing.sm
  },
  highlightCard: {
    backgroundColor: appTheme.colors.surface,
    borderRadius: appTheme.radius.md,
    borderWidth: 1,
    borderColor: appTheme.colors.border,
    padding: appTheme.spacing.md,
    gap: 4
  },
  highlightLabel: {
    color: appTheme.colors.textSecondary,
    fontSize: appTheme.typography.caption,
    fontWeight: '600'
  },
  highlightValue: {
    color: appTheme.colors.textPrimary,
    fontSize: appTheme.typography.heading,
    fontWeight: '700'
  },
  highlightValueAccent: {
    color: appTheme.colors.primary
  },
  highlightValueSuccess: {
    color: appTheme.colors.success
  },
  highlightValueWarning: {
    color: appTheme.colors.warning
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
