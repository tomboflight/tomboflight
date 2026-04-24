import React from 'react';
import {
  ActivityIndicator,
  Pressable,
  StyleProp,
  StyleSheet,
  Text,
  TextStyle,
  View,
  ViewStyle
} from 'react-native';

import { appTheme } from '../../theme';

type WorkspaceHeroProps = {
  title: string;
  description: string;
  kicker?: string;
  contextLine?: string;
};

export function WorkspaceHero({ title, description, kicker = 'Tomb of Light Mobile', contextLine }: WorkspaceHeroProps) {
  return (
    <View style={styles.heroCard}>
      <Text style={styles.heroKicker}>{kicker}</Text>
      <Text style={styles.heroTitle}>{title}</Text>
      <Text style={styles.heroDescription}>{description}</Text>
      {contextLine ? <Text style={styles.heroContext}>{contextLine}</Text> : null}
    </View>
  );
}

type SectionCardProps = {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  contentStyle?: StyleProp<ViewStyle>;
};

export function SectionCard({ title, subtitle, children, contentStyle }: SectionCardProps) {
  return (
    <View style={styles.sectionCard}>
      <View style={styles.sectionHeader}>
        <Text style={styles.sectionTitle}>{title}</Text>
        {subtitle ? <Text style={styles.sectionSubtitle}>{subtitle}</Text> : null}
      </View>
      <View style={contentStyle}>{children}</View>
    </View>
  );
}

type DataStateCardProps = {
  kind: 'loading' | 'error' | 'empty';
  title: string;
  message: string;
  actionLabel?: string;
  onAction?: () => void;
  actionDisabled?: boolean;
};

export function DataStateCard({
  kind,
  title,
  message,
  actionLabel,
  onAction,
  actionDisabled = false
}: DataStateCardProps) {
  const stateTone =
    kind === 'error'
      ? styles.stateError
      : kind === 'empty'
        ? styles.stateEmpty
        : styles.stateLoading;

  return (
    <View style={[styles.stateCard, stateTone]}>
      {kind === 'loading' ? <ActivityIndicator size="small" color={appTheme.colors.primary} /> : null}
      <Text style={styles.stateTitle}>{title}</Text>
      <Text style={styles.stateMessage}>{message}</Text>
      {actionLabel && onAction ? (
        <Pressable
          style={[styles.inlineAction, actionDisabled && styles.inlineActionDisabled]}
          onPress={onAction}
          disabled={actionDisabled}
          accessibilityRole="button"
          accessibilityLabel={actionLabel}
        >
          <Text style={styles.inlineActionText}>{actionLabel}</Text>
        </Pressable>
      ) : null}
    </View>
  );
}

type WorkspaceChipProps = {
  label: string;
  tone?: 'default' | 'accent' | 'success' | 'warning' | 'muted';
};

export function WorkspaceChip({ label, tone = 'default' }: WorkspaceChipProps) {
  const toneStyle =
    tone === 'accent'
      ? styles.chipAccent
      : tone === 'success'
        ? styles.chipSuccess
        : tone === 'warning'
          ? styles.chipWarning
          : tone === 'muted'
            ? styles.chipMuted
            : styles.chipDefault;

  const textToneStyle =
    tone === 'muted'
      ? styles.chipTextMuted
      : tone === 'success'
        ? styles.chipTextSuccess
        : tone === 'warning'
          ? styles.chipTextWarning
          : styles.chipTextDefault;

  return (
    <View style={[styles.chip, toneStyle]}>
      <Text style={[styles.chipText, textToneStyle]}>{label}</Text>
    </View>
  );
}

type KeyValueRowProps = {
  label: string;
  value: string;
  valueStyle?: StyleProp<TextStyle>;
};

export function KeyValueRow({ label, value, valueStyle }: KeyValueRowProps) {
  return (
    <View style={styles.keyValueRow}>
      <Text style={styles.keyLabel}>{label}</Text>
      <Text style={[styles.keyValue, valueStyle]}>{value}</Text>
    </View>
  );
}

type PrimaryActionButtonProps = {
  label: string;
  onPress: () => void;
  accessibilityLabel: string;
  disabled?: boolean;
  style?: StyleProp<ViewStyle>;
};

export function PrimaryActionButton({
  label,
  onPress,
  accessibilityLabel,
  disabled = false,
  style
}: PrimaryActionButtonProps) {
  return (
    <Pressable
      style={[styles.primaryButton, disabled && styles.buttonDisabled, style]}
      onPress={onPress}
      disabled={disabled}
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel}
    >
      <Text style={styles.primaryButtonText}>{label}</Text>
    </Pressable>
  );
}

type SecondaryActionButtonProps = {
  label: string;
  onPress: () => void;
  accessibilityLabel: string;
  disabled?: boolean;
  style?: StyleProp<ViewStyle>;
};

