import React from 'react';

import { FeaturePlaceholderScreen } from '../../src/components/FeaturePlaceholderScreen';

export default function TreeScreen() {
  return (
    <FeaturePlaceholderScreen
      title="Family Tree Viewer"
      description="Mobile tree view entry point for lineage exploration."
      todoItems={[
        'TODO: Load tree graph payload from FastAPI.',
        'TODO: Add pan/zoom interactions for mobile.',
        'TODO: Support node detail expansion.'
      ]}
    />
  );
}
