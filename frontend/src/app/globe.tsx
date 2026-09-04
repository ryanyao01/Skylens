import {
  Modal,
  Pressable,
  View,
  Text,
  TextInput,
  StyleSheet,
} from "react-native";
import { Search, Funnel } from "lucide-react-native";
import MapView, { Marker } from "react-native-maps";
import { BlackButton } from "@/components/BlackButton";
import { useEffect, useState } from "react";

const API_BASE_URL = (
  process.env.EXPO_PUBLIC_API_URL ?? "http://127.0.0.1:8080"
).replace(/\/$/, "");

interface AirportInfo {
  score: number;
  live_flights: number;
  pred_capacity: number;
  hist_mean_arrivals: number;
  offline_peak_capacity: number;
  live_peak_count: number;
  peak_source: string;
  weather_penalty: number;
  wind_kn: number;
  precip_mm: number;
  visibility_m: number;
  model_trained: boolean;
  scoring_basis: string;
  live_data_status: string;
  live_data_message: string;
  timestamp: string;
  lat: number;
  lon: number;
  name: string;
}

type AirportData = Record<string, AirportInfo>;

// TODO: Fetch airport data continuously in the background
const fetchAirportData = async (signal: AbortSignal): Promise<AirportData> => {
  const response = await fetch(`${API_BASE_URL}/airports/scores`, { signal });
  if (!response.ok) {
    throw new Error(`HTTP error! Status: ${response.status}`);
  }

  return response.json();
};

export default function GlobeScreen() {
  const [airportData, setAirportData] = useState<AirportData>({});
  const [airportDataError, setAirportDataError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();

    const loadAirportData = async () => {
      try {
        const data = await fetchAirportData(controller.signal);
        setAirportData(data);
      } catch (error) {
        if (error instanceof Error && error.name !== "AbortError") {
          setAirportDataError(error.message);
        }
      }
    };

    loadAirportData();

    return () => {
      controller.abort();
    };
  }, []);

  return (
    <View style={styles.container}>
      <Modal
        visible={airportDataError !== null}
        transparent
        animationType="fade"
        onRequestClose={() => setAirportDataError(null)}
      >
        <View style={styles.dialogBackdrop}>
          <View style={styles.dialog}>
            <Text style={styles.dialogTitle}>Unable to load airports</Text>
            <Text style={styles.dialogMessage}>{airportDataError}</Text>
            <Pressable
              accessibilityRole="button"
              onPress={() => setAirportDataError(null)}
              style={({ pressed }) => [
                styles.dialogButton,
                pressed && styles.dialogButtonPressed,
              ]}
            >
              <Text style={styles.dialogButtonText}>Close</Text>
            </Pressable>
          </View>
        </View>
      </Modal>
      <View style={styles.mapBase}>
        <MapView
          style={{ height: "100%", width: "100%" }}
          initialRegion={{
            latitude: 39.3017,
            longitude: -94.7139,
            latitudeDelta: 10,
            longitudeDelta: 10,
          }}
        >
          {Object.entries(airportData).map(([code, airport]) => (
            <Marker
              key={code}
              title={airport.name}
              description={`Airport Code: ${code} | Score: ${airport.score}`}
              coordinate={{ latitude: airport.lat, longitude: airport.lon }}
            />
          ))}
        </MapView>
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
  container: {
    flex: 1,
    backgroundColor: "#0A0A0A",
  },
  mapBase: {
    flex: 1,
  },
  dialogBackdrop: {
    flex: 1,
    backgroundColor: "rgba(0, 0, 0, 0.65)",
    justifyContent: "center",
    alignItems: "center",
    padding: 24,
  },
  dialog: {
    width: "100%",
    maxWidth: 360,
    backgroundColor: "#171717",
    borderColor: "#3A3A3A",
    borderWidth: 1,
    borderRadius: 16,
    padding: 24,
  },
  dialogTitle: {
    color: "#FFFFFF",
    fontSize: 18,
    fontWeight: "600",
    marginBottom: 8,
  },
  dialogMessage: {
    color: "#A1A1A1",
    fontSize: 14,
    lineHeight: 20,
    marginBottom: 20,
  },
  dialogButton: {
    alignSelf: "flex-end",
    backgroundColor: "#FFFFFF",
    borderRadius: 10,
    paddingHorizontal: 18,
    paddingVertical: 10,
  },
  dialogButtonPressed: {
    opacity: 0.75,
  },
  dialogButtonText: {
    color: "#0A0A0A",
    fontSize: 14,
    fontWeight: "600",
  },
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
