// Lightweight cache server for GTFS data
// Returns processed JSON for vehicles positions and updates (delays), protobuf GTFS for alerts

const express = require('express');
const cors = require('cors');
const GtfsRealtimeBindings = require('gtfs-realtime-bindings');
const fetch = require('node-fetch');
const app = express();
const PORT = process.env.PORT || 3000;
const utils = require('./utils.js')
const { loadEnvFile } = require('node:process');
loadEnvFile('.env');

const API_BASE_URL = (
  process.env.BMC_API_BASE_URL || 'https://api-management-discovery-production.azure-api.net'
).replace(/\/+$/, '');

const CONFIG = {
    vehicleUrl: `${API_BASE_URL}/api/gtfs/feed/tec/rt/vehicle-position?format=protobuf`,
    alertUrl: `${API_BASE_URL}/api/gtfs/feed/tec/rt/alert?format=protobuf`,
    updateUrl: `${API_BASE_URL}/api/gtfs/feed/tec/rt/trip-update?format=protobuf`,
    refreshIntervals: {
      vehicles: 30_000,
      alerts: 30_000,
      updates: 30_000
    },
    apiKey: process.env.BMC_PARTNER_KEY || process.env.API_KEY || '',
    verboseLogging: process.env.VERBOSE_LOGGING === 'true'
};

// Cache data into memory
let cachedData = {
    vehicles: null,
    alerts: null,
    alertsRaw: null, //gtfs protobuf
    updates: null,
    delayByTrip: {},
    lastUpdate: {
	vehicles: null,
	alerts: null,
	alertsRaw: null,
	updates: null
  }
};

// ----------------------------------------------------------------------------------
// Activate CORS to allow requests from front-end
app.use(cors());

// Serve and use utils.js as static file
app.use('/utils.js', express.static(__dirname + '/utils.js'));


// Conditional logging
function log(message, force = false) {
  if (CONFIG.verboseLogging || force) {
    console.log(message);
  }
}

function fetchOptions() {
  return {
    headers: {
      'bmc-partner-key': CONFIG.apiKey
    }
  };
}

// ----------------------------------------------------------------------------------
// Get and convert vehicles data from GTFS protobuf to JSON
async function fetchAndConvertVehicles() {
  try {
    log(`[${new Date().toISOString()}] Fetching vehicle data...`);
    const response = await fetch(CONFIG.vehicleUrl, fetchOptions());
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const buffer = await response.arrayBuffer();
    const feed = GtfsRealtimeBindings.transit_realtime.FeedMessage.decode(
      new Uint8Array(buffer)
    );

    // Convert into usable JSON
    const formattedVehicleData = feed.entity.map(entity => {
      if (!entity.vehicle) return null;

      const vehicle = entity.vehicle;
	const position = vehicle.position;
	
      return {
          vehicleId: vehicle.vehicle?.id || entity.id,
	  latitude: position?.latitude || null,
          longitude: position?.longitude || null,
	  speed: position?.speed ?? null,
	  currentStopSequence: vehicle.currentStopSequence || null,
          //timestamp: vehicle.timestamp?.toNumber() || null,
	  stopId: vehicle.stopId || null,
	  trip: vehicle.trip? {
              tripId: vehicle.trip.tripId || null,
              routeId: vehicle.trip.routeId || null,
              //startTime: vehicle.trip.startTime || null,
              //startDate: vehicle.trip.startDate || null,
	      //route_short_name and route_long_name are computed in client who have static gtfs data
	      //route_short_name: utils.getRouteShortName(vehicle.trip.routeId) || null, // TO DO server-side
	      //route_long_name: utils.getRouteLongName(vehicle.trip.routeId) || null,   // TO DO server-side
	  } : null,
	  //agency: vehicle.trip?.routeId?.split("-")[0] || null // agendy id from route id
        //bearing: position?.bearing || null,
        //currentStatus: vehicle.currentStatus || null,
      };
    }).filter(v => v !== null);

    log(formattedVehicleData);
      
    cachedData.vehicles = formattedVehicleData;
    cachedData.lastUpdate.vehicles = new Date();
    
    log(`[${new Date().toISOString()}] Vehicle data updated: ${formattedVehicleData.length} vehicles`);
    
    return formattedVehicleData;
  } catch (error) {
    console.error('Error fetching vehicle data:', error.message);
    return null;
  }
}


