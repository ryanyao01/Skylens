import React from "react";
import {
  View,
  Text,
  TextInput,
  StyleSheet,
  DimensionValue,
  Platform,
} from "react-native";
import { Search, Funnel, Plane } from "lucide-react-native";

import { BlackButton } from "@/components/BlackButton";

// Conditionally import MapView so it doesn't crash on the Web
let MapView: any;
if (Platform.OS !== "web") {
  MapView = require("react-native-maps").default;
}

// Flight Marker Component
// TODO: Replace markers with <Marker> components from react-native-maps
interface FlightMarkerProps {
  top: DimensionValue;
  left: DimensionValue;
  rotation: number;
  flightNum: string;
  altitude: string;
}

const FlightMarker: React.FC<FlightMarkerProps> = ({
  top,
  left,
  rotation,
  flightNum,
  altitude,
}) => {
  return (
    <View style={[styles.markerContainer, { top, left }]}>
      {/* Flight Info Popup */}
      <View style={styles.flightLabel}>
        <Text style={styles.flightNumText}>{flightNum}</Text>
        <Text style={styles.altitudeText}>{altitude}</Text>
      </View>

      {/* Plane Icon rotated to match flight path */}
      <View style={{ transform: [{ rotate: `${rotation}deg` }] }}>
        <Plane color="#00D3F2" size={20} strokeWidth={2} />
      </View>
    </View>
  );
};

export default function GlobeScreen() {
  return (
    <View style={styles.container}>
      <View style={styles.mapBase}>
        {Platform.OS === "web" ? (
          <View style={[StyleSheet.absoluteFill, styles.webMapPlaceholder]}>
            <Text style={styles.webMapText}>
              Map view is available on iOS & Android
            </Text>
          </View>
        ) : (
          <MapView
            style={StyleSheet.absoluteFill}
            initialRegion={{
              latitude: 37.78825,
              longitude: -122.4324,
              latitudeDelta: 0.0922,
              longitudeDelta: 0.0421,
            }}
          />
        )}

        {/* User Location Dot */}
        <View style={styles.userLocationOuter}>
          <View style={styles.userLocationInner} />
        </View>

        {/* Flight Markers */}
        <FlightMarker
          top="27.41%"
          left="29.23%"
          rotation={45}
          flightNum="DL402"
          altitude="32,000 FT"
        />
        <FlightMarker
          top="21.67%"
          left="49.97%"
          rotation={-90}
          flightNum="BA112"
          altitude="36,000 FT"
        />
        <FlightMarker
          top="30.56%"
          left="88.61%"
          rotation={180}
          flightNum="JL005"
          altitude="34,000 FT"
        />
      </View>

      {/* Floating Search Header */}
      <View style={styles.headerContainer}>
        <View style={styles.searchRow}>
          {/* Search Input Box */}
          <View style={styles.searchInputContainer}>
            <Search color="#A1A1A1" size={20} strokeWidth={2} />
            <TextInput
              style={styles.textInput}
              placeholder="Search flight"
              placeholderTextColor="#737373"
              underlineColorAndroid="transparent"
            />
          </View>

          {/* Filter / Options Button */}
          <View style={styles.filterButtonContainer}>
            <BlackButton
              icon={Funnel}
              onPress={() => {
                console.log("Filter button pressed");
              }}
            />
          </View>
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  // Main Layout
  container: {
    flex: 1,
    backgroundColor: "#0A0A0A",
  },
  mapBase: {
    flex: 1,
    // Add background image here
  },
  webMapPlaceholder: {
    backgroundColor: "#171717",
    justifyContent: "center",
    alignItems: "center",
  },
  webMapText: {
    color: "#737373",
    fontSize: 14,
  },

  // User Location Dot
  userLocationOuter: {
    position: "absolute",
    top: "49.29%",
    left: "49.58%",
    width: 16,
    height: 16,
    backgroundColor: "rgba(43, 127, 255, 0.75)",
    borderRadius: 8,
    justifyContent: "center",
    alignItems: "center",
  },
  userLocationInner: {
    width: 16,
    height: 16,
    backgroundColor: "#2B7FFF",
    borderColor: "#FFFFFF",
    borderWidth: 2,
    borderRadius: 8,
  },

  // Flight Markers
  markerContainer: {
    position: "absolute",
    alignItems: "center",
    justifyContent: "center",
    // Shifts the transform origin so the icon sits exactly on the coordinate
    marginLeft: -10,
    marginTop: -10,
  },
  flightLabel: {
    position: "absolute",
    top: 24, // Drops it below the plane icon
    backgroundColor: "rgba(23, 23, 23, 0.9)",
    borderColor: "#262626",
    borderWidth: 1,
    borderRadius: 10,
    padding: 8,
    alignItems: "center",
    opacity: 1,
  },
  flightNumText: {
    color: "#FFFFFF",
    fontSize: 12,
    lineHeight: 16,
  },
  altitudeText: {
    color: "#00D3F2",
    fontSize: 10,
    lineHeight: 15,
  },

  // Top Search Header
  headerContainer: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    paddingTop: 48,
    paddingHorizontal: 24,
    paddingBottom: 24,
  },
  searchRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
  },
  searchInputContainer: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "rgba(23, 23, 23, 0.8)",
    borderColor: "#262626",
    borderWidth: 1,
    borderRadius: 16,
    paddingHorizontal: 16,
    height: 48,
  },
  textInput: {
    flex: 1,
    color: "#FFFFFF",
    fontSize: 14,
    marginLeft: 12,
  },
  filterButtonContainer: {
    width: 44,
    height: 48,
    alignItems: "center",
    justifyContent: "center",
  },
});
