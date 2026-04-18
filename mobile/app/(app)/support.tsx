import React from 'react';

import { FeaturePlaceholderScreen } from '../../src/components/FeaturePlaceholderScreen';

export default function SupportScreen() {
  return (
    <FeaturePlaceholderScreen
      title="Support"
      description="Customer support entry point for help requests and issue guidance."
      todoItems={[
        'Integrate support ticket submission with FastAPI backend.',
        'Add FAQ and escalation paths for package-specific questions.',
        'Capture device/session metadata for support diagnostics.'
      ]}
    />
  );
}
