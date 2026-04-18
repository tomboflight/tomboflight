import React from 'react';

import { FeaturePlaceholderScreen } from '../../src/components/FeaturePlaceholderScreen';

export default function BillingScreen() {
  return (
    <FeaturePlaceholderScreen
      title="Billing Summary"
      description="Billing overview starter for package and payment status."
      todoItems={[
        'TODO: Connect billing summary endpoint from FastAPI.',
        'TODO: Render invoices and payment history.',
        'TODO: Add secure payment handoff flow.'
      ]}
    />
  );
}
