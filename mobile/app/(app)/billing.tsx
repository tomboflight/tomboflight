import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'expo-router';
import { Alert, Linking, Pressable, StyleSheet, Text, View } from 'react-native';

import { ScreenContainer } from '../../src/components/ScreenContainer';
import {
  createBillingPortalSession,
  fetchAccessContext,
  fetchBillingConfig,
  fetchBillingOverview,
  fetchMyOrders,
  mapWorkspaceDataError,
  BillingOverviewPayload,
  BillingConfigPayload,
  OrderPayload
} from '../../src/services/api';
import { appTheme } from '../../src/theme';
import {
  asRecord,
  asString,
  formatTimestamp,
  toHumanLabel
} from '../../src/features/workspace/format';
import {
  DataStateCard,
  KeyValueRow,
  SectionCard,
  WorkspaceChip,
  WorkspaceHero
} from '../../src/features/workspace/ui';

type AccessContextSnapshot = {
  activeProjectId: string;
  activeFamilyId: string;
  packageLane: string;
  experienceMode: string;
};

function summarizeContext(payload: Record<string, unknown>): AccessContextSnapshot {
  return {
    activeProjectId: asString(payload.active_project_id),
    activeFamilyId: asString(payload.active_family_id),
    packageLane: asString(payload.package_lane),
    experienceMode: asString(payload.experience_mode)
  };
}

function sortedOrders(items: OrderPayload[]): OrderPayload[] {
  return [...items]
    .sort((left, right) => {
      const leftDate = Date.parse(asString(left.created_at) || '');
      const rightDate = Date.parse(asString(right.created_at) || '');

      if (!Number.isNaN(leftDate) && !Number.isNaN(rightDate)) {
        return rightDate - leftDate;
      }

      if (!Number.isNaN(rightDate)) {
        return 1;
      }

      if (!Number.isNaN(leftDate)) {
        return -1;
      }

      return 0;
    });
}

