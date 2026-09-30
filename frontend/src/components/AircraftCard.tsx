import React from "react";
import { View, Text, ImageBackground, StyleSheet } from "react-native";

import { Clock, MapPin, Share2 } from "lucide-react-native";
import { LinearGradient } from "expo-linear-gradient";
import { WhiteButton } from "@/components/WhiteButton";
import { BlackButton } from "@/components/BlackButton";
import { colors } from "@/constants/theme";

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
            colors={[colors.surface.transparent, colors.surface.base]}
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
            <Clock color={colors.text.secondary} size={16} strokeWidth={1.5} />
            <Text style={styles.infoText}>{dateStr}</Text>
          </View>
          <View style={styles.infoItem}>
            <MapPin color={colors.text.secondary} size={16} strokeWidth={1.5} />
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
    backgroundColor: colors.surface.base,
    borderColor: colors.border.subtle,
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
    color: colors.text.primary,
    fontSize: 20,
    lineHeight: 25,
  },
  airlineText: {
    color: colors.text.accent,
    fontSize: 14,
    lineHeight: 20,
  },
  registrationBadge: {
    backgroundColor: colors.overlay.fillStrong,
    borderColor: colors.overlay.border,
    borderWidth: 1,
    borderRadius: 10,
    paddingVertical: 7,
    paddingHorizontal: 12,
  },
  registrationText: {
    color: colors.overlay.text,
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
    color: colors.text.secondary,
    fontSize: 12,
  },

  // Stats Grid
  statsGrid: {
    flexDirection: "row",
    justifyContent: "space-between",
  },
  statBox: {
    flex: 1,
    backgroundColor: colors.surface.inset,
    borderColor: colors.border.subtle,
    borderWidth: 1,
    borderRadius: 14,
    height: 66,
    justifyContent: "center",
    alignItems: "center",
    marginHorizontal: 4,
  },
  statLabel: {
    color: colors.text.tertiary,
    fontSize: 12,
    marginBottom: 4,
  },
  statValue: {
    color: colors.text.primary,
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
