import { createBrowserRouter, Link, Outlet, useLocation } from 'react-router'
import { RouterProvider } from 'react-router/dom'

import { BuildFooter } from './components/BuildFooter'
import { LocationSelector } from './components/LocationSelector'
import { ScannersLink } from './components/ScannersLink'
import { CONTRACT_VERSION, type MetaFile } from './contract'
import { metaDataPath, useJson } from './data'
import { CodePage } from './pages/CodePage'
import { IndexPage } from './pages/IndexPage'
import { ScannersPage } from './pages/ScannersPage'

function Layout() {
  const { search } = useLocation()
  const meta = useJson<MetaFile>(metaDataPath())
  // Wait for meta.json before reading any other data file: pages written for another
  // contract version could misread them. If meta.json itself fails, pages say so as usual.
  if (meta.status === 'loading') return null
  const outOfStep = meta.status === 'ready' && meta.data.contract_version !== CONTRACT_VERSION
  return (
    <>
      <header className="app-header">
        <h1 className="app-title">
          {/* Keeps ?location= so going home doesn't reset the filter. */}
          <Link to={{ pathname: '/', search }}>Snacker Tracker</Link>
        </h1>
        {!outOfStep && <LocationSelector />}
        {!outOfStep && <ScannersLink />}
      </header>
      <main className="app-main">
        {outOfStep ? <OutOfStep dataVersion={meta.data.contract_version} /> : <Outlet />}
      </main>
      <BuildFooter stamp={__BUILD_STAMP__} />
    </>
  )
}

/** The data was built to a different contract version than this interface reads. */
function OutOfStep({ dataVersion }: { dataVersion: number | undefined }) {
  return (
    <section className="panel" role="alert" aria-labelledby="out-of-step-heading">
      <h2 id="out-of-step-heading">Data and interface are out of step</h2>
      <p className="status status-error">
        The data was built for contract version {dataVersion ?? 'none (built before versions)'}, but this
        interface reads version {CONTRACT_VERSION}. Rebuild the data or redeploy the interface so they match.
      </p>
    </section>
  )
}

const router = createBrowserRouter([
  {
    element: <Layout />,
    children: [
      { path: '/', element: <IndexPage /> },
      { path: '/codes/:code', element: <CodePage /> },
      { path: '/scanners', element: <ScannersPage /> },
    ],
  },
])

export default function App() {
  return <RouterProvider router={router} />
}
