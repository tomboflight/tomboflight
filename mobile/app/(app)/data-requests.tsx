import React, { useCallback } from 'react';
import { Linking, Pressable, StyleSheet, Text, View } from 'react-native';

import { ScreenContainer } from '../../src/components/ScreenContainer';
import { SectionCard, WorkspaceHero } from '../../src/features/workspace/ui';
import { appTheme } from '../../src/theme';

const DATA_REQUEST_URL = 'https://tomboflight.com/data-request.html';
const PRIVACY_URL = 'https://tomboflight.com/privacy.html';

async function openExternal(url: string): Promise<void> {
  try {
    if (await Linking.canOpenURL(url)) {
      await Linking.openURL(url);
    }
  } catch {
    // The platform owns the final external-link decision.
  }
}

export default function DataRequestsScreen() {
  const openDataRequest = useCallback(() => void openExternal(DATA_REQUEST_URL), []);
  const openPrivacy = useCallback(() => void openExternal(PRIVACY_URL), []);

  return (
    <ScreenContainer>
      <WorkspaceHero
        title="Account & Data Requests"
        description="Use the public Tomb of Light request form for privacy access, correction, deletion, or other account-data questions. The request is handled under the same customer identity and retention policies as the web workspace."
      />

      <SectionCard title="Submit a Request" subtitle="This in-app entry point opens the official Tomb of Light data-request resource.">
        <View style={styles.actions}>
          <Pressable style={styles.primaryButton} onPress={openDataRequest} accessibilityRole="button" accessibilityLabel="Open Tomb of Light data request form">
            <Text style={styles.primaryButtonText}>Open Data Request Form</Text>
          </Pressable>
          <Pressable style={styles.secondaryButton} onPress={openPrivacy} accessibilityRole="button" accessibilityLabel="Open Tomb of Light privacy policy">
            <Text style={styles.secondaryButtonText}>Read Privacy Policy</Text>
          </Pressable>
        </View>
      </SectionCard>

      <SectionCard title="What the Form Covers">
        <Text style={styles.bodyText}>• Access or correction questions</Text>
        <Text style={styles.bodyText}>• Account or personal-data deletion requests</Text>
        <Text style={styles.bodyText}>• Privacy choices and retention questions</Text>
        <Text style={styles.bodyText}>• Support when you cannot access your account</Text>
      </SectionCard>
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  actions: { gap: appTheme.spacing.sm },
  primaryButton: { backgroundColor: appTheme.colors.primary, borderRadius: appTheme.radius.md, alignItems: 'center', justifyContent: 'center', minHeight: 46, paddingVertical: 12 },
  primaryButtonText: { color: appTheme.colors.surface, fontSize: appTheme.typography.body, fontWeight: '700' },
  secondaryButton: { backgroundColor: appTheme.colors.surface, borderWidth: 1, borderColor: appTheme.colors.border, borderRadius: appTheme.radius.md, alignItems: 'center', justifyContent: 'center', minHeight: 46, paddingVertical: 12 },
  secondaryButtonText: { color: appTheme.colors.textPrimary, fontSize: appTheme.typography.body, fontWeight: '600' },
  bodyText: { color: appTheme.colors.textSecondary, fontSize: appTheme.typography.body, lineHeight: 24 }
});
