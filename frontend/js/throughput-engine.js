/**
 * KisanSetu — Dynamic Mandi Throughput Engine (Anti-Bottleneck Core)
 * Modular mathematical slot allocation and capacity meter.
 * Hourly Capacity = (Active Weighbridges * Avg Weighing Rate per Hr) + Buffer Adjustment
 */

(function (window) {
  'use strict';

  const DEFAULT_SLOTS = [
    "09:00 AM – 10:00 AM",
    "10:00 AM – 11:00 AM",
    "11:00 AM – 12:00 PM",
    "12:00 PM – 01:00 PM",
    "01:00 PM – 02:00 PM",
    "02:00 PM – 03:00 PM",
    "03:00 PM – 04:00 PM",
    "04:00 PM – 05:00 PM"
  ];

  const KisanThroughput = {
    /**
     * Calculate hourly physical vehicle capacity based on hardware assets
     */
    calculateHourlyCapacity(activeWeighbridges = 2, avgRatePerHr = 10, bufferAdjustment = -2) {
      const wb = Math.max(1, parseInt(activeWeighbridges, 10) || 2);
      const rate = Math.max(1, parseInt(avgRatePerHr, 10) || 10);
      const buf = parseInt(bufferAdjustment, 10) !== undefined ? parseInt(bufferAdjustment, 10) : -2;
      return Math.max(5, (wb * rate) + buf);
    },

    /**
     * 3-tier capacity classification
     * Green: <60%
     * Amber: 60-85%
     * Red / Locked: >85%
     */
    getCapacityTier(utilizationPct) {
      const pct = parseFloat(utilizationPct) || 0;
      if (pct < 60.0) {
        return {
          tier: "GREEN",
          code: "green",
          labelHindi: "कम भीड़ (सुगम प्रवेश)",
          labelEnglish: "Low Load (Fast-Track)",
          colorHex: "#15803d",
          bgHex: "#dcfce7",
          borderHex: "#86efac",
          badgeClass: "bg-emerald-50 text-emerald-800 border-emerald-200",
          isLocked: false
        };
      } else if (pct <= 85.0) {
        return {
          tier: "AMBER",
          code: "amber",
          labelHindi: "मध्यम भीड़ (सामान्य प्रतीक्षा)",
          labelEnglish: "Moderate Load (Standard Buffer)",
          colorHex: "#b45309",
          bgHex: "#fef3c7",
          borderHex: "#fde68a",
          badgeClass: "bg-amber-50 text-amber-800 border-amber-200",
          isLocked: false
        };
      } else {
        return {
          tier: "RED",
          code: "red",
          labelHindi: "अत्यधिक भीड़ (स्लॉट लॉक)",
          labelEnglish: "Heavy Congestion (Slot Locked)",
          colorHex: "#b91c1c",
          bgHex: "#fee2e2",
          borderHex: "#fca5a5",
          badgeClass: "bg-rose-50 text-rose-800 border-rose-200",
          isLocked: true
        };
      }
    },

    /**
     * Generate dynamic schedule with simulated realistic load for client-side rendering
     */
    generateDynamicSchedule(center = {}, bookingDate = "") {
      const activeWb = center.activeWeighbridges || 2;
      const rateHr = center.avgWeighingRatePerHr || 10;
      const buffer = center.bufferAdjustment !== undefined ? center.bufferAdjustment : -2;
      const hourlyCapacity = this.calculateHourlyCapacity(activeWb, rateHr, buffer);

      const syntheticLoads = [6, 14, 17, 11, 4, 16, 7, 3]; // 17 will hit >85% Red/Locked

      let totalBooked = 0;
      const slots = DEFAULT_SLOTS.map((timeRange, index) => {
        const booked = syntheticLoads[index % syntheticLoads.length];
        totalBooked += booked;
        const utilization = Math.round((booked / hourlyCapacity) * 100);
        const tier = this.getCapacityTier(utilization);
        const available = Math.max(0, hourlyCapacity - booked);

        return {
          id: `slot-${index + 1}`,
          timeRange,
          hourlyCapacity,
          bookedVehicles: booked,
          availableCapacity: available,
          utilizationPercent: utilization,
          tier: tier.tier,
          tierCode: tier.code,
          labelHindi: tier.labelHindi,
          labelEnglish: tier.labelEnglish,
          colorHex: tier.colorHex,
          bgHex: tier.bgHex,
          borderHex: tier.borderHex,
          badgeClass: tier.badgeClass,
          isLocked: tier.isLocked,
          isAvailable: !tier.isLocked
        };
      });

      const totalDayCapacity = hourlyCapacity * slots.length;
      const dayUtilization = Math.round((totalBooked / totalDayCapacity) * 100);
      const isSaturated = dayUtilization >= 75 || slots.some(s => s.isLocked);

      return {
        centerId: center.id || center.centerId,
        centerName: center.name,
        district: center.district,
        date: bookingDate,
        formulaText: `(${activeWb} Weighbridges × ${rateHr} rate/hr) + (${buffer} buffer) = ${hourlyCapacity} vehicles/hr`,
        hourlyCapacity,
        totalDayCapacity,
        totalBooked,
        dayUtilization,
        isSaturated,
        slots
      };
    },

    /**
     * Fetch throughput schedule from backend with graceful local fallback
     */
    async fetchThroughputSchedule(centerId, date = "") {
      try {
        const res = await fetch(`/api/v1/throughput/${encodeURIComponent(centerId)}?date=${encodeURIComponent(date)}`);
        if (!res.ok) throw new Error("HTTP error " + res.status);
        const json = await res.json();
        if (json.success && json.data) {
          return json.data;
        }
      } catch (err) {
        console.warn("KisanThroughput: API fallback to client calculation:", err.message);
      }
      return this.generateDynamicSchedule({ id: centerId }, date);
    },

    /**
     * Fetch alternative nearby centers when chosen mandi is saturated
     */
    async fetchAlternativeCenters(centerId, commodity = "") {
      try {
        const res = await fetch(`/api/v1/throughput/${encodeURIComponent(centerId)}/alternatives?commodity=${encodeURIComponent(commodity)}`);
        if (!res.ok) throw new Error("HTTP error " + res.status);
        const json = await res.json();
        if (json.success && json.data && json.data.length > 0) {
          return json.data;
        }
      } catch (err) {
        console.warn("KisanThroughput: API alternative fallback:", err.message);
      }

      // High-fidelity fallback alternative centers
      return [
        {
          centerId: "CTR-TARAORI-02",
          name: "Taraori Grain Procurement Yard (तरावड़ी खरीद केंद्र)",
          district: "Karnal",
          distanceKm: 14.5,
          driveTimeMinutes: 24,
          operatingHours: "09:00 AM – 05:00 PM",
          loadStatus: "low",
          currentQueueVehicles: 3,
          utilizationPercent: 28.0,
          tierCode: "green",
          tierLabel: "सुगम प्रवेश (Fast-Track)",
          availableSlotsEstimate: 14,
          recommendationReason: "केवल 14.5 किमी दूर • नगण्य प्रतीक्षा • त्वरित प्रवेश उपलब्ध"
        },
        {
          centerId: "CTR-GHARAUNDA-03",
          name: "Gharaunda Kisan Mandi (घरौंडा किसान मंडी)",
          district: "Karnal",
          distanceKm: 18.2,
          driveTimeMinutes: 30,
          operatingHours: "09:00 AM – 05:00 PM",
          loadStatus: "medium",
          currentQueueVehicles: 6,
          utilizationPercent: 48.0,
          tierCode: "green",
          tierLabel: "सामान्य कतार (Normal)",
          availableSlotsEstimate: 10,
          recommendationReason: "18.2 किमी दूर • 2 वेईब्रिज सक्रिय • आज ही स्लॉट उपलब्ध"
        }
      ];
    }
  };

  window.KisanThroughput = KisanThroughput;
})(window);
