import React from 'react';

import { FeaturePlaceholderScreen } from '../../src/components/FeaturePlaceholderScreen';

export default function DashboardScreen() {
  return (
    <FeaturePlaceholderScreen
      title="Dashboard"
      description="Package-lane dashboard starter for customer progress visibility."
      todoItems={[
        'TODO: Load access context from /users/me/access-context.',
        'TODO: Load workspace memberships from /workspace-access/my-memberships.',
        'TODO: Show milestone and activity status.',
        'TODO: Add deep links to project, uploads, and certificates.'
      ]}
    />
  );
}
