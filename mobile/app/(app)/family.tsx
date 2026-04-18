import React from 'react';

import { FeaturePlaceholderScreen } from '../../src/components/FeaturePlaceholderScreen';

export default function FamilyScreen() {
  return (
    <FeaturePlaceholderScreen
      title="Family"
      description="Customer-facing family records overview and member context starter screen."
      todoItems={[
        'Fetch family entity summaries from FastAPI.',
        'Support member list navigation and relationship quick views.',
        'Introduce access controls for household-level visibility.'
      ]}
    />
  );
}
