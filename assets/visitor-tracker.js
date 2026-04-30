/**
 * visitor-tracker.js
 * Lightweight visitor tracking snippet.
 *
 * Drop into any page:
 *   <script src="/assets/visitor-tracker.js"></script>
 *
 * Runs on page load. Sends page URL, timestamp, and referrer
 * to POST /api/track/visit. Stores visitor_id in localStorage
 * so returning visitors are recognized.
 */
(function () {
  "use strict";

  var ENDPOINT = "/api/track/visit";
  var STORAGE_KEY = "ai1stseo_visitor_id";

  // Get or create visitor ID
  var visitorId = "";
  try {
    visitorId = localStorage.getItem(STORAGE_KEY) || "";
  } catch (e) {
    // localStorage unavailable (private browsing, etc.)
  }

  var payload = {
    page: window.location.pathname + window.location.search,
    timestamp: new Date().toISOString(),
    referrer: document.referrer || "",
    visitor_id: visitorId,
  };

  // Send tracking request
  try {
    var xhr = new XMLHttpRequest();
    xhr.open("POST", ENDPOINT, true);
    xhr.setRequestHeader("Content-Type", "application/json");
    xhr.onreadystatechange = function () {
      if (xhr.readyState === 4 && xhr.status === 200) {
        try {
          var resp = JSON.parse(xhr.responseText);
          // Store visitor_id for future visits
          if (resp.visitor_id) {
            try {
              localStorage.setItem(STORAGE_KEY, resp.visitor_id);
            } catch (e) {
              // ignore
            }
          }
        } catch (e) {
          // ignore parse errors
        }
      }
    };
    xhr.send(JSON.stringify(payload));
  } catch (e) {
    // Tracking should never break the page
  }
})();
