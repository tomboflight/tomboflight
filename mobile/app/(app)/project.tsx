import React from 'react';

import { FeaturePlaceholderScreen } from '../../src/components/FeaturePlaceholderScreen';

export default function ProjectScreen() {
  return (
    <FeaturePlaceholderScreen
      title="Project Summary"
      description="Project-level snapshot including milestones, scope, and current progress."
      todoItems={[
        'Fetch project summary payload from FastAPI.',
        'Render milestone and completion indicators.',
        'Attach notifications for project updates.'
      ]}
    />
  );
}
