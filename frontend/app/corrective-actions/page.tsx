import { CorrectiveActionsWorkspace } from './corrective-actions-workspace';

import { getCorrectiveActions } from '@/lib/api';

export default async function CorrectiveActionsPage() {
  const overview = await getCorrectiveActions();

  return <CorrectiveActionsWorkspace initialOverview={overview} />;
}
