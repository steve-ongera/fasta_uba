import { Link } from "react-router-dom";

export default function NotFound() {
  return (
    <div className="ff-not-found">
      <h1>404</h1>
      <p>This page took a wrong turn.</p>
      <Link to="/" className="ff-btn ff-btn--primary">
        Back home
      </Link>
    </div>
  );
}
