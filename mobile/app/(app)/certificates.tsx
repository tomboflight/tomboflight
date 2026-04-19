import React from 'react';

import { FeaturePlaceholderScreen } from '../../src/components/FeaturePlaceholderScreen';

export default function CertificatesScreen() {
  return (
    <FeaturePlaceholderScreen
      title="Certificates"
      description="Customer certificate and lineage proof access starter screen."
      todoItems={[
        'TODO: Load certificate metadata from FastAPI.',
        'TODO: Add secure preview/download flow.',
        'TODO: Show issuance + verification status.'
      ]}
    />
  );
}
