import { PtoWorkspace } from './pto-workspace';

import { getPtoOverview } from '@/lib/api';

export default async function PtoPage() {
  const overview = await getPtoOverview();

  return <PtoWorkspace initialOverview={overview} />;
}
