import { useEffect, useState } from 'react';
import { MapContainer, TileLayer, GeoJSON, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import './index.css';

interface PipelineResult {
  weather_data: {
    past_3_days_precipitation_mm: number[];
    actual_today_precipitation_mm: number;
    predicted_precipitation_mm: number;
    design_rainfall_used_mm: number;
  };
  model_parameters: { cn: number; lambda_ia: number; };
  simulation: {
    runoff_mm: number;
    inflow_volume_m3: number;
    dam_water_level_increase_meters: number;
  };
  alert: { level: string; color: string; message: string; };
}

function MapUpdater({ geojson, color, weight, fillOpacity }: { geojson: any, color: string, weight?: number, fillOpacity?: number }) {
  if (!geojson) return null;
  return (
    <GeoJSON 
       data={geojson} 
       style={(feature) => {
         const val = feature?.properties?.DN || 1;
         let resolvedColor = color;
         if (color === 'STREAM_LOGIC') {
            resolvedColor = val == 1 ? "#ffffb2" : val == 2 ? "#fecc5c" : val == 3 ? "#fd8d3c" : val == 4 ? "#f03b20" : "#bd0026";
         }
         else if (color === 'LULC_LOGIC') {
            resolvedColor = val == 1 ? "blue" : val == 2 ? "green" : val == 3 ? "yellow" : val == 4 ? "red" : val == 5 ? "brown" : "gray";
         }
         return { color: resolvedColor, weight: weight || 2, fillOpacity: fillOpacity || 0.1 };
       }}
    />
  );
}

export default function App() {
  const [pipeline, setPipeline] = useState<PipelineResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [activeLayers, setActiveLayers] = useState({
    watershed: true,
    streams: false,
    dem: false,
    filledDem: false,
    lulc: false
  });

  const [geoData, setGeoData] = useState<any>({});

  useEffect(() => {
    // Load static files
    const loadGeoJson = async (name: string, path: string) => {
      try {
        const res = await fetch(path);
        const data = await res.json();
        setGeoData(prev => ({...prev, [name]: data}));
      } catch (e) {
        console.error("Failed to load", path);
      }
    };
    
    // Using the copied paths
    loadGeoJson('watershed', '/data/GIS/our-catchment-area-new.geojson');
    loadGeoJson('streams', '/data/GIS/stream-order-new.geojson');
    loadGeoJson('dem', '/data/GIS/dem-new.geojson');
    loadGeoJson('filledDem', '/data/GIS/filled-dem-new.geojson');
    loadGeoJson('lulc', '/data/GIS/lulc-vectorized-new.geojson');
  }, []);

  const API_BASE = import.meta.env.VITE_API_URL || '';

  const runPipeline = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/pipeline`);
      const data = await res.json();
      setPipeline(data);
    } catch(e) {
      console.error(e);
      alert('Failed to run pipeline. Is the backend running?');
    }
    setLoading(false);
  };

  const toggleLayer = (layer: keyof typeof activeLayers) => {
    setActiveLayers(prev => ({...prev, [layer]: !prev[layer]}));
  };

  return (
    <div className="app-container">
      {/* Main Panel */}
      <main className="main-content">
        <header className="header-banner">
          <div>
            <h1>Himayat Sagar Flood Detection Core</h1>
            <p>Advanced Sensor & Satellite Intelligence Dashboard</p>
          </div>
          <button className="run-btn" onClick={runPipeline} disabled={loading}>
            {loading ? 'Simulating...' : 'RUN LIVE PIPELINE'}
          </button>
        </header>

        {pipeline && (
          <div className={`alert-banner animate-fade-in alert-${pipeline.alert.level}`}>
            <div style={{fontSize: '2rem'}}>
               {pipeline.alert.level === 'CRITICAL' ? '⚠️' : pipeline.alert.level === 'WARNING' ? '⚠️' : '✅'}
            </div>
            <div>
              <h3 style={{marginBottom: '0.25rem'}}>SYSTEM ALERT: {pipeline.alert.level}</h3>
              <p style={{color: 'inherit', margin:0}}>{pipeline.alert.message}</p>
            </div>
          </div>
        )}

        <div className="glass-panel" style={{padding: 0, overflow: 'hidden'}}>
          <MapContainer center={[17.33, 78.30]} zoom={11} id="map">
            <TileLayer url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png" attribution="CARTO" />
            
            {activeLayers.watershed && geoData.watershed && <MapUpdater geojson={geoData.watershed} color="#3b82f6" fillOpacity={0.2} />}
            {activeLayers.streams && geoData.streams && <MapUpdater geojson={geoData.streams} color="STREAM_LOGIC" weight={2} />}
            {activeLayers.dem && geoData.dem && <MapUpdater geojson={geoData.dem} color="#8B4513" weight={0.5} fillOpacity={0.4} />}
            {activeLayers.filledDem && geoData.filledDem && <MapUpdater geojson={geoData.filledDem} color="#8B0000" weight={0.5} fillOpacity={0.3} />}
            {activeLayers.lulc && geoData.lulc && <MapUpdater geojson={geoData.lulc} color="LULC_LOGIC" weight={1} fillOpacity={0.4} />}
          </MapContainer>
        </div>
      </main>

      {/* Sidebar Panel */}
      <aside className="sidebar">
        
        <div className="glass-panel">
          <h2>Map Layers</h2>
          <div className="layer-controls">
            <label className="layer-toggle">
              <input type="checkbox" checked={activeLayers.watershed} onChange={() => toggleLayer('watershed')} />
              Watershed Boundary
            </label>
            <label className="layer-toggle">
              <input type="checkbox" checked={activeLayers.streams} onChange={() => toggleLayer('streams')} />
              Stream Orders
            </label>
            <label className="layer-toggle">
              <input type="checkbox" checked={activeLayers.dem} onChange={() => toggleLayer('dem')} />
              Raw DEM
            </label>
            <label className="layer-toggle">
              <input type="checkbox" checked={activeLayers.filledDem} onChange={() => toggleLayer('filledDem')} />
              Filled DEM
            </label>
            <label className="layer-toggle">
              <input type="checkbox" checked={activeLayers.lulc} onChange={() => toggleLayer('lulc')} />
              Geographic LULC
            </label>
          </div>
        </div>

        {pipeline ? (
           <div className="glass-panel animate-fade-in">
             <h2>Live Simulation Stats</h2>
             <hr style={{borderColor: 'rgba(255,255,255,0.1)', margin: '1rem 0'}}/>
             
             <h3>Precipitation Data</h3>
             <div className="data-grid">
               <div className="data-item">
                 <span>Today's Rain</span>
                 <strong>{pipeline.weather_data.actual_today_precipitation_mm.toFixed(1)} mm</strong>
               </div>
               <div className="data-item">
                 <span>AR Predicted</span>
                 <strong style={{color: '#c084fc'}}>{pipeline.weather_data.predicted_precipitation_mm.toFixed(1)} mm</strong>
               </div>
             </div>

             <h3 style={{marginTop: '1.5rem'}}>CS-SCN Runoff Model</h3>
             <div className="data-grid">
               <div className="data-item">
                 <span>Opt. Curve Number</span>
                 <strong>{pipeline.model_parameters.cn.toFixed(2)}</strong>
               </div>
               <div className="data-item">
                 <span>Peak Runoff</span>
                 <strong style={{color: '#38bdf8'}}>{pipeline.simulation.runoff_mm.toFixed(2)} mm</strong>
               </div>
             </div>

             <h3 style={{marginTop: '1.5rem'}}>Reservoir Impact</h3>
             <div className="data-grid" style={{gridTemplateColumns: '1fr'}}>
               <div className="data-item" style={{background: 'rgba(56, 189, 248, 0.1)', border: '1px solid rgba(56, 189, 248, 0.3)'}}>
                 <span style={{color: '#bae6fd'}}>Est. Dam Water Level Increase</span>
                 <strong style={{fontSize: '2rem', color: '#e0f2fe'}}>{pipeline.simulation.dam_water_level_increase_meters.toFixed(2)} m</strong>
               </div>
             </div>
           </div>
        ) : (
           <div className="glass-panel" style={{textAlign: 'center', opacity: 0.6}}>
             <h2 style={{fontSize:'1.2rem'}}>Awaiting Signal</h2>
             <p>Press "Run Live Pipeline" to start fetching real-time data and simulating dam impact.</p>
           </div>
        )}
      </aside>
    </div>
  );
}
