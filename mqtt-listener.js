// ----------------------------
// 1. Firebase Initialization
// ----------------------------
const admin = require("firebase-admin");
const serviceAccount = require("./mqtt-to-firebase-key.json");

admin.initializeApp({
  credential: admin.credential.cert(serviceAccount),
});

const db = admin.firestore();

// ----------------------------
// 2. MQTT Initialization
// ----------------------------
const mqtt = require("mqtt");

const client = mqtt.connect(
  "mqtts://cf285fe28f4b4589855b6394ae136dfb.s1.eu.hivemq.cloud:8883",
  {
    username: "IOT-Jaakko",
    password: " ######",
  }
);

// ----------------------------
// 3. MQTT Subscription
// ----------------------------
const TOPIC = "jaakko_picow";

client.on("connect", () => {
  console.log("Connected to HiveMQ CE...");
  client.subscribe("#", (err) => {
    if (!err) console.log("Subscribed to all topics");
  });

  client.subscribe(TOPIC, (err) => {
    if (!err) console.log("Subscribed to:", TOPIC);
  });
});

// ----------------------------
// 4. Handle Incoming Messages
// ----------------------------
// Global cache (keeps last known value of each sensor)
let sensorCache = {};
let lastUpdate = Date.now();

// Handle MQTT messages
client.on("message", async (topic, message) => {
  try {
    // console.log("Received topic:", topic);
    const payload = message.toString();

    // Update cache based on topic
    if (topic.includes("temp")) {
      sensorCache.temperature = parseFloat(payload);
    } else if (topic.includes("pressure")) {
      sensorCache.pressure = parseFloat(payload);
    } else if (topic.includes("moisture")) {
      sensorCache.moisture = payload;
    } else {
      // fallback for unknown topics
      sensorCache.value = payload;
    }

    // Update timestamp of last incoming message
    const ts = new Date();
    ts.setHours(ts.getHours()); // apply UTC+2

    const data = {
      timestamp: ts.toISOString(),
      sensors: { ...sensorCache },
    };
    console.log("data", data);
    await db.collection("mqtt_data").add(data);

    console.log("Updated cache:", sensorCache);
  } catch (error) {
    console.error("Error processing message:", error);
  }
});

// setInterval(async () => {
//   if (Object.keys(sensorCache).length > 0) {
//     const data = {
//       timestamp: Date.now(),
//       sensors: { ...sensorCache },
//     };

//     await db.collection("mqtt_data").add(data);
//     console.log("Saved snapshot:", data);
//   }
// }, 2000);

