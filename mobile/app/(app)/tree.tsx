import React from 'react';

import { FeaturePlaceholderScreen } from '../../src/components/FeaturePlaceholderScreen';

export default function TreeScreen() {
  return (
    <FeaturePlaceholderScreen
      title="Family Tree Viewer"
      description="Dedicated entry point for visual genealogy tree rendering on mobile."
      todoItems={[
        'Load tree graph payload from FastAPI.',
        'Add pan/zoom optimized rendering for mobile screens.',
        'Support node details and relationship drill-down interactions.'
      ]}
    />
  );
}
