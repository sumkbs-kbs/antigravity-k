import React, { lazy, Suspense } from 'react';
import { Route, Routes } from 'react-router-dom';
import { usePluginRegistry } from './pluginRegistry';

const JobOperationsPage = lazy(() => import('../features/job-operations/JobOperationsPage').then(module => ({ default: module.JobOperationsPage })));

const PluginPanelRoutes: React.FC = () => {
  const panels = usePluginRegistry(s => s.panels);

  return (
    <Routes>
      <Route path="job-operations" element={<Suspense fallback={<p>Loading job operations…</p>}><JobOperationsPage /></Suspense>} />
      {panels.map(panel => (
        <Route
          key={panel.path}
          path={panel.path.replace('/plugins/', '')}
          element={<panel.component />}
        />
      ))}
    </Routes>
  );
};

export default PluginPanelRoutes;