// ----------------------------------------------------------------------------------
// Get and convert alert data from the GTFS-Realtime protobuf feed.
async function fetchAndConvertAlerts() {
  try {
    log(`[${new Date().toISOString()}] Fetching alert data...`);
    
    const response = await fetch(CONFIG.alertUrl, fetchOptions());
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const buffer = await response.arrayBuffer();
    cachedData.alertsRaw = buffer;
    cachedData.lastUpdate.alertsRaw = new Date();
    const feed = GtfsRealtimeBindings.transit_realtime.FeedMessage.decode(
      new Uint8Array(buffer)
    );

      const entities = feed.entity
    // Convert into usable JSON
      const formattedAlertData = entities.map(entity => {
      if (!entity.alert) return null;

	  const alert = entity.alert;
	  if (!alert || !Array.isArray(alert.informedEntity)) return;

	  let startDate = ' ';
	  let endDate = ' ';
	  if (alert.activePeriod) {
	      startDate = utils.timestampToDate(alert.activePeriod[0].start);
	      endDate = utils.timestampToDate(alert.activePeriod[0].end);
	  }
	  //here we should extract and convert info from informedEntity for precise cancellation information
	  
      return {
        id: entity.id,
        //activePeriods: alert.activePeriod?.map(period => ({
        //  start: period.start?.toNumber() || null,
        //  end: period.end?.toNumber() || null
        //})) || [],
        //informedEntities: alert.informedEntity?.map(ie => ({
        //  agencyId: ie.agencyId || null,
        //  routeId: ie.routeId || null,
        //  routeType: ie.routeType || null,
        //  tripId: ie.trip?.tripId || null,
        //  stopId: ie.stopId || null
        //})) || [],
        //cause: alert.cause || null,
        //effect: alert.effect || null,
          url: alert.url?.translation?.[0]?.text || null,
	  //tripid: tripid,
	  start: startDate,
	  end: endDate,
	  //starttime: starttime,
	  stops: [],
        //headerText: alert.headerText?.translation?.[0]?.text || null,
	description: alert.descriptionText?.translation?.find(t => t.language === 'fr-be')?.text 
	      || alert.descriptionText?.translation?.[0]?.text 
	      || ''
      };
    }).filter(a => a !== null);

    log(formattedAlertData);
    cachedData.alerts = formattedAlertData;
    cachedData.lastUpdate.alerts = new Date();
    
    log(`[${new Date().toISOString()}] Alert data updated: ${formattedAlertData.length} alerts`);
    
    return formattedAlertData;
  } catch (error) {
    console.error('Error fetching alert data:', error.message);
    return null;
  }
}


// ----------------------------------------------------------------------------------
// Get and convert updates (delays) data from GTFS protobuf to JSON
async function fetchAndConvertUpdates() {
  try {
    log(`[${new Date().toISOString()}] Fetching trip updates data...`);
    
    const response = await fetch(CONFIG.updateUrl, fetchOptions());
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const buffer = await response.arrayBuffer();
    const feed = GtfsRealtimeBindings.transit_realtime.FeedMessage.decode(
      new Uint8Array(buffer)
    );

    // Convert into usable JSON
    const delayByTrip = {};

    feed.entity.forEach(entity => {
      if (!entity.tripUpdate) return;

      const tripUpdate = entity.tripUpdate;
      const tripId = tripUpdate.trip?.tripId;

      if (!tripId) return;

      // get delay for trip 
      const firstStopUpdate = tripUpdate.stopTimeUpdate?.find(stopUpdate =>
        typeof stopUpdate.arrival?.delay === 'number'
        || typeof stopUpdate.departure?.delay === 'number'
      );
      const tripDelay = typeof tripUpdate.delay === 'number'
        ? tripUpdate.delay
        : typeof firstStopUpdate?.departure?.delay === 'number'
          ? firstStopUpdate.departure.delay
          : firstStopUpdate?.arrival?.delay;
      
      // store in data structure
      if (typeof tripDelay === 'number') {
        delayByTrip[tripId] = Math.round(tripDelay/60); // delay in minutes
      }

      // we don't need more detailed updates
      // const updateInfo = {
      //   id: entity.id,
      //   tripId: tripId,
      //   routeId: tripUpdate.trip?.routeId || null,
      //   startTime: tripUpdate.trip?.startTime || null,
      //   startDate: tripUpdate.trip?.startDate || null,
      //   scheduleRelationship: tripUpdate.trip?.scheduleRelationship || null,
      //   delay: tripDelay,
      //   timestamp: tripUpdate.timestamp?.toNumber() || null,
      //   vehicleId: tripUpdate.vehicle?.id || null,
      //   stopTimeUpdates: tripUpdate.stopTimeUpdate?.map(stu => ({
      //     stopSequence: stu.stopSequence || null,
      //     stopId: stu.stopId || null,
      //     arrival: stu.arrival ? {
      //       delay: stu.arrival.delay || null,
      //       time: stu.arrival.time?.toNumber() || null,
      //       uncertainty: stu.arrival.uncertainty || null
      //     } : null,
      //     departure: stu.departure ? {
      //       delay: stu.departure.delay || null,
      //       time: stu.departure.time?.toNumber() || null,
      //       uncertainty: stu.departure.uncertainty || null
      //     } : null,
      //     scheduleRelationship: stu.scheduleRelationship || null
      //   })) || []
      // };
      //formattedUpdateData.push(updateInfo);
    });

    //cachedData.updates = formattedUpdateData;
    cachedData.delayByTrip = delayByTrip;
    cachedData.lastUpdate.updates = new Date();
    
    log(`[${new Date().toISOString()}] Trip updates data updated: ${Object.keys(delayByTrip).length} trips with delays`);
    
      //return { updates: formattedUpdateData, delayByTrip };
      return { updates: delayByTrip };
      
  } catch (error) {
    console.error('Error fetching trip updates data:', error.message);
    return null;
  }
}



