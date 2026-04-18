import React from 'react';

import { FeaturePlaceholderScreen } from '../../src/components/FeaturePlaceholderScreen';

export default function BillingScreen() {
  return (
    <FeaturePlaceholderScreen
      title="Billing Summary"
      description="Customer billing overview for current package and payment status."
      todoItems={[
        'Load billing summary from FastAPI billing endpoints.',
        'Render invoices, payment history, and next due amount.',
        'Add secure payment handoff or gateway redirect when approved.'
      ]}
    />
  );
}
