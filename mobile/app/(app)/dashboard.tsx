import React from 'react';

import { FeaturePlaceholderScreen } from '../../src/components/FeaturePlaceholderScreen';

export default function DashboardScreen() {
  return (
    <FeaturePlaceholderScreen
      title="Dashboard"
      description="Customer dashboard lane for package status and high-level progress updates."
      todoItems={[
        'Load customer package lanes from FastAPI backend.',
        'Display timeline/status cards for each package lane.',
        'Add deep links into project, uploads, and certificates.'
      ]}
    />
  );
}
