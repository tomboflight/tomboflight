import React from 'react';

import { FeaturePlaceholderScreen } from '../../src/components/FeaturePlaceholderScreen';

export default function SupportScreen() {
  return (
    <FeaturePlaceholderScreen
      title="Support"
      description="Customer support starter for help and escalation workflows."
      todoItems={[
        'TODO: Connect support request endpoint.',
        'TODO: Add FAQ and issue categories.',
        'TODO: Capture app/device diagnostics on request.'
      ]}
    />
  );
}
