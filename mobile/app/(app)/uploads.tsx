import React from 'react';

import { FeaturePlaceholderScreen } from '../../src/components/FeaturePlaceholderScreen';

export default function UploadsScreen() {
  return (
    <FeaturePlaceholderScreen
      title="Uploads"
      description="Customer document and media upload center for genealogy project inputs."
      todoItems={[
        'Integrate secure file upload workflow with backend API.',
        'Show upload queue, progress, and failure handling states.',
        'Connect uploaded assets to the correct project and member records.'
      ]}
    />
  );
}
