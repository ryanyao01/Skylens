import React from "react";
import { View, Text, ImageBackground, StyleSheet } from "react-native";

import { Clock, MapPin, Share2 } from "lucide-react-native";
import { LinearGradient } from "expo-linear-gradient";
import { WhiteButton } from "@/components/WhiteButton";
import { BlackButton } from "@/components/BlackButton";

interface AircraftCardProps {
  model: string;
  airline: string;
  registration: string;
  dateStr: string;
  location: string;
  altitude: string;
  speed: string;
  distance: string;
  imageSource: any; // e.g., require('../assets/boeing.jpg')
}

export const AircraftCard: React.FC<AircraftCardProps> = ({
  model,
  airline,
  registration,
  dateStr,
  location,
  altitude,
  speed,
  distance,
  imageSource,
}) => {
  return (
    <View style={styles.cardContainer}>
      {/* Top Half: Image, Gradient Overlay, and Header Text */}
      <View style={styles.imageSection}>
        <ImageBackground source={imageSource} style={styles.imageBackground}>
          {/* Dark gradient so the white text stays readable over bright photos */}
          <LinearGradient
            colors={["rgba(23, 23, 23, 0)", "#171717"]}
            style={styles.gradientOverlay}
          />

          <View style={styles.imageHeaderRow}>
            <View>
              <Text style={styles.aircraftTitle}>{model}</Text>
              <Text style={styles.airlineText}>{airline}</Text>
            </View>

            <View style={styles.registrationBadge}>
              <Text style={styles.registrationText}>{registration}</Text>
            </View>
          </View>
        </ImageBackground>
      </View>

      {/* Bottom Half: Details, Stats, and Action Buttons */}
      <View style={styles.detailsSection}>
        {/* Row 1: Time and Location */}
        <View style={styles.infoRow}>
          <View style={styles.infoItem}>
            <Clock color="#A1A1A1" size={16} strokeWidth={1.5} />
            <Text style={styles.infoText}>{dateStr}</Text>
          </View>
          <View style={styles.infoItem}>
            <MapPin color="#A1A1A1" size={16} strokeWidth={1.5} />
            <Text style={styles.infoText}>{location}</Text>
          </View>
        </View>

        {/* Row 2: Stats Grid */}
        <View style={styles.statsGrid}>
          <View style={styles.statBox}>
            <Text style={styles.statLabel}>ALT</Text>
            <Text style={styles.statValue}>{altitude}</Text>
          </View>
          <View style={styles.statBox}>
            <Text style={styles.statLabel}>SPD</Text>
            <Text style={styles.statValue}>{speed}</Text>
          </View>
          <View style={styles.statBox}>
            <Text style={styles.statLabel}>DIST</Text>
            <Text style={styles.statValue}>{distance}</Text>
          </View>
        </View>

        {/* Row 3: Action Buttons */}
        <View style={styles.actionRow}>
          <View style={{ flex: 1, marginRight: 12 }}>
            <WhiteButton
              text="View Details"
              onPress={() => console.log("Details pressed")}
            />
          </View>
          <View style={styles.shareButtonContainer}>
            <BlackButton
              icon={Share2}
              onPress={() => console.log("Bookmark pressed")}
            />
          </View>
        </View>
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  // Card Core Structure
  cardContainer: {
    backgroundColor: "#171717",
    borderColor: "#262626",
    borderWidth: 1,
    borderRadius: 24,
    overflow: "hidden", // Ensures the image doesn't bleed out of the rounded corners
  },
  // Card Image Half
  imageSection: {
    height: 192,
    width: "100%",
  },
  imageBackground: {
    flex: 1,
    justifyContent: "flex-end",
  },
  gradientOverlay: {
    ...StyleSheet.absoluteFill,
  },
  imageHeaderRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-end",
    padding: 16,
  },
  aircraftTitle: {
    color: "#FFFFFF",
    fontSize: 20,
    lineHeight: 25,
  },
  airlineText: {
    color: "#00D3F2",
    fontSize: 14,
    lineHeight: 20,
  },
  registrationBadge: {
    backgroundColor: "rgba(0, 0, 0, 0.5)",
    borderColor: "rgba(255, 255, 255, 0.1)",
    borderWidth: 1,
    borderRadius: 10,
    paddingVertical: 7,
    paddingHorizontal: 12,
  },
  registrationText: {
    color: "rgba(255, 255, 255, 0.8)",
    fontSize: 12,
    // fontFamily: 'Consolas',
  },
  // Card Details Half
  detailsSection: {
    padding: 20,
    gap: 24,
  },
  infoRow: {
    flexDirection: "row",
    gap: 16,
  },
  infoItem: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },
  infoText: {
    color: "#A1A1A1",
    fontSize: 12,
  },

  // Stats Grid
  statsGrid: {
    flexDirection: "row",
    justifyContent: "space-between",
  },
  statBox: {
    flex: 1,
    backgroundColor: "#0A0A0A",
    borderColor: "#262626",
    borderWidth: 1,
    borderRadius: 14,
    height: 66,
    justifyContent: "center",
    alignItems: "center",
    marginHorizontal: 4,
  },
  statLabel: {
    color: "#737373",
    fontSize: 12,
    marginBottom: 4,
  },
  statValue: {
    color: "#FFFFFF",
    fontSize: 14,
    // fontFamily: 'Consolas',
  },

  // Action Buttons
  actionRow: {
    flexDirection: "row",
    alignItems: "center",
  },
  shareButtonContainer: {
    width: 44,
    height: 48,
    alignItems: "center",
    justifyContent: "center",
  },
});
