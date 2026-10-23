# SupplyZero dashboard

React 18, TypeScript, Vite command center for the SupplyZero FastAPI backend.

## Start

Run the FastAPI backend first at `http://localhost:8000`, then open a second PowerShell window:

```powershell
cd "C:\Users\SUYASH SRIVASTAVA\OneDrive\Documents\SupplyZero\frontend"
npm install
npm run dev
```

Open http://127.0.0.1:5173. The frontend defaults to the local API and WebSocket URLs. Override them with `VITE_API_BASE_URL` and `VITE_WS_URL` if the backend runs elsewhere.

## Included

- Responsive fleet command center with category filters, RSL rings, health badges, Leaflet map, and recommendation queue.
- Shipment detail view with safe-band temperature chart, kinetic stress, forecast confidence band, and excursion timeline.
- Scenario drawer for compressor failure, freeze, door-open, heatwave, and telemetry-gap injection.
- Impact modal for saved value, CO₂e, diverted kilograms, and static-label comparison.
- Exponential WebSocket reconnect, 15-second ping / 30-second watchdog, 60-second REST fleet resync, bounded 200-point per-shipment telemetry buffers, and local demo state after three connection failures.
- Widget-level React error boundaries and offline-safe sample state.

The FastAPI server allows local Vite origins and replies to WebSocket heartbeat pings. Restart the backend after updating it.
