/**
 * src/pages/HomePage.jsx
 */

import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function HomePage() {
  const { isAuthenticated, isDriver } = useAuth();

  return (
    <div className="ff-home">
      <section className="ff-home__hero">
        <div className="ff-home__hero-text">
          <h1>
            Your ride, <span className="ff-accent">fasta.</span>
          </h1>
          <p>
            Request a ride in seconds, watch your driver arrive on a live map, and pay
            however you like — cash, wallet, or card.
          </p>

          <div className="ff-home__cta">
            {isAuthenticated ? (
              <Link to={isDriver ? "/driver" : "/rider"} className="ff-btn ff-btn--primary ff-btn--lg">
                Go to dashboard
              </Link>
            ) : (
              <>
                <Link to="/register" className="ff-btn ff-btn--primary ff-btn--lg">
                  Request a ride
                </Link>
                <Link to="/register?role=DRIVER" className="ff-btn ff-btn--outline ff-btn--lg">
                  Drive with FastaFasta
                </Link>
              </>
            )}
          </div>
        </div>

        <div className="ff-home__hero-art" aria-hidden="true">
          <div className="ff-home__map-mock">
            <div className="ff-home__pin ff-home__pin--pickup" />
            <div className="ff-home__pin ff-home__pin--drop" />
            <div className="ff-home__route" />
            <div className="ff-home__car">🚗</div>
          </div>
        </div>
      </section>

      <section className="ff-home__features">
        <div className="ff-feature">
          <div className="ff-feature__icon">📍</div>
          <h3>Live tracking</h3>
          <p>Watch your driver move toward you in real time, right on the map.</p>
        </div>
        <div className="ff-feature">
          <div className="ff-feature__icon">💸</div>
          <h3>Upfront fares</h3>
          <p>Know the price before you book — no surprises at drop-off.</p>
        </div>
        <div className="ff-feature">
          <div className="ff-feature__icon">⚡</div>
          <h3>Fast matching</h3>
          <p>We find the nearest available driver to your pickup point instantly.</p>
        </div>
        <div className="ff-feature">
          <div className="ff-feature__icon">⭐</div>
          <h3>Rated community</h3>
          <p>Every trip is rated both ways to keep the platform safe and friendly.</p>
        </div>
      </section>
    </div>
  );
}
