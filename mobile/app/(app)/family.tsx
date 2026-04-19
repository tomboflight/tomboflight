import React from 'react';

import { FeaturePlaceholderScreen } from '../../src/components/FeaturePlaceholderScreen';

export default function FamilyScreen() {
  return (
    <FeaturePlaceholderScreen
      title="Family"
      description="Family records starter for customer-facing household visibility."
      todoItems={[
        'TODO: Fetch family records from FastAPI.',
        'TODO: Add member list and profile drill-down.',
        'TODO: Enforce workspace role visibility (billing_owner/co_owner/family_manager).'
      ]}
    />
  );
}
