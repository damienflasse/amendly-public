/**
 * App — root component that wraps the route tree in a BrowserRouter.
 *
 * The full route definition lives in AppRoutes.jsx so it can be shared
 * between the client entry (this file + main.jsx) and the server entry
 * (entry-server.jsx) used for prerendering.
 *
 * Props: none
 */

import { BrowserRouter } from 'react-router-dom'
import AppRoutes from './AppRoutes'

export default function App() {
  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  )
}