export function SecondaryActionButton({
  label,
  onPress,
  accessibilityLabel,
  disabled = false,
  style
}: SecondaryActionButtonProps) {
  return (
    <Pressable
      style={[styles.secondaryButton, disabled && styles.buttonDisabled, style]}
      onPress={onPress}
      disabled={disabled}
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel}
    >
      <Text style={styles.secondaryButtonText}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  heroCard: {
    backgroundColor: '#0E2A52',
    borderRadius: appTheme.radius.lg,
    borderWidth: 1,
    borderColor: '#1F4D86',
    padding: appTheme.spacing.lg,
    gap: appTheme.spacing.xs,
    shadowColor: '#06122A',
    shadowOpacity: 0.22,
    shadowRadius: 16,
    shadowOffset: { width: 0, height: 8 },
    elevation: 4
  },
  heroKicker: {
    color: '#8AB6FF',
    fontSize: appTheme.typography.caption,
    fontWeight: '700',
    textTransform: 'uppercase',
    letterSpacing: 0.8
  },
  heroTitle: {
    color: '#F7FAFF',
    fontSize: appTheme.typography.title,
    fontWeight: '700'
  },
  heroDescription: {
    color: '#D3E2FF',
    fontSize: appTheme.typography.body,
    lineHeight: 22
  },
  heroContext: {
    color: '#ABC8FF',
    fontSize: appTheme.typography.caption,
    fontWeight: '600',
    marginTop: 4
  },
  sectionCard: {
    backgroundColor: appTheme.colors.surface,
    borderRadius: appTheme.radius.md,
    borderWidth: 1,
    borderColor: appTheme.colors.border,
    padding: appTheme.spacing.md,
    gap: appTheme.spacing.sm
  },
  sectionHeader: {
    gap: 4
  },
  sectionTitle: {
    color: appTheme.colors.textPrimary,
    fontSize: appTheme.typography.heading,
    fontWeight: '700'
  },
  sectionSubtitle: {
    color: appTheme.colors.textSecondary,
    fontSize: appTheme.typography.caption,
    lineHeight: 18
  },
  stateCard: {
    borderRadius: appTheme.radius.md,
    borderWidth: 1,
    padding: appTheme.spacing.md,
    gap: appTheme.spacing.sm
  },
  stateLoading: {
    backgroundColor: appTheme.colors.surface,
    borderColor: appTheme.colors.border
  },
  stateError: {
    backgroundColor: '#FFF5F5',
    borderColor: '#F2B5B5'
  },
  stateEmpty: {
    backgroundColor: '#F9FBFE',
    borderColor: '#D7E3F4'
  },
  stateTitle: {
    color: appTheme.colors.textPrimary,
    fontSize: appTheme.typography.body,
    fontWeight: '700'
  },
  stateMessage: {
    color: appTheme.colors.textSecondary,
    fontSize: appTheme.typography.body,
    lineHeight: 22
  },
  inlineAction: {
    alignSelf: 'flex-start',
    backgroundColor: appTheme.colors.primary,
    borderRadius: appTheme.radius.md,
    paddingVertical: 10,
    paddingHorizontal: 14
  },
  inlineActionDisabled: {
    opacity: 0.72
  },
  inlineActionText: {
    color: appTheme.colors.surface,
    fontSize: appTheme.typography.caption,
    fontWeight: '700'
  },
  chip: {
    borderWidth: 1,
    borderRadius: appTheme.radius.md,
    paddingHorizontal: 10,
    paddingVertical: 5
  },
  chipDefault: {
    borderColor: '#BCD2F8',
    backgroundColor: '#EEF5FF'
  },
  chipAccent: {
    borderColor: '#89B4FF',
    backgroundColor: '#DFECFF'
  },
  chipSuccess: {
    borderColor: '#A6DEC8',
    backgroundColor: '#ECFBF5'
  },
  chipWarning: {
    borderColor: '#F2D39D',
    backgroundColor: '#FFF7E8'
  },
  chipMuted: {
    borderColor: appTheme.colors.border,
    backgroundColor: '#F6F8FC'
  },
  chipText: {
    fontSize: appTheme.typography.caption,
    fontWeight: '700'
  },
  chipTextDefault: {
    color: appTheme.colors.primary
  },
  chipTextMuted: {
    color: appTheme.colors.textSecondary
  },
  chipTextSuccess: {
    color: appTheme.colors.success
  },
  chipTextWarning: {
    color: appTheme.colors.warning
  },
  keyValueRow: {
    gap: 2
  },
  keyLabel: {
    color: appTheme.colors.textSecondary,
    fontSize: appTheme.typography.caption,
    fontWeight: '600'
  },
  keyValue: {
    color: appTheme.colors.textPrimary,
    fontSize: appTheme.typography.body,
    fontWeight: '600'
  },
  primaryButton: {
    backgroundColor: appTheme.colors.primary,
    borderRadius: appTheme.radius.md,
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 12,
    paddingHorizontal: 14
  },
  primaryButtonText: {
    color: appTheme.colors.surface,
    fontSize: appTheme.typography.body,
    fontWeight: '700'
  },
  secondaryButton: {
    backgroundColor: appTheme.colors.surface,
    borderWidth: 1,
    borderColor: appTheme.colors.border,
    borderRadius: appTheme.radius.md,
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 12,
    paddingHorizontal: 14
  },
  secondaryButtonText: {
    color: appTheme.colors.textPrimary,
    fontSize: appTheme.typography.body,
    fontWeight: '600'
  },
  buttonDisabled: {
    opacity: 0.72
  }
});
