import { createBrowserRouter, Link, Outlet } from 'react-router'
import { RouterProvider } from 'react-router/dom'

import { IndexPage } from './pages/IndexPage'

function Layout() {
  return (
    <>
      <header className="app-header">
        <h1 className="app-title">
          <Link to="/">Snacker Tracker</Link>
        </h1>
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
    children: [{ path: '/', element: <IndexPage /> }],
  },
])

export default function App() {
  return <RouterProvider router={router} />
}
