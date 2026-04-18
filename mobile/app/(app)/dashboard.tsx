import React from 'react';

import { FeaturePlaceholderScreen } from '../../src/components/FeaturePlaceholderScreen';

export default function DashboardScreen() {
  return (
    <FeaturePlaceholderScreen
      title="Dashboard"
      description="Package-lane dashboard starter for customer progress visibility."
      todoItems={[
        'TODO: Load package lane cards from FastAPI.',
        'TODO: Show milestone and activity status.',
        'TODO: Add deep links to project, uploads, and certificates.'
      ]}
    />
  );
}
