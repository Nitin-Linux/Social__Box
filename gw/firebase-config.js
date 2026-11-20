// Centralized Firebase Configuration & Initialization
// Works for BOTH: compat SDK (admin-panel.html) and modular SDK (index.html, user-panel.html).
const firebaseConfig = {
  apiKey: "AIzaSyBH6tivGzGju9aeubEk-xgrXZgzQs6JCCo",
  authDomain: "gw-esports-559b3.firebaseapp.com",
  databaseURL: "https://gw-esports-559b3-default-rtdb.asia-southeast1.firebasedatabase.app",
  projectId: "gw-esports-559b3",
  storageBucket: "gw-esports-559b3.appspot.com",
  messagingSenderId: "152409172019",
  appId: "1:152409172019:web:05ace1e900ca4053e49b46"
};

// Expose for modular pages that read window.firebaseConfig.
window.firebaseConfig = firebaseConfig;

if (typeof firebase !== 'undefined' && firebase.apps) {
  if (!firebase.apps.length) {
    firebase.initializeApp(firebaseConfig);
  }
}