export default function BillingScreen() {
  const [isLoading, setIsLoading] = useState(true);
  const [isOpeningPortal, setIsOpeningPortal] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');

  const [accessContext, setAccessContext] = useState<AccessContextSnapshot | null>(null);
  const [billingOverview, setBillingOverview] = useState<BillingOverviewPayload | null>(null);
  const [billingConfig, setBillingConfig] = useState<BillingConfigPayload | null>(null);
  const [orders, setOrders] = useState<OrderPayload[]>([]);
  const [notes, setNotes] = useState<string[]>([]);
  const [lastUpdatedAt, setLastUpdatedAt] = useState('');

  const mountedRef = useRef(true);
  const requestSequence = useRef(0);

  const loadBilling = useCallback(async () => {
    const requestId = requestSequence.current + 1;
    requestSequence.current = requestId;

    setIsLoading(true);
    setErrorMessage('');
    setNotes([]);

    try {
      const contextPayload = await fetchAccessContext();

      if (!mountedRef.current || requestId !== requestSequence.current) {
        return;
      }

      const context = summarizeContext(asRecord(contextPayload));
      setAccessContext(context);

      const [configResult, overviewResult, ordersResult] = await Promise.allSettled([
        fetchBillingConfig(),
        fetchBillingOverview(),
        fetchMyOrders()
      ]);

      if (!mountedRef.current || requestId !== requestSequence.current) {
        return;
      }

      const responseNotes: string[] = [];

      if (configResult.status === 'fulfilled') {
        setBillingConfig(configResult.value);
      } else {
        setBillingConfig(null);
        responseNotes.push(`Billing config unavailable: ${mapWorkspaceDataError(configResult.reason)}`);
      }

      if (overviewResult.status === 'fulfilled') {
        setBillingOverview(overviewResult.value);
      } else {
        setBillingOverview(null);
        responseNotes.push(`Billing overview unavailable: ${mapWorkspaceDataError(overviewResult.reason)}`);
      }

      if (ordersResult.status === 'fulfilled') {
        setOrders(sortedOrders(ordersResult.value));
      } else {
        setOrders([]);
        responseNotes.push(`Order history unavailable: ${mapWorkspaceDataError(ordersResult.reason)}`);
      }

      setLastUpdatedAt(new Date().toISOString());
      setNotes(responseNotes);
    } catch (error) {
      if (!mountedRef.current || requestId !== requestSequence.current) {
        return;
      }

      setErrorMessage(mapWorkspaceDataError(error));
      setAccessContext(null);
      setBillingOverview(null);
      setBillingConfig(null);
      setOrders([]);
      setNotes([]);
      setLastUpdatedAt('');
    } finally {
      if (mountedRef.current && requestId === requestSequence.current) {
        setIsLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    void loadBilling();

    return () => {
      mountedRef.current = false;
    };
  }, [loadBilling]);

  const openBillingPortal = useCallback(async () => {
    if (isOpeningPortal) {
      return;
    }

    setIsOpeningPortal(true);

    try {
      const payload = await createBillingPortalSession();
      const url = asString(payload.url);
      if (!url) {
        throw new Error('Billing portal session did not return a URL.');
      }

      const canOpen = await Linking.canOpenURL(url);
      if (!canOpen) {
        throw new Error('This device cannot open the returned billing portal URL.');
      }

      await Linking.openURL(url);
    } catch (error) {
      Alert.alert('Billing Portal Unavailable', mapWorkspaceDataError(error));
    } finally {
      setIsOpeningPortal(false);
    }
  }, [isOpeningPortal]);

  const paymentMethods = Array.isArray(billingOverview?.payment_methods) ? billingOverview.payment_methods : [];
  const subscriptions = Array.isArray(billingOverview?.subscriptions) ? billingOverview.subscriptions : [];

  return (
    <ScreenContainer>
      <WorkspaceHero
        title="Billing"
        description="Payment methods, subscription coverage, and order history from your authenticated Tomb of Light account."
        contextLine={accessContext?.activeProjectId ? `Project ${accessContext.activeProjectId}` : undefined}
      />

      <Pressable
        style={[styles.refreshButton, isLoading && styles.refreshButtonDisabled]}
        onPress={() => void loadBilling()}
        disabled={isLoading || isOpeningPortal}
        accessibilityRole="button"
        accessibilityLabel="Refresh billing"
      >
        <Text style={styles.refreshText}>{isLoading ? 'Refreshing...' : 'Refresh Billing Data'}</Text>
      </Pressable>

      {isLoading ? (
        <DataStateCard
          kind="loading"
          title="Loading billing"
          message="Fetching payment method summary, subscription coverage, and recent order history."
        />
      ) : null}

      {!isLoading && errorMessage ? (
        <DataStateCard
          kind="error"
          title="Unable to load billing"
          message={errorMessage}
          actionLabel="Retry"
          onAction={() => void loadBilling()}
          actionDisabled={isOpeningPortal}
        />
      ) : null}

      {!isLoading && !errorMessage && !accessContext ? (
        <DataStateCard
          kind="empty"
          title="No billing context available"
          message="Account workspace context is unavailable for billing in this session."
          actionLabel="Refresh"
          onAction={() => void loadBilling()}
          actionDisabled={isOpeningPortal}
        />
      ) : null}

      {!isLoading && !errorMessage && accessContext ? (
        <>
          <SectionCard title="Billing Context" subtitle="Current package/workspace context tied to billing records.">
            <View style={styles.rows}>
              <KeyValueRow label="Package Lane" value={toHumanLabel(accessContext.packageLane || 'unknown')} />
              <KeyValueRow label="Experience Mode" value={toHumanLabel(accessContext.experienceMode || 'unknown')} />
              <KeyValueRow label="Active Project ID" value={accessContext.activeProjectId || 'Unavailable'} />
              <KeyValueRow label="Customer ID" value={asString(billingOverview?.customer_id) || 'Unavailable'} />
              <KeyValueRow label="Cards On File" value={String(billingOverview?.cards_on_file ?? 0)} />
              <KeyValueRow label="Last Updated" value={formatTimestamp(lastUpdatedAt, 'Unavailable')} />
            </View>

            <View style={styles.chipRow}>
              <WorkspaceChip
                label={billingOverview?.can_add_card ? 'Can Add Card' : 'Card Limit Reached'}
                tone={billingOverview?.can_add_card ? 'success' : 'warning'}
              />
              <WorkspaceChip
                label={`Max Cards ${typeof billingOverview?.max_cards === 'number' ? billingOverview.max_cards : 0}`}
                tone="muted"
              />
              <WorkspaceChip
                label={`Subscriptions ${subscriptions.length}`}
                tone="accent"
              />
            </View>
          </SectionCard>

          <SectionCard title="Payment Methods" subtitle="Current payment methods visible in your billing profile.">
            {paymentMethods.length > 0 ? (
              paymentMethods.map((method) => (
                <View key={asString(method.id) || `${asString(method.brand)}-${asString(method.last4)}`} style={styles.rowCard}>
                  <Text style={styles.rowTitle}>
                    {toHumanLabel(asString(method.brand) || 'card')} •••• {asString(method.last4) || '0000'}
                  </Text>
                  <Text style={styles.rowMeta}>
                    Expires: {asString(method.exp_month) || '--'}/{asString(method.exp_year) || '--'}
                  </Text>
                  <Text style={styles.rowMeta}>Funding: {toHumanLabel(asString(method.funding) || 'unknown')}</Text>
                  <View style={styles.chipRow}>
                    {method.is_default ? <WorkspaceChip label="Default" tone="success" /> : null}
                    <WorkspaceChip label={`Added ${formatTimestamp(method.created_at, 'Unknown')}`} tone="muted" />
                  </View>
                </View>
              ))
            ) : (
              <DataStateCard
                kind="empty"
                title="No payment methods"
                message="No payment methods were returned in the current billing overview payload."
              />
            )}
          </SectionCard>

          <SectionCard title="Subscriptions" subtitle="Service coverage associated with this account.">
            {subscriptions.length > 0 ? (
              subscriptions.map((subscription) => (
                <View key={asString(subscription.id) || asString(subscription.status)} style={styles.rowCard}>
                  <Text style={styles.rowTitle}>Subscription {asString(subscription.id) || 'Unknown'}</Text>
                  <Text style={styles.rowMeta}>Status: {toHumanLabel(asString(subscription.status) || 'unknown')}</Text>
                  <Text style={styles.rowMeta}>
                    Period Ends: {formatTimestamp(subscription.current_period_end, 'Unavailable')}
                  </Text>
                  <Text style={styles.rowMeta}>
                    Collection: {toHumanLabel(asString(subscription.collection_method) || 'unknown')}
                  </Text>
                  <View style={styles.chipRow}>
                    {Boolean(subscription.cancel_at_period_end) ? (
                      <WorkspaceChip label="Cancel At Period End" tone="warning" />
                    ) : (
                      <WorkspaceChip label="Renews Automatically" tone="success" />
                    )}
                    {Array.isArray(subscription.product_names) && subscription.product_names.length > 0 ? (
                      subscription.product_names.slice(0, 2).map((name) => (
                        <WorkspaceChip key={name} label={name} tone="muted" />
                      ))
                    ) : (
                      <WorkspaceChip label="No product names returned" tone="muted" />
                    )}
                  </View>
                </View>
              ))
            ) : (
              <DataStateCard
                kind="empty"
                title="No subscriptions returned"
                message="No active subscription records were included in the billing overview response."
              />
            )}
          </SectionCard>

          <SectionCard title="Recent Orders" subtitle="Order history from /orders/my-orders for this account.">
            {orders.length > 0 ? (
              orders.slice(0, 8).map((order) => (
                <View key={asString(order.id) || `${asString(order.package_code)}-${asString(order.created_at)}`} style={styles.rowCard}>
                  <Text style={styles.rowTitle}>{asString(order.package_name) || 'Tomb of Light Package'}</Text>
                  <Text style={styles.rowMeta}>Status: {toHumanLabel(asString(order.status) || 'unknown')}</Text>
                  <Text style={styles.rowMeta}>Price: {asString(order.price_label) || 'Unavailable'}</Text>
                  <Text style={styles.rowMeta}>Source: {toHumanLabel(asString(order.source) || 'unknown')}</Text>
                  <Text style={styles.rowMeta}>Created: {formatTimestamp(order.created_at, 'Unavailable')}</Text>
                </View>
              ))
            ) : (
              <DataStateCard
                kind="empty"
                title="No order history"
                message="No order records were returned for this account yet."
              />
            )}
          </SectionCard>

          {notes.length > 0 ? (
            <SectionCard title="Data Notes" subtitle="Non-blocking billing route limitations captured during refresh.">
              {notes.map((note) => (
                <Text key={note} style={styles.noteLine}>
                  - {note}
                </Text>
              ))}
            </SectionCard>
          ) : null}

          <SectionCard title="Actions" subtitle="Open secure billing portal or contact support.">
            <View style={styles.actions}>
              <Pressable
                style={[styles.primaryButton, isOpeningPortal && styles.buttonDisabled]}
                onPress={() => void openBillingPortal()}
                disabled={isOpeningPortal}
                accessibilityRole="button"
                accessibilityLabel="Open secure billing portal"
              >
                <Text style={styles.primaryButtonText}>
                  {isOpeningPortal ? 'Opening Portal...' : 'Open Secure Billing Portal'}
                </Text>
              </Pressable>

              <Link href="/(app)/support" asChild>
                <Pressable style={styles.secondaryButton} accessibilityRole="button" accessibilityLabel="Open support">
                  <Text style={styles.secondaryButtonText}>Open Billing Support</Text>
                </Pressable>
              </Link>
            </View>
          </SectionCard>
        </>
      ) : null}
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  refreshButton: {
    alignSelf: 'flex-start',
    backgroundColor: appTheme.colors.primary,
    borderRadius: appTheme.radius.md,
    minHeight: 44,
    justifyContent: 'center',
    paddingVertical: 10,
    paddingHorizontal: 16
  },
  refreshButtonDisabled: {
    opacity: 0.72
  },
  refreshText: {
    color: appTheme.colors.surface,
    fontSize: appTheme.typography.caption,
    fontWeight: '700'
  },
  rows: {
    gap: appTheme.spacing.sm
  },
  rowCard: {
    borderWidth: 1,
    borderColor: appTheme.colors.border,
    borderRadius: appTheme.radius.md,
    backgroundColor: '#FAFCFF',
    padding: appTheme.spacing.sm,
    gap: 2
  },
  rowTitle: {
    color: appTheme.colors.textPrimary,
    fontSize: appTheme.typography.body,
    fontWeight: '600'
  },
  rowMeta: {
    color: appTheme.colors.textSecondary,
    fontSize: appTheme.typography.caption,
    lineHeight: 18
  },
  chipRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: appTheme.spacing.xs,
    marginTop: 4
  },
  noteLine: {
    color: appTheme.colors.textSecondary,
    fontSize: appTheme.typography.body,
    lineHeight: 22
  },
  actions: {
    gap: appTheme.spacing.sm
  },
  primaryButton: {
    backgroundColor: appTheme.colors.primary,
    borderRadius: appTheme.radius.md,
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: 46,
    paddingVertical: 12
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
    minHeight: 46,
    paddingVertical: 12
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
