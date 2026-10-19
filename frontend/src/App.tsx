import { createBrowserRouter, Link, Outlet, useLocation } from 'react-router'
import { RouterProvider } from 'react-router/dom'

import { LocationSelector } from './components/LocationSelector'
import { CodePage } from './pages/CodePage'
import { IndexPage } from './pages/IndexPage'

function Layout() {
  const { search } = useLocation()
  return (
    <>
      <header className="app-header">
        <h1 className="app-title">
          {/* Keeps ?location= so going home doesn't reset the filter. */}
          <Link to={{ pathname: '/', search }}>Snacker Tracker</Link>
        </h1>
        <LocationSelector />
      </header>
      <main className="app-main">
        <Outlet />
      </main>
    </>
  )
}

const router = createBrowserRouter([
  {
    element: <Layout />,
    children: [
      { path: '/', element: <IndexPage /> },
      { path: '/codes/:code', element: <CodePage /> },
    ],
  },
])

export default function App() {
  return <RouterProvider router={router} />
}
