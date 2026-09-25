/**
 * src/App.jsx
 * Top-level route table. Rider and driver areas are role-gated by
 * <ProtectedRoute role="RIDER" | "DRIVER">.
 */

import { Route, Routes } from "react-router-dom";

import Navbar from "./components/layout/Navbar.jsx";
import ProtectedRoute from "./components/layout/ProtectedRoute.jsx";

import HomePage from "./pages/HomePage.jsx";
import LoginPage from "./pages/LoginPage.jsx";
import RegisterPage from "./pages/RegisterPage.jsx";
import NotFound from "./pages/NotFound.jsx";

import RiderDashboard from "./pages/rider/RiderDashboard.jsx";
import RideTracking from "./pages/rider/RideTracking.jsx";
import RideHistory from "./pages/rider/RideHistory.jsx";
import RiderProfile from "./pages/rider/RiderProfile.jsx";

import DriverDashboard from "./pages/driver/DriverDashboard.jsx";
import ActiveTrip from "./pages/driver/ActiveTrip.jsx";
import Earnings from "./pages/driver/Earnings.jsx";
import DriverProfile from "./pages/driver/DriverProfile.jsx";

export default function App() {
  return (
    <div className="ff-app">
      <Navbar />

      <main className="ff-app__main">
        <Routes>
          {/* public */}
          <Route path="/" element={<HomePage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />

          {/* rider */}
          <Route
            path="/rider"
            element={
              <ProtectedRoute role="RIDER">
                <RiderDashboard />
              </ProtectedRoute>
            }
          />
          <Route
            path="/rider/trip/:tripId"
            element={
              <ProtectedRoute role="RIDER">
                <RideTracking />
              </ProtectedRoute>
            }
          />
          <Route
            path="/rider/history"
            element={
              <ProtectedRoute role="RIDER">
                <RideHistory />
              </ProtectedRoute>
            }
          />
          <Route
            path="/rider/profile"
            element={
              <ProtectedRoute role="RIDER">
                <RiderProfile />
              </ProtectedRoute>
            }
          />

          {/* driver */}
          <Route
            path="/driver"
            element={
              <ProtectedRoute role="DRIVER">
                <DriverDashboard />
              </ProtectedRoute>
            }
          />
          <Route
            path="/driver/trip/:tripId"
            element={
              <ProtectedRoute role="DRIVER">
                <ActiveTrip />
              </ProtectedRoute>
            }
          />
          <Route
            path="/driver/earnings"
            element={
              <ProtectedRoute role="DRIVER">
                <Earnings />
              </ProtectedRoute>
            }
          />
          <Route
            path="/driver/profile"
            element={
              <ProtectedRoute role="DRIVER">
                <DriverProfile />
              </ProtectedRoute>
            }
          />

          <Route path="*" element={<NotFound />} />
        </Routes>
      </main>
    </div>
  );
}
