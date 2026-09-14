/**
 * KisanSetu — Offline-Resilient & Rural-First UX (Offline Storage Layer)
 * Uses IndexedDB (with localStorage fallback) to ensure issued gate passes & QR tokens
 * remain 100% viewable and verifiable even with zero network connectivity.
 */

(function (window) {
  'use strict';

  const DB_NAME = "kisan_setu_offline_db";
  const DB_VERSION = 1;
  const STORE_NAME = "gate_passes";
  const LOCAL_STORAGE_KEY = "kisan_offline_passes_backup";

  let idbPromise = null;

  function openDatabase() {
    if (idbPromise) return idbPromise;
    if (!window.indexedDB) {
      console.warn("IndexedDB not available, using localStorage fallback.");
      return Promise.resolve(null);
    }

    idbPromise = new Promise((resolve, reject) => {
      const req = indexedDB.open(DB_NAME, DB_VERSION);
      req.onupgradeneeded = (e) => {
        const db = e.target.result;
        if (!db.objectStoreNames.contains(STORE_NAME)) {
          db.createObjectStore(STORE_NAME, { keyPath: "tokenId" });
        }
      };
      req.onsuccess = (e) => resolve(e.target.result);
      req.onerror = (e) => {
        console.warn("IndexedDB open error:", e);
        resolve(null);
      };
    });

    return idbPromise;
  }

  const KisanOfflineStorage = {
    /**
     * Save issued gate pass & signed token offline
     */
    async savePass(tokenData) {
      if (!tokenData || !tokenData.tokenId) return;

      const record = {
        ...tokenData,
        cachedAt: new Date().toISOString()
      };

      // 1. Save to LocalStorage immediate mirror
      try {
        const existing = JSON.parse(localStorage.getItem(LOCAL_STORAGE_KEY) || "[]");
        const filtered = existing.filter(p => p.tokenId !== record.tokenId);
        filtered.unshift(record);
        localStorage.setItem(LOCAL_STORAGE_KEY, JSON.stringify(filtered.slice(0, 10)));
      } catch (err) {
        console.warn("LocalStorage savePass error:", err);
      }

      // 2. Save to IndexedDB
      const db = await openDatabase();
      if (db) {
        try {
          const tx = db.transaction(STORE_NAME, "readwrite");
          const store = tx.objectStore(STORE_NAME);
          store.put(record);
        } catch (err) {
          console.warn("IDB put error:", err);
        }
      }
    },

    /**
     * Retrieve offline pass by Token ID
     */
    async getPass(tokenId) {
      if (!tokenId) return null;

      // Check IndexedDB
      const db = await openDatabase();
      if (db) {
        try {
          const res = await new Promise((resolve) => {
            const tx = db.transaction(STORE_NAME, "readonly");
            const store = tx.objectStore(STORE_NAME);
            const req = store.get(tokenId);
            req.onsuccess = () => resolve(req.result || null);
            req.onerror = () => resolve(null);
          });
          if (res) return res;
        } catch (err) {
          // fallback to localStorage
        }
      }

      // LocalStorage fallback
      try {
        const list = JSON.parse(localStorage.getItem(LOCAL_STORAGE_KEY) || "[]");
        return list.find(p => p.tokenId === tokenId || p.bookingId === tokenId) || null;
      } catch (err) {
        return null;
      }
    },

    /**
     * Retrieve all cached offline passes
     */
    async getAllPasses() {
      const db = await openDatabase();
      if (db) {
        try {
          const res = await new Promise((resolve) => {
            const tx = db.transaction(STORE_NAME, "readonly");
            const store = tx.objectStore(STORE_NAME);
            const req = store.getAll();
            req.onsuccess = () => resolve(req.result || []);
            req.onerror = () => resolve([]);
          });
          if (res && res.length > 0) return res;
        } catch (err) {}
      }

      try {
        return JSON.parse(localStorage.getItem(LOCAL_STORAGE_KEY) || "[]");
      } catch (err) {
        return [];
      }
    },

    /**
     * Initialize online/offline UI monitor banner
     */
    initConnectivityWatcher() {
      const updateBanner = () => {
        let banner = document.getElementById("kisan-offline-banner");
        const isOffline = !navigator.onLine;

        if (isOffline) {
          if (!banner) {
            banner = document.createElement("div");
            banner.id = "kisan-offline-banner";
            banner.className = "fixed top-0 left-0 right-0 z-50 bg-amber-600 text-white text-xs font-bold py-2 px-4 text-center shadow-md flex items-center justify-center gap-2";
            banner.innerHTML = `
              <span>📡</span>
              <span>ऑफ़लाइन मोड सक्रिय: इंटरनेट कनेक्शन उपलब्ध नहीं है। आपका जारी गेट पास व QR टोकन ऑफ़लाइन सुरक्षित एवं वैध है।</span>
              <span class="text-[10px] bg-black/20 px-2 py-0.5 rounded font-mono uppercase">Offline Mode</span>
            `;
            document.body.prepend(banner);
          }
        } else {
          if (banner) {
            banner.remove();
          }
        }
      };

      window.addEventListener("online", updateBanner);
      window.addEventListener("offline", updateBanner);
      updateBanner();
    }
  };

  // Auto initialize watcher on DOM load
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => KisanOfflineStorage.initConnectivityWatcher());
  } else {
    KisanOfflineStorage.initConnectivityWatcher();
  }

  window.KisanOfflineStorage = KisanOfflineStorage;
})(window);
