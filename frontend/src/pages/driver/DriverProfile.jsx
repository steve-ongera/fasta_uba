import { useAuth } from "../../context/AuthContext";

export default function DriverProfile() {
  const { user } = useAuth();
  const driver = user?.driver_profile;

  return (
    <div className="ff-page">
      <h1>My profile</h1>
      <div className="ff-profile-card">
        <div className="ff-driver-card__avatar ff-driver-card__avatar--lg">
          {user?.first_name?.[0] || user?.username?.[0]}
        </div>
        <h2>
          {user?.first_name} {user?.last_name}
        </h2>
        <p>{user?.email}</p>
        <p>{user?.phone_number}</p>

        {driver && (
          <div className="ff-fare-summary">
            <div>
              <span>Rating</span>
              <strong>★ {driver.rating_avg}</strong>
            </div>
            <div>
              <span>Total trips</span>
              <strong>{driver.total_trips}</strong>
            </div>
            <div>
              <span>Vehicle</span>
              <strong>
                {driver.vehicle?.make} {driver.vehicle?.model}
              </strong>
            </div>
            <div>
              <span>Plate</span>
              <strong>{driver.vehicle?.plate_number}</strong>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
