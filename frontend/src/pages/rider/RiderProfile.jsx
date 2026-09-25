import { useAuth } from "../../context/AuthContext";

export default function RiderProfile() {
  const { user } = useAuth();
  const rider = user?.rider_profile;

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

        {rider && (
          <div className="ff-fare-summary">
            <div>
              <span>Rating</span>
              <strong>★ {rider.rating_avg}</strong>
            </div>
            <div>
              <span>Total trips</span>
              <strong>{rider.total_trips}</strong>
            </div>
            <div>
              <span>Wallet</span>
              <strong>KES {rider.wallet_balance}</strong>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