// ----------------------------------------------------------------------------------
// Routes API

// api endpoint for vehicle positions in JSON
app.get('/api/vehicles', (req, res) => {
  if (!cachedData.vehicles) {
    return res.status(503).json({ 
      error: 'Data not yet available',
      message: 'Server is initializing, please retry in a few seconds'
    });
  }
  res.json({
    data: cachedData.vehicles,
    lastUpdate: cachedData.lastUpdate.vehicles,
    count: cachedData.vehicles.length
  });
});


// api endpoint for raw alerts in protobuf 
app.get('/api/alerts/raw', (req, res) => {
  if (!cachedData.alertsRaw) {
    return res.status(503).json({ 
      error: 'Data not yet available',
      message: 'Server is initializing, please retry in a few seconds'
    });
  }
  // headers for protobuf
  res.set({
    'Content-Type': 'application/x-protobuf',
    'Content-Length': cachedData.alertsRaw.byteLength
  });
  // sent raw buffer
  res.send(Buffer.from(cachedData.alertsRaw));
});


//api endpoint for alerts (json, lacks human-readable cancellation times)
app.get('/api/alerts', (req, res) => {
  if (!cachedData.alerts) {
    return res.status(503).json({ 
      error: 'Data not yet available',
      message: 'Server is initializing, please retry in a few seconds'
    });
  }
  res.json({
    data: cachedData.alerts,
    lastUpdate: cachedData.lastUpdate.alerts,
    count: cachedData.alerts.length
  });
});


// api endpoint to get delays for tripids (simplified format)
app.get('/api/delays', (req, res) => {
  if (!cachedData.delayByTrip) {
    return res.status(503).json({ 
      error: 'Data not yet available',
      message: 'Server is initializing, please retry in a few seconds'
    });
  }
  res.json({
    delayByTrip: cachedData.delayByTrip,
    lastUpdate: cachedData.lastUpdate.updates,
    count: Object.keys(cachedData.delayByTrip).length
  });
});


// Status endpoint to check server is running and last updates
app.get('/status', (req, res) => {
  res.json({
    status: 'okdoki',
    uptime: process.uptime(),
    lastUpdate: cachedData.lastUpdate,
      dataAvailable: {
	  vehicles: cachedData.vehicles !== null,
	  alerts: cachedData.alerts !== null,
	  delays: cachedData.delayByTrip !== null
      }
  });
});


// Root endpoint
app.get('/', (req, res) => {
  res.json({
    message: 'GTFS Realtime Cache Server',
    endpoints: {
	vehicles: '/api/vehicles',
	alerts: '/api/alerts',
	alertsRaw: '/api/alerts/raw',	
	//updates: '/api/updates',
	delays: '/api/delays',
	health: '/status'
    }
  });
});





// ----------------------------------------------------------------------------------
// Init and start server
async function init() {
    if (!CONFIG.apiKey) {
      throw new Error('Missing BMC_PARTNER_KEY (or legacy API_KEY) in server/.env');
    }

    log('GTFS Cache Server starting...');
    log('Configuration:', {
      vehicleUrl: CONFIG.vehicleUrl,
      alertUrl: CONFIG.alertUrl,
      updateUrl: CONFIG.updateUrl,
      refreshIntervals: CONFIG.refreshIntervals,
      port: PORT
  });

    // Get first data when server starts
    const initialData = await Promise.all([
	fetchAndConvertVehicles(),
	fetchAndConvertAlerts(),
	fetchAndConvertUpdates()
    ]);
    if (initialData.some(data => data === null)) {
      throw new Error('One or more initial Belgian Mobility feed requests failed.');
    }

  // Update data
    setInterval(fetchAndConvertVehicles, CONFIG.refreshIntervals.vehicles);
    setInterval(fetchAndConvertAlerts, CONFIG.refreshIntervals.alerts);
    setInterval(fetchAndConvertUpdates, CONFIG.refreshIntervals.updates);

  // Start HTTP server
  app.listen(PORT, () => {
      console.log(`Server running on port ${PORT}`);
      console.log(`Verbose logging: ${CONFIG.verboseLogging ? 'enabled' : 'disabled (set VERBOSE_LOGGING=true to enable)'}`);
      console.log(`Access it at http://localhost:${PORT}`);
  });
}

// Handle uncaught exceptions
process.on('uncaughtException', (error) => {
  console.error('Uncaught Exception:', error);
});
process.on('unhandledRejection', (reason, promise) => {
  console.error('Unhandled Rejection at:', promise, 'reason:', reason);
});

// Start
init().catch(error => {
  console.error('GTFS Cache Server startup failed:', error.message);
  process.exitCode = 1;
});
