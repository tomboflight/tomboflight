import React from 'react';

import { FeaturePlaceholderScreen } from '../../src/components/FeaturePlaceholderScreen';

export default function CertificatesScreen() {
  return (
    <FeaturePlaceholderScreen
      title="Certificates"
      description="Customer certificate and lineage proof access screen."
      todoItems={[
        'Fetch available certificate metadata from FastAPI.',
        'Support secure file preview/download handoff flow.',
        'Add certificate validity and issuance timeline details.'
      ]}
    />
  );
}
