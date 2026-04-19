import React from 'react';

import { FeaturePlaceholderScreen } from '../../src/components/FeaturePlaceholderScreen';

export default function UploadsScreen() {
  return (
    <FeaturePlaceholderScreen
      title="Uploads"
      description="Customer upload center for project documents and media."
      todoItems={[
        'TODO: Integrate upload API with FastAPI using multipart FormData payloads.',
        'TODO: Show upload queue/progress states.',
        'TODO: Link files to project/member records.'
      ]}
    />
  );
}
