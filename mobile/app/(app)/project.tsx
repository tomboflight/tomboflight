import React from 'react';

import { FeaturePlaceholderScreen } from '../../src/components/FeaturePlaceholderScreen';

export default function ProjectScreen() {
  return (
    <FeaturePlaceholderScreen
      title="Project Summary"
      description="Project summary starter for milestones and scope context."
      todoItems={[
        'TODO: Pull project summary from FastAPI.',
        'TODO: Render milestone timeline.',
        'TODO: Attach project update notifications.'
      ]}
    />
  );
}
