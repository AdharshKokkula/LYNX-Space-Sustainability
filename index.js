require({
  packages: [
    {
      name: "root",
      location: document.location.pathname + "/..",
    },
  ],
}, [
  "esri/Map",
  "esri/Camera",
  "esri/views/SceneView",
  "esri/views/3d/externalRenderers",
  "root/renderer",
  "dojo/number",
  "dojo/string",
  "dojo/domReady!",
], function (
  Map,
  Camera,
  SceneView,
  ExternalRenderers,
  Renderer,
  number,
  string
) {
  $(document).ready(function () {
    // Enforce strict mode
    "use strict";

    // Files
    var TLE = "data/tle.20171129.txt";
    var OIO = "data/oio.20171129.txt";

    // Well known satellite constellations.
    var GPS = [
      20959, 22877, 23953, 24876, 25933, 26360, 26407, 26605, 26690, 27663,
      27704, 28129, 28190, 28361, 28474, 28874, 29486, 29601, 32260, 32384,
      32711, 35752, 36585, 37753, 38833, 39166, 39533, 39741, 40105, 40294,
      40534,
    ];
    var GLONASS = [
      28915, 29672, 29670, 29671, 32276, 32275, 32393, 32395, 36111, 36112,
      36113, 36400, 36402, 36401, 37139, 37138, 37137, 37829, 37869, 37867,
      37868, 39155, 39620, 40001,
    ];
    var INMARSAT = [
      20918, 21149, 21814, 21940, 23839, 24307, 24674, 24819, 25153, 28628,
      28899, 33278, 40384, 39476,
    ];
    var LANDSAT = [25682, 39084];
    var DIGITALGLOBE = [25919, 32060, 33331, 35946, 40115];
    var SPACESTATIONS = [
      25544, // International Space Station
      41765, // Tiangong-2
    ];

    // Orbital altitude definitions.
    var LOW_ORBIT = 2000;
    var GEOSYNCHRONOUS_ORBIT = 35786;

    // Satellite database urls.
    var NASA_SATELLITE_DATABASE =
      "https://nssdc.gsfc.nasa.gov/nmc/masterCatalog.do?sc="; // use International id
    var N2YO_SATELLITE_DATABASE = "https://www.n2yo.com/satellite/?s="; // use NORAD id

    // Rendering variables.
    var renderer = null;

    // Make renderer accessible globally for reset functionality
    window.renderer = null;

    // Create map and view
    var view = new SceneView({
      map: new Map({
        basemap: "hybrid",
      }),
      container: "map",
      ui: {
        components: ["zoom", "compass"],
      },
      environment: {
        // lighting: {
        //   directShadowsEnabled: false,
        //   ambientOcclusionEnabled: false,
        //   cameraTrackingEnabled: false,
        // },
        atmosphereEnabled: true,
        atmosphere: {
          quality: "high",
        },
        starsEnabled: false,
      },
      constraints: {
        altitude: {
          max: 12000000000,
        },
      },
    });
    view.when(function () {
      // Set initial camera position
      view.set(
        "camera",
        Camera.fromJSON({
          position: {
            x: -1308000,
            y: 2670000,
            spatialReference: {
              wkid: 102100,
              latestWkid: 3857,
            },
            z: 110000000,
          },
        })
      );

      // Increase far clipping plane
      view.constraints.clipDistance.far *= 4;

      // Load satellites
      loadSatellites().done(function (satellites) {
        // Load satellite layer
        renderer = new Renderer(satellites);
        window.renderer = renderer; // Make available globally
        ExternalRenderers.add(view, renderer);

        // Show satellite count
        updateCounter();

        // Store satellites for search
        storeSatellitesForSearch(satellites);

        // Load metadata
        loadMetadata().done(function (metadata) {
          $.each(renderer.satellites, function () {
            this.metadata = metadata[this.id];
          });

          // Initialize search functionality after metadata is loaded
          initializeSearchFunctionality();
        });
      });
    });
    view.on("click", function (e) {
      // Highlighted satellite
      var sat = renderer.satelliteHover;
      let details = document.getElementById("bottom-left");
      let probability = document.getElementById("botton-right-probability");

      // Nothing selected. Hide orbit and close information window.
      if (sat === null) {
        renderer.hideOrbit();
        details.style.display = "none";
        probability.style.display = "none";
        // showDialog("main");
        return;
      }

      //////////////////////////////////

      ////////////////////////////////////

      // Display information panel
      $("#infoWindow-title").html(sat.metadata.name);
      $("#infoWindow-norad").html(sat.id);
      $("#infoWindow-int").html(sat.metadata.int);
      $("#infoWindow-name").html(sat.metadata.name);
      $("#infoWindow-country").html(sat.metadata.country);
      const periodInMinutes = sat.metadata.period;
      const periodInSeconds = periodInMinutes * 60;
      const periodInHours = periodInMinutes / 60;

      const formattedPeriod = `${number.format(periodInHours, {
        places: 2,
      })} hours | ${number.format(periodInMinutes, {
        places: 2,
      })} min | ${number.format(periodInSeconds, { places: 2 })} sec`;

      $("#infoWindow-period").html(formattedPeriod);
      $("#infoWindow-inclination").html(sat.metadata.inclination + "°");
      $("#infoWindow-apogee").html(
        number.format(sat.metadata.apogee, {
          places: 0,
        }) + " km"
      );
      $("#infoWindow-perigee").html(
        number.format(sat.metadata.perigee, {
          places: 0,
        }) + " km"
      );
      $("#infoWindow-size").html(sat.metadata.size);
      $("#infoWindow-launch").html(sat.metadata.launch.toLocaleDateString());
      $("#link-nasa").attr(
        "href",
        string.substitute(NASA_SATELLITE_DATABASE + "${id}", {
          id: sat.metadata.int,
        })
      );
      $("#link-n2yo").attr(
        "href",
        string.substitute(N2YO_SATELLITE_DATABASE + "${id}", { id: sat.id })
      );
      showDialog("info");

      // Display the orbit for the click satellite
      console.log("Selected Satellite NORAD ID:", sat.id);

      ////////////////////////////////////

      // Loading spinner functions
      function showCollisionLoadingSpinner() {
        const bottomRightProbability = document.getElementById(
          "botton-right-probability"
        );
        const table = document.getElementById("table");

        if (bottomRightProbability && table) {
          // Clear existing content
          table.innerHTML = "";

          // Add loading class for transition
          bottomRightProbability.classList.add("loading");

          // Create spinner element
          const spinnerContainer = document.createElement("div");
          spinnerContainer.className = "collision-loading-spinner";
          spinnerContainer.id = "collision-spinner";

          const spinnerRing = document.createElement("div");
          spinnerRing.className = "spinner-ring";

          // Create 3 spinning elements
          for (let i = 0; i < 3; i++) {
            const spinnerDiv = document.createElement("div");
            spinnerRing.appendChild(spinnerDiv);
          }

          const spinnerText = document.createElement("div");
          spinnerText.className = "spinner-text";
          spinnerText.textContent = "Calculating Collision Probability";

          const spinnerSubtitle = document.createElement("div");
          spinnerSubtitle.className = "spinner-subtitle";
          spinnerSubtitle.textContent = "Analyzing satellite trajectories...";

          spinnerContainer.appendChild(spinnerRing);
          spinnerContainer.appendChild(spinnerText);
          spinnerContainer.appendChild(spinnerSubtitle);

          table.appendChild(spinnerContainer);

          // Show the probability panel
          bottomRightProbability.style.display = "block";
        }
      }

      function hideCollisionLoadingSpinner() {
        const bottomRightProbability = document.getElementById(
          "botton-right-probability"
        );
        const spinner = document.getElementById("collision-spinner");

        if (bottomRightProbability) {
          // Remove loading class
          bottomRightProbability.classList.remove("loading");
        }

        if (spinner) {
          // Smooth fade out
          spinner.style.opacity = "0";
          spinner.style.transform = "translateY(-10px)";

          setTimeout(() => {
            if (spinner.parentNode) {
              spinner.parentNode.removeChild(spinner);
            }
          }, 300);
        }
      }

      async function checkServerHealth() {
        try {
          const response = await fetch("http://127.0.0.1:5000/health", {
            method: "GET",
            signal: AbortSignal.timeout(5000), // 5 second timeout
          });
          return response.ok;
        } catch (error) {
          console.warn("Server health check failed:", error.message);
          return false;
        }
      }

      async function getSatelliteCollisionProbability(satelliteId) {
        console.log(
          "Fetching collision probability for satellite:",
          satelliteId
        );

        // Show loading spinner
        showCollisionLoadingSpinner();

        try {
          const url = "http://127.0.0.1:5000/satellite-collision-probability";
          const payload = { target_norad_id: satelliteId };

          // Add timeout to the fetch request
          const controller = new AbortController();
          const timeoutId = setTimeout(() => controller.abort(), 30000); // 30 second timeout

          const response = await fetch(url, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify(payload),
            signal: controller.signal,
          });

          clearTimeout(timeoutId);

          // Check if the response is successful
          if (!response.ok) {
            const errorBody = await response.text();
            console.error("HTTP Error Status:", response.status);
            console.error("HTTP Error Body:", errorBody);

            // Handle specific error cases
            if (response.status === 404) {
              throw new Error("Satellite not found in database");
            } else if (response.status >= 500) {
              throw new Error("Server error occurred");
            } else {
              throw new Error(`HTTP ${response.status}: ${errorBody}`);
            }
          }

          // Parse the JSON response
          const data = await response.json();
          console.log("Collision probability data:", data);

          // Hide loading spinner and update HTML elements with response data
          hideCollisionLoadingSpinner();
          updateCollisionProbabilityUI(data);

          return data;
        } catch (error) {
          console.error("Error fetching collision probability:", error);

          // Handle different types of errors
          let errorMessage = "Unable to fetch collision data";

          if (error.name === "AbortError") {
            errorMessage = "Request timed out. Please try again.";
          } else if (error.message.includes("Failed to fetch")) {
            errorMessage =
              "Backend server is not running. Please start the server.";
          } else if (error.message.includes("NetworkError")) {
            errorMessage =
              "Network connection error. Please check your connection.";
          } else {
            errorMessage = error.message || "Unknown error occurred";
          }

          // Hide loading spinner and show error in the collision probability panel
          hideCollisionLoadingSpinner();
          updateCollisionProbabilityUI({
            status: "error",
            error_message: errorMessage,
          });

          return null;
        }
      }

      function updateCollisionProbabilityUI(data) {
        const bottomRightProbability = document.getElementById(
          "botton-right-probability"
        );
        const table = document.getElementById("table");

        // Ensure spinner is hidden and clear existing content
        hideCollisionLoadingSpinner();

        // Remove existing additional rows if any
        if (bottomRightProbability) {
          const existingAdditionalRows =
            bottomRightProbability.querySelectorAll(".additional-info");
          existingAdditionalRows.forEach((row) => row.remove());
        }

        // Clear table content to ensure no spinner remnants
        if (table) {
          table.innerHTML = "";
        }

        // Handle error cases
        if (data.status === "error" || !data) {
          const errorMessage = data.error_message || "Unknown error occurred";

          if (table) {
            const errorRow = document.createElement("tr");
            errorRow.classList.add("additional-info", "error-row");

            const errorCell = document.createElement("td");
            errorCell.setAttribute("colspan", "2");
            errorCell.classList.add("table-error");
            errorCell.style.color = "#ff6b6b";
            errorCell.style.textAlign = "center";
            errorCell.style.padding = "10px";
            errorCell.textContent = errorMessage;

            errorRow.appendChild(errorCell);
            table.appendChild(errorRow);
          }
          return;
        }

        // Handle no collisions predicted
        if (data.status === "no_collisions_predicted") {
          if (table) {
            const noCollisionRow = document.createElement("tr");
            noCollisionRow.classList.add("additional-info", "no-collision-row");

            const noCollisionCell = document.createElement("td");
            noCollisionCell.setAttribute("colspan", "2");
            noCollisionCell.classList.add("table-info");
            noCollisionCell.style.color = "#4ecdc4";
            noCollisionCell.style.textAlign = "center";
            noCollisionCell.style.padding = "10px";
            noCollisionCell.textContent =
              "No collision risks detected in the next 7 days";

            noCollisionRow.appendChild(noCollisionCell);
            table.appendChild(noCollisionRow);
          }
          return;
        }

        // Check if we have collision data
        if (data.status === "success" && data.collision_data) {
          const collisionData = data.collision_data;

          if (table) {
            // Add rows for additional information
            const additionalRows = [
              {
                label: "Collision Probability",
                value: collisionData.collision_probability,
              },
              {
                label: "Potential Collision NORAD ID",
                value: collisionData.norad_id,
              },
              {
                label: "Distance (km)",
                value:
                  typeof collisionData["distance (km)"] === "number"
                    ? collisionData["distance (km)"].toFixed(2)
                    : collisionData["distance (km)"],
              },
              {
                label: "Relative Speed (km/s)",
                value:
                  typeof collisionData["relative_speed (km/s)"] === "number"
                    ? collisionData["relative_speed (km/s)"].toFixed(2)
                    : collisionData["relative_speed (km/s)"],
              },
              {
                label: "Latitude",
                value:
                  typeof collisionData.latitude === "number"
                    ? collisionData.latitude.toFixed(2) + "°"
                    : collisionData.latitude,
              },
              {
                label: "Longitude",
                value:
                  typeof collisionData.longitude === "number"
                    ? collisionData.longitude.toFixed(2) + "°"
                    : collisionData.longitude,
              },
              {
                label: "Analysis Timestamp",
                value: data.timestamp
                  ? new Date(data.timestamp).toLocaleString()
                  : "N/A",
              },
            ];

            additionalRows.forEach((item) => {
              const row = document.createElement("tr");
              row.classList.add("additional-info");

              const labelCell = document.createElement("td");
              labelCell.classList.add("table-heading");
              labelCell.style.fontWeight = "bold";
              labelCell.style.color = "#337ab7";
              labelCell.textContent = `${item.label}:`;

              const valueCell = document.createElement("td");
              valueCell.classList.add("table-value");
              valueCell.style.color = "#ffffff";
              valueCell.textContent = item.value;

              row.appendChild(labelCell);
              row.appendChild(valueCell);
              table.appendChild(row);
            });
            
            // Initialize report generator with collision data
            if (typeof initializeReportGenerator === 'function') {
              initializeReportGenerator(
                data.target_norad_id,
                data.collision_data
              );
            }
          }
        } else {
          console.error("Unexpected data format:", data);

          if (table) {
            const errorRow = document.createElement("tr");
            errorRow.classList.add("additional-info", "error-row");

            const errorCell = document.createElement("td");
            errorCell.setAttribute("colspan", "2");
            errorCell.classList.add("table-error");
            errorCell.style.color = "#ff6b6b";
            errorCell.style.textAlign = "center";
            errorCell.style.padding = "10px";
            errorCell.textContent = "Unexpected response format";

            errorRow.appendChild(errorCell);
            table.appendChild(errorRow);
          }
        }
      }

      // Check if server is available before making the request
      checkServerHealth().then((isHealthy) => {
        if (isHealthy) {
          getSatelliteCollisionProbability(String(sat.id));
        } else {
          // Show fallback message
          updateCollisionProbabilityUI({
            status: "error",
            error_message:
              "Backend server is not running. Please start the server using start_server.bat",
          });
        }
      });

      renderer.showOrbit();

      ////////////////////////////////////
    });

    $("#map").mousemove(function (e) {
      if (!renderer) {
        return;
      }
      renderer.mousemove(e.offsetX, e.offsetY);
    });

    $("#bottom-left-help a").attr("target", "_blank");
    $("#bottom-left-about a").attr("target", "_blank");
    $("#link-nasa, #link-n2yo").attr("target", "_blank");

    $(".rc-close").click(function () {
      $.each(renderer.satellites, function () {
        this.highlighted = false;
      });
      renderer.hideOrbit();
      showDialog("main");
      details.style.display = "none";
      probability.style.display = "none";
    });

    $("#buttonReset").click(function () {
      resetUI();
      selectSatellites();
      updateCounter();
      renderer.updateSelection();
    });

    // Country
    $(".rc-country > button").click(function () {
      $(".rc-country > button").removeClass("active");
      $(this).addClass("active");
      selectSatellites();
      updateCounter();
      renderer.updateSelection();
    });

    // Type or Size
    $(".rc-type > button, .rc-size > button").click(function () {
      $(this).addClass("active").siblings(".active").removeClass("active");
      selectSatellites();
      updateCounter();
      renderer.updateSelection();
    });

    function showDialog() {
      const details = document.getElementById("bottom-left");
      const probability = document.getElementById("botton-right-probability");
      details.style.display = "block";
      probability.style.display = "block";
    }

    function selectSatellites() {
      // Country
      var country = $(".rc-country > button.active").attr("data-value");
      var junk = $(".rc-type > button.active").attr("data-value");
      var size = $(".rc-size > button.active").attr("data-value");

      var val1 = $("#slider-launchdate").slider("getValue");
      var val2 = $("#slider-period").slider("getValue");
      var val3 = $("#slider-inclination").slider("getValue");
      var val4 = $("#slider-apogee").slider("getValue");
      var val5 = $("#slider-perigee").slider("getValue");

      var min1 = $("#slider-launchdate").slider("getAttribute", "min");
      var min2 = $("#slider-period").slider("getAttribute", "min");
      var min3 = $("#slider-inclination").slider("getAttribute", "min");
      var min4 = $("#slider-apogee").slider("getAttribute", "min");
      var min5 = $("#slider-perigee").slider("getAttribute", "min");

      var max1 = $("#slider-launchdate").slider("getAttribute", "max");
      var max2 = $("#slider-period").slider("getAttribute", "max");
      var max3 = $("#slider-inclination").slider("getAttribute", "max");
      var max4 = $("#slider-apogee").slider("getAttribute", "max");
      var max5 = $("#slider-perigee").slider("getAttribute", "max");

      // Exit if nothing selected
      if (
        country === "none" &&
        junk === "none" &&
        size === "none" &&
        val1[0] === min1 &&
        val1[1] === max1 &&
        val2[0] === min2 &&
        val2[1] === max2 &&
        val3[0] === min3 &&
        val3[1] === max3 &&
        val4[0] === min4 &&
        val4[1] === max4 &&
        val5[0] === min5 &&
        val5[1] === max5
      ) {
        $.each(renderer.satellites, function () {
          this.selected = false;
        });
        return;
      }

      //
      $.each(renderer.satellites, function () {
        // Reset selection
        this.selected = false;

        // Exit if metadata is missing
        if (this.metadata === null || this.metadata === undefined) {
          return true;
        }

        // Select by country
        if (country !== "none") {
          if (this.metadata.country !== country) {
            return true;
          }
        }

        // Select by junk
        if (junk !== "none") {
          var name = this.metadata.name;
          if (
            junk === "junk" &&
            name.indexOf(" DEB") === -1 &&
            name.indexOf(" R/B") === -1
          ) {
            return true;
          }
          if (
            junk === "not-junk" &&
            (name.indexOf(" DEB") !== -1 || name.indexOf(" R/B") !== -1)
          ) {
            return true;
          }
        }

        // Size
        if (size !== "none") {
          if (this.metadata.size !== size) {
            return true;
          }
        }

        // Launch date
        if (val1[0] !== min1 || val1[1] !== max1) {
          var y = this.metadata.launch.getFullYear();
          if (y <= val1[0] || y >= val1[1]) {
            return true;
          }
        }

        // Orbital period
        if (val2[0] !== min2 || val2[1] !== max2) {
          if (
            this.metadata.period < val2[0] ||
            this.metadata.period > val2[1]
          ) {
            return true;
          }
        }

        // Inclination
        if (val3[0] !== min3 || val3[1] !== max3) {
          if (
            this.metadata.inclination < val3[0] ||
            this.metadata.inclination > val3[1]
          ) {
            return true;
          }
        }

        // Apogee
        if (val4[0] !== min4 || val4[1] !== max4) {
          if (
            this.metadata.apogee < val4[0] ||
            this.metadata.apogee > val4[1]
          ) {
            return true;
          }
        }

        // Perigee
        if (val5[0] !== min5 || val5[1] !== max5) {
          if (
            this.metadata.perigee < val5[0] ||
            this.metadata.perigee > val5[1]
          ) {
            return true;
          }
        }

        // Select satellite
        this.selected = true;
      });
    }

    function updateCounter() {
      var selected = 0;
      $.each(renderer.satellites, function () {
        if (this.selected) {
          selected++;
        }
      });
      if (selected === 0) {
        $("#satellite-count").html(
          string.substitute("${count} satellites loaded", {
            count: number.format(renderer.satellites.length, {
              places: 0,
            }),
          })
        );
      } else {
        $("#satellite-count").html(
          string.substitute("${found} of ${count} satellites found", {
            found: number.format(selected, {
              places: 0,
            }),
            count: number.format(renderer.satellites.length, {
              places: 0,
            }),
          })
        );
      }
    }

    function loadSatellites() {
      var defer = new $.Deferred();
      $.get(TLE, function (data) {
        var lines = data.split("\n");
        var count = (lines.length / 2).toFixed(0);
        var satellites = [];
        for (var i = 0; i < count; i++) {
          var line1 = lines[i * 2 + 0];
          var line2 = lines[i * 2 + 1];
          var satrec = null;
          try {
            satrec = satellite.twoline2satrec(line1, line2);
          } catch (err) {
            continue;
          }
          if (satrec === null || satrec === undefined) {
            continue;
          }
          satellites.push({
            id: Number(line1.substring(2, 7)),
            satrec: satrec,
            selected: false,
            highlighted: false,
            metadata: null,
          });
        }
        defer.resolve(satellites);
      });
      return defer.promise();
    }

    function loadMetadata() {
      var defer = new $.Deferred();
      $.get(OIO, function (data) {
        var metadata = {};
        var lines = data.split("\n");
        $.each(lines, function () {
          var items = this.split(",");
          var int = items[0];
          var name = items[1];
          var norad = Number(items[2]);
          var country = items[3];
          var period = items[4];
          var inclination = items[5];
          var apogee = items[6];
          var perigee = items[7];
          var size = items[8];
          var launch = new Date(items[10]);
          metadata[norad] = {
            int: int,
            name: name,
            country: country,
            period: period,
            inclination: inclination,
            apogee: apogee,
            perigee: perigee,
            size: size,
            launch: launch,
          };
        });
        defer.resolve(metadata);
      });
      return defer.promise();
    }

    function resetUI() {
      $(".rc-country > button")
        .removeClass("active")
        .siblings('[data-value="none"]')
        .addClass("active");
      $(".rc-type > button")
        .removeClass("active")
        .siblings('[data-value="none"]')
        .addClass("active");
      $(".rc-size > button")
        .removeClass("active")
        .siblings('[data-value="none"]')
        .addClass("active");
      resetSlider("#slider-launchdate");
      resetSlider("#slider-period");
      resetSlider("#slider-inclination");
      resetSlider("#slider-apogee");
      resetSlider("#slider-perigee");
    }

    function resetSlider(name) {
      $(name).slider("setValue", [
        $(name).slider("getAttribute", "min"),
        $(name).slider("getAttribute", "max"),
      ]);
    }

    // Search functionality
    var allSatellites = [];
    var selectedSuggestionIndex = -1;

    // Store satellites when loaded for search functionality
    function storeSatellitesForSearch(satellites) {
      allSatellites = satellites;
      console.log("Stored satellites for search:", satellites.length);
    }

    // Search satellites by NORAD ID or name
    function searchSatellites(query) {
      if (!query || query.length < 2) {
        return [];
      }

      var results = [];
      var queryLower = query.toLowerCase();
      var isNumeric = /^\d+$/.test(query);

      $.each(allSatellites, function () {
        if (!this.metadata) return;

        var match = false;
        var noradMatch = false;
        var nameMatch = false;

        // Check NORAD ID (exact match or starts with)
        if (isNumeric && this.id.toString().indexOf(query) === 0) {
          noradMatch = true;
          match = true;
        }

        // Check satellite name (contains)
        if (
          this.metadata.name &&
          this.metadata.name.toLowerCase().indexOf(queryLower) !== -1
        ) {
          nameMatch = true;
          match = true;
        }

        if (match) {
          results.push({
            satellite: this,
            noradMatch: noradMatch,
            nameMatch: nameMatch,
          });
        }
      });

      // Sort results: NORAD matches first, then name matches
      results.sort(function (a, b) {
        if (a.noradMatch && !b.noradMatch) return -1;
        if (!a.noradMatch && b.noradMatch) return 1;
        return 0;
      });

      return results.slice(0, 10); // Limit to 10 results
    }

    // Show search suggestions
    function showSuggestions(suggestions) {
      var suggestionsContainer = $("#search-suggestions");

      // Animate out if already visible
      if (suggestionsContainer.hasClass("show")) {
        suggestionsContainer.removeClass("show").addClass("hide");
        setTimeout(function () {
          showSuggestionsContent(suggestions, suggestionsContainer);
        }, 150);
      } else {
        showSuggestionsContent(suggestions, suggestionsContainer);
      }
    }

    function showSuggestionsContent(suggestions, container) {
      container.empty().removeClass("hide");

      if (suggestions.length === 0) {
        container.hide();
        return;
      }

      $.each(suggestions, function (index, result) {
        var sat = result.satellite;
        var suggestionHtml =
          '<span class="suggestion-norad">' +
          sat.id +
          "</span>" +
          '<span class="suggestion-name">' +
          sat.metadata.name +
          "</span>";

        var suggestionItem = $('<div class="suggestion-item">')
          .html(suggestionHtml)
          .data("satellite", sat)
          .data("index", index);

        suggestionItem.click(function (e) {
          e.preventDefault();
          e.stopPropagation();
          var satellite = $(this).data("satellite");
          console.log("Suggestion clicked:", satellite);
          fillSearchInput(satellite);
        });

        container.append(suggestionItem);
      });

      container.show();
      setTimeout(function () {
        container.addClass("show");
      }, 10);
      selectedSuggestionIndex = -1;
    }

    // Hide search suggestions
    function hideSuggestions() {
      var suggestionsContainer = $("#search-suggestions");
      suggestionsContainer.removeClass("show").addClass("hide");
      setTimeout(function () {
        suggestionsContainer.hide().removeClass("hide");
      }, 300);
      selectedSuggestionIndex = -1;
    }

    // Fill search input with selected satellite name
    function fillSearchInput(satellite) {
      console.log("fillSearchInput called with:", satellite);

      // Fill the input with satellite name FIRST
      $("#norad-input").val(satellite.metadata.name);

      // Hide suggestions after filling
      setTimeout(function () {
        hideSuggestions();
      }, 100);

      console.log("Filled search input with:", satellite.metadata.name);
    }

    // Select a satellite with animation
    function selectSatelliteWithAnimation(satellite) {
      // Add searching animation to input and button
      $("#norad-input").addClass("searching");
      $("#search-button").addClass("searching");

      // Simulate processing time for animation effect
      setTimeout(function () {
        selectSatellite(satellite);
        $("#norad-input").removeClass("searching");
        $("#search-button").removeClass("searching");
      }, 400);
    }

    // Select a satellite and navigate to it
    function selectSatellite(satellite) {
      // Hide suggestions
      hideSuggestions();

      // Clear the input
      $("#norad-input").val("");

      // Highlight the satellite
      $.each(renderer.satellites, function () {
        this.highlighted = false;
      });
      satellite.highlighted = true;

      // Trigger click event to show satellite details
      renderer.satelliteHover = satellite;

      // Show satellite details
      $("#infoWindow-title").html(satellite.metadata.name);
      $("#infoWindow-norad").html(satellite.id);
      $("#infoWindow-int").html(satellite.metadata.int);
      $("#infoWindow-name").html(satellite.metadata.name);
      $("#infoWindow-country").html(satellite.metadata.country);

      const periodInMinutes = satellite.metadata.period;
      const periodInSeconds = periodInMinutes * 60;
      const periodInHours = periodInMinutes / 60;

      const formattedPeriod = `${number.format(periodInHours, {
        places: 2,
      })} hours | ${number.format(periodInMinutes, {
        places: 2,
      })} min | ${number.format(periodInSeconds, { places: 2 })} sec`;

      $("#infoWindow-period").html(formattedPeriod);
      $("#infoWindow-inclination").html(satellite.metadata.inclination + "°");
      $("#infoWindow-apogee").html(
        number.format(satellite.metadata.apogee, {
          places: 0,
        }) + " km"
      );
      $("#infoWindow-perigee").html(
        number.format(satellite.metadata.perigee, {
          places: 0,
        }) + " km"
      );
      $("#infoWindow-size").html(satellite.metadata.size);
      $("#infoWindow-launch").html(
        satellite.metadata.launch.toLocaleDateString()
      );
      $("#link-n2yo").attr(
        "href",
        string.substitute(N2YO_SATELLITE_DATABASE + "${id}", {
          id: satellite.id,
        })
      );

      // Show dialog
      showDialog("info");

      // Show orbit
      renderer.showOrbit();

      console.log(
        "Selected Satellite:",
        satellite.metadata.name,
        "NORAD ID:",
        satellite.id
      );
    }

    // Handle keyboard navigation
    function handleKeyNavigation(e) {
      var suggestions = $(".suggestion-item");
      if (suggestions.length === 0) return;

      switch (e.keyCode) {
        case 38: // Up arrow
          e.preventDefault();
          selectedSuggestionIndex =
            selectedSuggestionIndex <= 0
              ? suggestions.length - 1
              : selectedSuggestionIndex - 1;
          updateSelection();
          break;
        case 40: // Down arrow
          e.preventDefault();
          selectedSuggestionIndex =
            selectedSuggestionIndex >= suggestions.length - 1
              ? 0
              : selectedSuggestionIndex + 1;
          updateSelection();
          break;
        case 13: // Enter
          e.preventDefault();
          if (selectedSuggestionIndex >= 0) {
            var selectedSat = suggestions
              .eq(selectedSuggestionIndex)
              .data("satellite");
            fillSearchInput(selectedSat);
          }
          break;
        case 27: // Escape
          hideSuggestions();
          break;
      }
    }

    function updateSelection() {
      $(".suggestion-item").removeClass("active");
      if (selectedSuggestionIndex >= 0) {
        $(".suggestion-item").eq(selectedSuggestionIndex).addClass("active");
      }
    }

    // Initialize search functionality after satellites are loaded
    function initializeSearchFunctionality() {
      console.log("Initializing search functionality");

      $("#norad-input").on("input", function () {
        var query = $(this).val().trim();
        console.log("Search input:", query);
        if (query.length >= 1) {
          var suggestions = searchSatellites(query);
          console.log("Found suggestions:", suggestions.length);
          showSuggestions(suggestions);
        } else {
          hideSuggestions();
        }
      });

      $("#norad-input").on("keydown", handleKeyNavigation);

      $("#norad-input").on("blur", function () {
        // Delay hiding suggestions to allow clicks
        setTimeout(hideSuggestions, 500);
      });

      $("#search-button").click(function () {
        var query = $("#norad-input").val().trim();
        if (query) {
          var suggestions = searchSatellites(query);
          if (suggestions.length > 0) {
            // Find exact match by name or NORAD ID first
            var exactMatch = null;
            $.each(suggestions, function (index, result) {
              var sat = result.satellite;
              if (
                sat.metadata.name.toLowerCase() === query.toLowerCase() ||
                sat.id.toString() === query
              ) {
                exactMatch = sat;
                return false; // break loop
              }
            });

            // Use exact match if found, otherwise use first suggestion
            var satelliteToSelect = exactMatch || suggestions[0].satellite;
            selectSatelliteWithAnimation(satelliteToSelect);
          }
        }
      });
    }
  });
});
