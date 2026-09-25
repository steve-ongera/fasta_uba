/**
 * src/services/api.js
 * Central axios instance for all REST calls to the Django backend, plus
 * every endpoint the app needs wrapped as a plain function so components
 * never construct URLs by hand.
 */

import axios from "axios";

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api";

const ACCESS_KEY = "ff_access_token";
const REFRESH_KEY = "ff_refresh_token";

export const tokenStore = {
  getAccess: () => localStorage.getItem(ACCESS_KEY),
  getRefresh: () => localStorage.getItem(REFRESH_KEY),
  set: (access, refresh) => {
    localStorage.setItem(ACCESS_KEY, access);
    if (refresh) localStorage.setItem(REFRESH_KEY, refresh);
  },
  clear: () => {
    localStorage.removeItem(ACCESS_KEY);
    localStorage.removeItem(REFRESH_KEY);
  },
};

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: { "Content-Type": "application/json" },
});

// attach access token to every request
api.interceptors.request.use((config) => {
  const token = tokenStore.getAccess();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// auto-refresh on 401, retry the original request once
let isRefreshing = false;
let queue = [];

const flushQueue = (error, token = null) => {
  queue.forEach(({ resolve, reject }) => (error ? reject(error) : resolve(token)));
  queue = [];
};

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    if (error.response?.status === 401 && !originalRequest._retry && tokenStore.getRefresh()) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          queue.push({ resolve, reject });
        }).then((token) => {
          originalRequest.headers.Authorization = `Bearer ${token}`;
          return api(originalRequest);
        });
      }

      originalRequest._retry = true;
      isRefreshing = true;

      try {
        const { data } = await axios.post(`${API_BASE_URL}/auth/token/refresh/`, {
          refresh: tokenStore.getRefresh(),
        });
        tokenStore.set(data.access, tokenStore.getRefresh());
        flushQueue(null, data.access);
        originalRequest.headers.Authorization = `Bearer ${data.access}`;
        return api(originalRequest);
      } catch (refreshError) {
        flushQueue(refreshError, null);
        tokenStore.clear();
        window.location.href = "/login";
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }

    return Promise.reject(error);
  }
);

export default api;

// ---------------------------------------------------------------------------
// AUTH
// ---------------------------------------------------------------------------

export const authAPI = {
  register: (payload) => api.post("/auth/register/", payload).then((r) => r.data),
  login: (payload) => api.post("/auth/login/", payload).then((r) => r.data),
  logout: () => api.post("/auth/logout/", { refresh: tokenStore.getRefresh() }).then((r) => r.data),
  me: () => api.get("/auth/me/").then((r) => r.data),
};

// ---------------------------------------------------------------------------
// FARE
// ---------------------------------------------------------------------------

export const fareAPI = {
  estimate: (payload) => api.post("/fare/estimate/", payload).then((r) => r.data),
};

// ---------------------------------------------------------------------------
// DRIVER
// ---------------------------------------------------------------------------

export const driverAPI = {
  setStatus: (status) => api.post("/driver/status/", { status }).then((r) => r.data),
  updateLocation: (lat, lng, heading) =>
    api.post("/driver/location/", { lat, lng, heading }).then((r) => r.data),
  earnings: () => api.get("/driver/earnings/").then((r) => r.data),
  pendingOffer: () => api.get("/driver/offers/pending/").then((r) => r.data),
  respondToOffer: (offerId, action) =>
    api.post(`/driver/offers/${offerId}/respond/`, { action }).then((r) => r.data),
};

// ---------------------------------------------------------------------------
// SAVED PLACES
// ---------------------------------------------------------------------------

export const placesAPI = {
  list: () => api.get("/places/").then((r) => r.data),
  create: (payload) => api.post("/places/", payload).then((r) => r.data),
  remove: (id) => api.delete(`/places/${id}/`).then((r) => r.data),
};

// ---------------------------------------------------------------------------
// TRIPS
// ---------------------------------------------------------------------------

export const tripAPI = {
  request: (payload) => api.post("/trips/request/", payload).then((r) => r.data),
  active: () => api.get("/trips/active/").then((r) => r.data),
  history: (page = 1) => api.get(`/trips/history/?page=${page}`).then((r) => r.data),
  detail: (tripId) => api.get(`/trips/${tripId}/`).then((r) => r.data),
  arrive: (tripId) => api.post(`/trips/${tripId}/arrive/`).then((r) => r.data),
  start: (tripId) => api.post(`/trips/${tripId}/start/`).then((r) => r.data),
  complete: (tripId) => api.post(`/trips/${tripId}/complete/`).then((r) => r.data),
  cancel: (tripId, reason = "") => api.post(`/trips/${tripId}/cancel/`, { reason }).then((r) => r.data),
};

// ---------------------------------------------------------------------------
// PAYMENTS
// ---------------------------------------------------------------------------

export const paymentAPI = {
  detail: (tripId) => api.get(`/trips/${tripId}/payment/`).then((r) => r.data),
  confirm: (tripId, transactionRef) =>
    api.post(`/trips/${tripId}/payment/confirm/`, { transaction_ref: transactionRef }).then((r) => r.data),
};

// ---------------------------------------------------------------------------
// RATINGS
// ---------------------------------------------------------------------------

export const ratingAPI = {
  rate: (tripId, score, comment = "") =>
    api.post("/ratings/", { trip: tripId, score, comment }).then((r) => r.data),
};

// ---------------------------------------------------------------------------
// NOTIFICATIONS
// ---------------------------------------------------------------------------

export const notificationAPI = {
  list: () => api.get("/notifications/").then((r) => r.data),
  markRead: (id) => api.post(`/notifications/${id}/read/`).then((r) => r.data),
};
