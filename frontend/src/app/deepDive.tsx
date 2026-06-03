import { View, Text, StyleSheet, ScrollView } from "react-native";

import { AircraftCard } from "@/components/AircraftCard";

export default function DeepDiveScreen() {
  return (
    <ScrollView
      style={styles.screenContainer}
      contentContainerStyle={styles.scrollContent}
    >
      {/* Header Section */}
      <View style={styles.headerRow}>
        <View>
          <Text style={styles.pageTitle}>Your Catalog</Text>
          <Text style={styles.subtitle}>2 Aircraft Spotted</Text>
        </View>
      </View>

      {/* Roster of Aircraft */}
      <AircraftCard
        model="Boeing 747-8"
        airline="Lufthansa"
        registration="D-ABYT"
        dateStr="Today, 14:32"
        location="New York, USA"
        altitude="35,000 ft"
        speed="560 kts"
        distance="4.2 mi"
        imageSource={{
          uri: "https://readyfortakeoffbook.com/cdn/shop/articles/image-hero-Boeing-747-8-I.webp?v=1773433844&width=2048",
        }}
      />

      <AircraftCard
        model="Airbus A380-800"
        airline="Emirates"
        registration="A6-EEU"
        dateStr="Yesterday, 09:15"
        location="London, UK"
        altitude="38,000 ft"
        speed="545 kts"
        distance="6.8 mi"
        imageSource={{
          uri: "https://content.presspage.com/uploads/2431/1920_An_Emirates_Airbus_A380-932722.jpg?10000",
        }}
      />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  // Global Screen Styles
  screenContainer: {
    flex: 1,
    backgroundColor: "#0A0A0A",
  },
  scrollContent: {
    paddingTop: 48,
    paddingHorizontal: 24,
    paddingBottom: 100, // Extra padding at bottom to prevent nav bar overlap
    gap: 24,
  },

  // Header Styles
  headerRow: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 8,
  },
  pageTitle: {
    color: "#FFFFFF",
    fontSize: 24,
    lineHeight: 32,
    letterSpacing: -0.6,
    // fontFamily: 'Segoe UI Symbol',
  },
  subtitle: {
    color: "#A1A1A1",
    fontSize: 14,
    lineHeight: 20,
  },
});
